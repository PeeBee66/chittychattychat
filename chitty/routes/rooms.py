import uuid
from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models.rooms import Room
from models.participants import Participant
from services.crypto import crypto_service
from services.names import name_service
from models.db import db
import logging

logger = logging.getLogger(__name__)

rooms_bp = Blueprint('rooms', __name__, url_prefix='/api/v1/rooms')

def get_client_ip():
    """Get client IP address"""
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()

def get_or_create_device_id():
    """Get device ID from session or create new one"""
    if 'device_id' not in session:
        session['device_id'] = crypto_service.generate_device_id()
        session.permanent = True
    return session['device_id']

@rooms_bp.route('', methods=['POST'])
def create_room():
    """Create a new room in pending state"""
    try:
        data = request.get_json() or {}
        room_id = data.get('room_id')

        # Create room with optional specified ID
        room = Room.create_room(room_id=room_id)
        if not room:
            logger.error("Failed to create room - Room.create_room() returned None")
            return jsonify({'error': 'Failed to create room'}), 500
        
        logger.info(f"🏠 Room created: {room['room_id']} (status: pending)")
        
        # Create JWT token for host
        # Store room data in additional_claims instead of identity
        token_data = {
            'room_id': room['room_id'],
            'role': 'host',
            'device_id': get_or_create_device_id()
        }
        room_token = create_access_token(
            identity=f"{room['room_id']}_host",  # Simple string identity
            additional_claims=token_data,
            expires_delta=False
        )
        
        return jsonify({
            'room_id': room['room_id'],
            'room_token': room_token,
            'status': 'pending'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating room: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@rooms_bp.route('/<room_id>/accept', methods=['POST'])
@jwt_required()
def accept_room(room_id):
    """Accept a room and activate it with 24h expiry"""
    try:
        from flask_jwt_extended import get_jwt
        jwt_data = get_jwt()
        token_data = {
            'room_id': jwt_data.get('room_id'),
            'role': jwt_data.get('role'),
            'device_id': jwt_data.get('device_id')
        }
        if token_data['room_id'] != room_id or token_data['role'] != 'host':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get room
        room = Room.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        if room['status'] != 'pending':
            return jsonify({'error': 'Room already accepted or invalid'}), 400
        
        # Accept room
        if not Room.accept_room(room_id):
            logger.error(f"Failed to accept room {room_id}")
            return jsonify({'error': 'Failed to accept room'}), 500
        
        logger.info(f"✅ Room accepted and activated: {room_id} (expires in 24h)")
        
        # Generate and store room key
        room_key = crypto_service.generate_room_key()
        room_key_enc = crypto_service.encrypt_room_key(room_key)
        
        # Store encrypted room key
        query = """
        INSERT INTO room_keys (room_id, room_key_enc)
        VALUES (%s, %s)
        """
        db.execute(query, (room_id, room_key_enc))
        
        # Add host as participant when accepting the room
        client_ip = get_client_ip()
        participant = Participant.create_participant(room_id, 'host', token_data['device_id'], client_ip)
        if participant:
            logger.info(f"👤 Host added as participant: room {room_id} (participant {participant['id']})")
            
            # Update token with participant_id
            updated_token_data = {
                'room_id': room_id,
                'participant_id': participant['id'],
                'role': 'host',
                'device_id': token_data['device_id']
            }
            updated_token = create_access_token(
                identity=f"{room_id}_{participant['id']}",
                additional_claims=updated_token_data,
                expires_delta=False
            )
            
            # Provide room key to host
            import base64
            room_key_b64 = base64.b64encode(room_key).decode('utf-8')
            
            return jsonify({
                'success': True, 
                'status': 'active',
                'participant_token': updated_token,
                'participant_id': participant['id'],
                'room_key': room_key_b64
            }), 200
        else:
            logger.warning(f"Failed to create host participant for room {room_id}")
        
        return jsonify({'success': True, 'status': 'active'}), 200
        
    except Exception as e:
        logger.error(f"Error accepting room: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@rooms_bp.route('/<room_id>/join', methods=['POST'])
def join_room(room_id):
    """Join an active room"""
    try:
        # Get room
        room = Room.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        if room['status'] not in ['active', 'locked']:
            return jsonify({'error': 'Room is not available for joining'}), 400
        
        # Check if room expired
        if room['expires_at']:
            from datetime import datetime
            expires_at = datetime.fromisoformat(room['expires_at'].replace('Z', '+00:00'))
            if expires_at < datetime.utcnow().replace(tzinfo=expires_at.tzinfo):
                return jsonify({'error': 'Room has expired'}), 410
        
        device_id = get_or_create_device_id()
        client_ip = get_client_ip()
        
        # Check if this device is already in the room
        existing_participant = Participant.get_participant_by_device(room_id, device_id)
        if existing_participant:
            # Allow reconnection
            token_data = {
                'room_id': room_id,
                'participant_id': existing_participant['id'],
                'role': existing_participant['role'],
                'device_id': device_id
            }
            participant_token = create_access_token(
                identity=f"{room_id}_{existing_participant['id']}",
                additional_claims=token_data,
                expires_delta=False
            )
            
            # Get room key for existing participant
            room_key_b64 = None
            try:
                key_query = "SELECT room_key_enc FROM room_keys WHERE room_id = %s"
                key_result = db.execute_one(key_query, (room_id,))
                if key_result:
                    room_key_bytes = crypto_service.decrypt_room_key(bytes(key_result['room_key_enc']))
                    import base64
                    room_key_b64 = base64.b64encode(room_key_bytes).decode('utf-8')
            except Exception as e:
                logger.error(f"Failed to get room key for reconnection: {e}")
            
            return jsonify({
                'participant_id': existing_participant['id'],
                'participant_token': participant_token,
                'role': existing_participant['role'],
                'display_name': existing_participant['display_name'],
                'room_key': room_key_b64
            }), 200
        
        # Count ACTIVE participants using connection manager
        from services.connection_manager import connection_manager
        active_participant_count = connection_manager.get_connection_count(room_id)
        
        # Also check database participant count as backup
        db_participant_count = Participant.count_participants(room_id)
        
        # Use the higher of the two counts for safety
        max_participant_count = max(active_participant_count, db_participant_count)
        
        if max_participant_count >= 2:
            logger.warning(f"Room {room_id} join rejected: full ({active_participant_count} active, {db_participant_count} total)")
            return jsonify({
                'error': 'Room is full', 
                'message': 'This room already has 2 participants. Only 2 people can chat at a time.'
            }), 409
        
        # Determine role based on database count (more reliable for role assignment)
        role = 'host' if db_participant_count == 0 else 'guest'
        
        # Create participant
        participant = Participant.create_participant(room_id, role, device_id, client_ip)
        if not participant:
            logger.error(f"Failed to create participant for room {room_id}, role: {role}")
            return jsonify({'error': 'Failed to join room'}), 500
        
        logger.info(f"👤 Participant joined: {role} in room {room_id} (IP: {client_ip})")
        
        # Lock room if we now have 2 participants
        if db_participant_count == 1:  # This is the second participant
            Room.lock_room(room_id)
            logger.info(f"🔒 Room locked: {room_id} (2 participants)")
        
        # Create JWT token
        token_data = {
            'room_id': room_id,
            'participant_id': participant['id'],
            'role': role,
            'device_id': device_id
        }
        participant_token = create_access_token(
            identity=f"{room_id}_{participant['id']}",
            additional_claims=token_data,
            expires_delta=False
        )
        
        # Get room key for new participant
        room_key_b64 = None
        try:
            key_query = "SELECT room_key_enc FROM room_keys WHERE room_id = %s"
            key_result = db.execute_one(key_query, (room_id,))
            if key_result:
                room_key_bytes = crypto_service.decrypt_room_key(bytes(key_result['room_key_enc']))
                import base64
                room_key_b64 = base64.b64encode(room_key_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to get room key for new participant: {e}")
        
        return jsonify({
            'participant_id': participant['id'],
            'participant_token': participant_token,
            'role': role,
            'device_bind_required': True,
            'room_key': room_key_b64
        }), 201
        
    except Exception as e:
        logger.error(f"Error joining room: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@rooms_bp.route('/<room_id>/name', methods=['POST'])
@jwt_required()
def set_display_name(room_id):
    """Set participant's display name"""
    try:
        from flask_jwt_extended import get_jwt
        jwt_data = get_jwt()
        if jwt_data.get('room_id') != room_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        if not data or 'display_name' not in data:
            return jsonify({'error': 'Display name is required'}), 400
        
        display_name = data['display_name'].strip()
        if not display_name:
            return jsonify({'error': 'Display name cannot be empty'}), 400
        
        # Set display name
        participant_id = jwt_data.get('participant_id')
        if Participant.set_display_name(participant_id, display_name):
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Failed to set display name'}), 500
            
    except Exception as e:
        logger.error(f"Error setting display name: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@rooms_bp.route('/<room_id>/destroy', methods=['POST'])
@jwt_required()
def destroy_room(room_id):
    """Destroy a room immediately"""
    try:
        from flask_jwt_extended import get_jwt
        jwt_data = get_jwt()
        if jwt_data.get('room_id') != room_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Close room
        if Room.close_room(room_id, reason='destroyed'):
            logger.info(f"💥 Room destroyed: {room_id} (manually destroyed)")
            return jsonify({'success': True}), 200
        else:
            logger.error(f"Failed to destroy room {room_id}")
            return jsonify({'error': 'Failed to destroy room'}), 500
            
    except Exception as e:
        logger.error(f"Error destroying room: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@rooms_bp.route('/<room_id>', methods=['GET'])
@jwt_required()
def get_room_info(room_id):
    """Get room information"""
    try:
        from flask_jwt_extended import get_jwt
        jwt_data = get_jwt()
        if jwt_data.get('room_id') != room_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        room = Room.get_room(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        participants = Participant.get_room_participants(room_id)
        participant_count = len(participants)
        
        # Don't expose IP addresses in public API
        safe_participants = []
        for p in participants:
            safe_participants.append({
                'id': p['id'],
                'role': p['role'],
                'display_name': p['display_name'],
                'joined_at': p['joined_at']
            })
        
        return jsonify({
            'room': room,
            'participants': safe_participants,
            'participant_count': participant_count
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting room info: {e}")
        return jsonify({'error': 'Internal server error'}), 500