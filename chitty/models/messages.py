from datetime import datetime
from typing import Optional, Dict, List
from .db import db
import logging

logger = logging.getLogger(__name__)

class Message:
    @staticmethod
    def create_message(room_id: str, participant_id: int, body_ct: bytes, 
                      nonce: bytes, tag: bytes, msg_type: str = 'text', 
                      ip_address: str = None) -> Optional[Dict]:
        """Create a new encrypted message"""
        try:
            query = """
            INSERT INTO messages (room_id, participant_id, body_ct, nonce, tag, msg_type, ip_address, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, room_id, participant_id, created_at, msg_type
            """
            result = db.execute_one(query, (
                room_id, participant_id, body_ct, nonce, tag, msg_type, ip_address, datetime.utcnow()
            ))
            if result:
                return {
                    'id': result['id'],
                    'room_id': result['room_id'],
                    'participant_id': result['participant_id'],
                    'created_at': result['created_at'].isoformat(),
                    'msg_type': result['msg_type']
                }
            return None
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            return None
    
    @staticmethod
    def get_room_messages(room_id: str, limit: int = 100) -> List[Dict]:
        """Get messages for a room (encrypted)"""
        try:
            query = """
            SELECT m.id, m.room_id, m.participant_id, m.created_at, 
                   m.body_ct, m.nonce, m.tag, m.msg_type, m.ip_address,
                   p.display_name, p.role
            FROM messages m
            LEFT JOIN participants p ON m.participant_id = p.id
            WHERE m.room_id = %s
            ORDER BY m.created_at ASC
            LIMIT %s
            """
            results = db.execute(query, (room_id, limit))
            messages = []
            if results:
                for row in results:
                    messages.append({
                        'id': row['id'],
                        'room_id': row['room_id'],
                        'participant_id': row['participant_id'],
                        'created_at': row['created_at'].isoformat(),
                        'body_ct': bytes(row['body_ct']),
                        'nonce': bytes(row['nonce']),
                        'tag': bytes(row['tag']),
                        'msg_type': row['msg_type'],
                        'ip_address': str(row['ip_address']) if row['ip_address'] else None,
                        'display_name': row['display_name'],
                        'role': row['role']
                    })
            return messages
        except Exception as e:
            logger.error(f"Error getting room messages: {e}")
            return []
    
    @staticmethod
    def get_latest_message_preview(room_id: str) -> Optional[Dict]:
        """Get the latest message for preview (returns encrypted data)"""
        try:
            query = """
            SELECT m.id, m.created_at, m.body_ct, m.nonce, m.tag, m.msg_type,
                   p.display_name
            FROM messages m
            LEFT JOIN participants p ON m.participant_id = p.id
            WHERE m.room_id = %s
            ORDER BY m.created_at DESC
            LIMIT 1
            """
            result = db.execute_one(query, (room_id,))
            if result:
                return {
                    'id': result['id'],
                    'created_at': result['created_at'].isoformat(),
                    'body_ct': bytes(result['body_ct']),
                    'nonce': bytes(result['nonce']),
                    'tag': bytes(result['tag']),
                    'msg_type': result['msg_type'],
                    'display_name': result['display_name']
                }
            return None
        except Exception as e:
            logger.error(f"Error getting latest message preview: {e}")
            return None
    
    @staticmethod
    def count_room_messages(room_id: str) -> int:
        """Count messages in a room"""
        try:
            query = "SELECT COUNT(*) as count FROM messages WHERE room_id = %s"
            result = db.execute_one(query, (room_id,))
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Error counting messages: {e}")
            return 0