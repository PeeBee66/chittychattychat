import os
import logging
import ipaddress
from datetime import datetime
from flask import Flask, render_template, request, jsonify, abort
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from minio import Minio
from minio.error import S3Error
import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AdminPanel:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'admin-secret-key')
        
        # Database connection
        self.db_url = os.getenv('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # MinIO connection
        self.minio_endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
        self.minio_access_key = os.getenv('MINIO_ACCESS_KEY')
        self.minio_secret_key = os.getenv('MINIO_SECRET_KEY')
        self.archive_bucket = os.getenv('S3_BUCKET_ARCHIVES', 'archives')
        
        if not all([self.minio_access_key, self.minio_secret_key]):
            raise ValueError("MinIO credentials are required")
        
        # Initialize MinIO client
        self.minio_client = Minio(
            self.minio_endpoint,
            access_key=self.minio_access_key,
            secret_key=self.minio_secret_key,
            secure=False
        )
        
        # Master key for decryption
        master_key_b64 = os.getenv('MASTER_KEY')
        if not master_key_b64:
            raise ValueError("MASTER_KEY environment variable is required")
        self.master_key = base64.b64decode(master_key_b64)
        
        # Allowed CIDR blocks
        allowed_cidrs = os.getenv('ALLOWED_ADMIN_CIDRS', '127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16')
        self.allowed_networks = []
        for cidr in allowed_cidrs.split(','):
            try:
                self.allowed_networks.append(ipaddress.ip_network(cidr.strip(), strict=False))
            except ValueError as e:
                logger.warning(f"Invalid CIDR {cidr}: {e}")
        
        self.setup_routes()
    
    def check_ip_allowed(self, ip_str):
        """Check if IP is allowed"""
        try:
            client_ip = ipaddress.ip_address(ip_str)
            for network in self.allowed_networks:
                if client_ip in network:
                    return True
            return False
        except ValueError:
            return False
    
    def get_client_ip(self):
        """Get client IP address"""
        if request.environ.get('HTTP_X_FORWARDED_FOR'):
            return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
        return request.environ.get('REMOTE_ADDR', '127.0.0.1')
    
    def require_admin_access(self):
        """Middleware to check admin access"""
        client_ip = self.get_client_ip()
        if not self.check_ip_allowed(client_ip):
            logger.warning(f"Admin access denied for IP: {client_ip}")
            abort(403)
    
    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
    
    def decrypt_room_key(self, encrypted_room_key):
        """Decrypt room key with master key"""
        try:
            nonce = encrypted_room_key[:12]
            ciphertext = encrypted_room_key[12:]
            aesgcm = AESGCM(self.master_key)
            room_key = aesgcm.decrypt(nonce, ciphertext, None)
            return room_key
        except Exception as e:
            logger.error(f"Error decrypting room key: {e}")
            raise
    
    def decrypt_message(self, room_key, ciphertext, nonce, tag):
        """Decrypt a message with room key"""
        try:
            aesgcm = AESGCM(room_key)
            full_ciphertext = ciphertext + tag
            plaintext_bytes = aesgcm.decrypt(nonce, full_ciphertext, None)
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Error decrypting message: {e}")
            return '[DECRYPTION_FAILED]'
    
    def setup_routes(self):
        @self.app.before_request
        def before_request():
            self.require_admin_access()
        
        @self.app.route('/')
        def dashboard():
            """Admin dashboard showing all rooms"""
            try:
                with self.get_db_connection() as conn:
                    with conn.cursor() as cursor:
                        # Get rooms with participant counts and latest messages
                        query = """
                        SELECT 
                            r.room_id,
                            r.status,
                            r.created_at,
                            r.accepted_at,
                            r.expires_at,
                            r.closed_at,
                            r.archive_key,
                            COUNT(DISTINCT p.id) as participant_count,
                            EXTRACT(EPOCH FROM (r.expires_at - NOW())) as time_left_seconds,
                            COUNT(DISTINCT m.id) as message_count
                        FROM rooms r
                        LEFT JOIN participants p ON r.room_id = p.room_id
                        LEFT JOIN messages m ON r.room_id = m.room_id
                        GROUP BY r.room_id, r.status, r.created_at, r.accepted_at, r.expires_at, r.closed_at, r.archive_key
                        ORDER BY r.created_at DESC
                        LIMIT 100
                        """
                        
                        cursor.execute(query)
                        rooms_data = cursor.fetchall()
                        
                        rooms = []
                        for row in rooms_data:
                            room_data = dict(row)
                            
                            # Get latest message preview
                            preview_query = """
                            SELECT m.body_ct, m.nonce, m.tag, m.msg_type, m.created_at,
                                   p.display_name
                            FROM messages m
                            LEFT JOIN participants p ON m.participant_id = p.id
                            WHERE m.room_id = %s
                            ORDER BY m.created_at DESC
                            LIMIT 1
                            """
                            cursor.execute(preview_query, (room_data['room_id'],))
                            latest_msg = cursor.fetchone()
                            
                            if latest_msg:
                                try:
                                    # Get room key and decrypt preview
                                    key_query = "SELECT room_key_enc FROM room_keys WHERE room_id = %s"
                                    cursor.execute(key_query, (room_data['room_id'],))
                                    key_row = cursor.fetchone()
                                    
                                    if key_row:
                                        room_key = self.decrypt_room_key(bytes(key_row['room_key_enc']))
                                        decrypted_text = self.decrypt_message(
                                            room_key,
                                            bytes(latest_msg['body_ct']),
                                            bytes(latest_msg['nonce']),
                                            bytes(latest_msg['tag'])
                                        )
                                        room_data['latest_message'] = {
                                            'text': decrypted_text[:50] + ('...' if len(decrypted_text) > 50 else ''),
                                            'sender': latest_msg['display_name'] or 'Anonymous',
                                            'created_at': latest_msg['created_at'],
                                            'msg_type': latest_msg['msg_type']
                                        }
                                    else:
                                        room_data['latest_message'] = {'text': '[No key available]', 'sender': '', 'created_at': None, 'msg_type': 'text'}
                                except Exception as e:
                                    logger.error(f"Failed to decrypt message preview: {e}")
                                    room_data['latest_message'] = {'text': '[Decryption failed]', 'sender': '', 'created_at': None, 'msg_type': 'text'}
                            else:
                                room_data['latest_message'] = None
                            
                            rooms.append(room_data)
                
                return render_template('dashboard.html', rooms=rooms)
                
            except Exception as e:
                logger.error(f"Dashboard error: {e}")
                return render_template('error.html', error="Failed to load dashboard"), 500
        
        @self.app.route('/room/<room_id>')
        def room_transcript(room_id):
            """Show full transcript for a room"""
            try:
                with self.get_db_connection() as conn:
                    with conn.cursor() as cursor:
                        # Get room info
                        room_query = """
                        SELECT room_id, status, created_at, accepted_at, expires_at, closed_at, archive_key
                        FROM rooms WHERE room_id = %s
                        """
                        cursor.execute(room_query, (room_id,))
                        room = cursor.fetchone()
                        
                        if not room:
                            return render_template('error.html', error="Room not found"), 404
                        
                        room_data = dict(room)
                        
                        # Get participants
                        participants_query = """
                        SELECT id, role, device_id, display_name, ip_address, joined_at
                        FROM participants WHERE room_id = %s
                        ORDER BY joined_at
                        """
                        cursor.execute(participants_query, (room_id,))
                        participants = [dict(p) for p in cursor.fetchall()]
                        
                        # Get and decrypt messages
                        messages_query = """
                        SELECT m.id, m.participant_id, m.created_at, m.body_ct, m.nonce, m.tag, 
                               m.msg_type, m.ip_address, p.display_name, p.role
                        FROM messages m
                        LEFT JOIN participants p ON m.participant_id = p.id
                        WHERE m.room_id = %s
                        ORDER BY m.created_at ASC
                        """
                        cursor.execute(messages_query, (room_id,))
                        encrypted_messages = cursor.fetchall()
                        
                        # Get room key
                        key_query = "SELECT room_key_enc FROM room_keys WHERE room_id = %s"
                        cursor.execute(key_query, (room_id,))
                        key_row = cursor.fetchone()
                        
                        messages = []
                        if key_row:
                            try:
                                room_key = self.decrypt_room_key(bytes(key_row['room_key_enc']))
                                
                                for msg in encrypted_messages:
                                    msg_dict = dict(msg)
                                    try:
                                        decrypted_text = self.decrypt_message(
                                            room_key,
                                            bytes(msg['body_ct']),
                                            bytes(msg['nonce']),
                                            bytes(msg['tag'])
                                        )
                                        msg_dict['decrypted_text'] = decrypted_text
                                        msg_dict['decryption_error'] = False
                                    except Exception as e:
                                        msg_dict['decrypted_text'] = '[DECRYPTION_FAILED]'
                                        msg_dict['decryption_error'] = True
                                    
                                    messages.append(msg_dict)
                                    
                            except Exception as e:
                                logger.error(f"Failed to decrypt room key: {e}")
                                # Show encrypted messages
                                for msg in encrypted_messages:
                                    msg_dict = dict(msg)
                                    msg_dict['decrypted_text'] = '[ROOM_KEY_DECRYPTION_FAILED]'
                                    msg_dict['decryption_error'] = True
                                    messages.append(msg_dict)
                        else:
                            # No room key found
                            for msg in encrypted_messages:
                                msg_dict = dict(msg)
                                msg_dict['decrypted_text'] = '[NO_ROOM_KEY]'
                                msg_dict['decryption_error'] = True
                                messages.append(msg_dict)
                        
                        return render_template('transcript.html', 
                                             room=room_data, 
                                             participants=participants, 
                                             messages=messages)
                
            except Exception as e:
                logger.error(f"Transcript error: {e}")
                return render_template('error.html', error="Failed to load transcript"), 500
        
        @self.app.route('/archive/<room_id>')
        def archived_transcript(room_id):
            """Show archived transcript from MinIO"""
            try:
                with self.get_db_connection() as conn:
                    with conn.cursor() as cursor:
                        # Get room archive key
                        cursor.execute("SELECT archive_key FROM rooms WHERE room_id = %s", (room_id,))
                        room = cursor.fetchone()
                        
                        if not room or not room['archive_key']:
                            return render_template('error.html', error="Archive not found"), 404
                        
                        # Get archive from MinIO
                        try:
                            response = self.minio_client.get_object(self.archive_bucket, room['archive_key'])
                            archive_data = json.loads(response.read().decode('utf-8'))
                            response.close()
                            response.release_conn()
                            
                            return render_template('archive.html', archive=archive_data)
                            
                        except S3Error as e:
                            logger.error(f"MinIO error: {e}")
                            return render_template('error.html', error="Failed to load archive from storage"), 500
                
            except Exception as e:
                logger.error(f"Archive error: {e}")
                return render_template('error.html', error="Failed to load archived transcript"), 500
        
        @self.app.route('/health')
        def health():
            """Health check"""
            try:
                # Test database
                with self.get_db_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1")
                
                # Test MinIO
                self.minio_client.list_buckets()
                
                return {'status': 'healthy', 'service': 'admin-panel'}, 200
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {'status': 'unhealthy', 'error': str(e)}, 503
        
        @self.app.errorhandler(403)
        def forbidden(error):
            return render_template('403.html'), 403
        
        @self.app.errorhandler(404)
        def not_found(error):
            return render_template('404.html'), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return render_template('error.html', error="Internal server error"), 500

# Create application instance
admin_panel = AdminPanel()
app = admin_panel.app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5056, debug=True)