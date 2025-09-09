import logging
import time
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token
from models.participants import Participant
from models.rooms import Room
from models.messages import Message
from services.crypto import crypto_service
from services.connection_manager import connection_manager
from models.db import db
import base64
import json

logger = logging.getLogger(__name__)

def init_socketio(app):
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
    
    @socketio.on('connect')
    def on_connect(auth):
        """Handle client connection"""
        try:
            if not auth or 'token' not in auth:
                logger.warning("Connection rejected: No token provided")
                disconnect()
                return False
            
            # Decode JWT token
            try:
                decoded = decode_token(auth['token'])
                # Get data from additional claims
                room_id = decoded.get('room_id')
                participant_id = decoded.get('participant_id')
                device_id = decoded.get('device_id')
                role = decoded.get('role')
                
                if not all([room_id, participant_id, device_id]):
                    logger.warning("Connection rejected: Missing required token data")
                    disconnect()
                    return False
            except Exception as e:
                logger.warning(f"Connection rejected: Invalid token - {e}")
                disconnect()
                return False
            
            # Validate participant and device
            if not Participant.validate_device_access(room_id, participant_id, device_id):
                logger.warning(f"Connection rejected: Invalid device access for participant {participant_id}")
                disconnect()
                return False
            
            # Get room info
            room = Room.get_room(room_id)
            if not room or room['status'] not in ['active', 'locked']:
                logger.warning(f"Connection rejected: Room {room_id} not available")
                disconnect()
                return False
            
            # Join socket room
            join_room(room_id)
            
            # Store connection info in session
            from flask import session
            session['room_id'] = room_id
            session['participant_id'] = participant_id
            session['device_id'] = device_id
            session['role'] = role
            
            # Add connection to manager
            session_id = request.sid
            connection_manager.add_connection(session_id, room_id, participant_id, role)
            
            logger.info(f"🔌 Socket connected: {role} in room {room_id} (participant {participant_id})")
            
            # Get participant info for connection status
            participant = Participant.get_participant(participant_id)
            
            # Emit connection status to all participants in room
            emit('participant_connected', {
                'participant_id': participant_id,
                'role': role,
                'display_name': participant.get('display_name') if participant else None
            }, room=room_id)
            
            # Remove this line - we'll update status below
            
            # Get room participants and current connection status
            all_participants = Participant.get_room_participants(room_id)
            connected_count = connection_manager.get_connection_count(room_id)
            
            # Mark participants as connected based on connection manager
            for participant_data in all_participants:
                participant_data['is_connected'] = connection_manager.is_participant_connected(
                    room_id, participant_data['id']
                )
            
            emit('connection_status_update', {
                'connected_participants': connected_count,
                'total_participants': len(all_participants),
                'is_secure': connected_count >= 2,
                'participants': all_participants
            }, room=room_id)
            
            # Emit room locked status if applicable
            if room['status'] == 'locked':
                emit('room_locked', {'room_id': room_id})
            
            # Send timer update
            if room['expires_at']:
                from datetime import datetime
                expires_at = datetime.fromisoformat(room['expires_at'].replace('Z', '+00:00'))
                time_left = (expires_at - datetime.utcnow().replace(tzinfo=expires_at.tzinfo)).total_seconds()
                if time_left > 0:
                    emit('timer_update', {'time_left_seconds': int(time_left)})
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
            disconnect()
            return False
    
    @socketio.on('disconnect')
    def on_disconnect():
        """Handle client disconnection"""
        try:
            from flask import session
            room_id = session.get('room_id')
            participant_id = session.get('participant_id')
            role = session.get('role')
            
            if room_id and participant_id:
                # Remove connection from manager
                session_id = request.sid
                session_info = connection_manager.remove_connection(session_id)
                
                # Get participant info before leaving
                participant = Participant.get_participant(participant_id)
                
                # Emit disconnection to all participants in room
                emit('participant_disconnected', {
                    'participant_id': participant_id,
                    'role': role,
                    'display_name': participant.get('display_name') if participant else None
                }, room=room_id)
                
                # Leave room
                leave_room(room_id)
                
                # Clean up inactive participants - remove disconnected participant from DB
                Participant.remove_participant(participant_id)
                
                # Get remaining connected participants
                room_connections = connection_manager.get_room_connections(room_id)
                remaining_participant_ids = list(room_connections.keys())
                
                # Clean up any other inactive participants
                Participant.cleanup_inactive_participants(room_id, remaining_participant_ids)
                
                # Update room status based on remaining participants
                connected_count = len(remaining_participant_ids)
                if connected_count < 2:
                    # Unlock room if less than 2 participants
                    from models.rooms import Room
                    current_room = Room.get_room(room_id)
                    if current_room and current_room['status'] == 'locked':
                        # Change back to active status to allow new participants
                        Room.unlock_room(room_id)
                        logger.info(f"🔓 Room unlocked: {room_id} ({connected_count} participants remaining)")
                
                # Get updated participant list
                all_participants = Participant.get_room_participants(room_id)
                
                # Mark participants as connected based on connection manager
                for participant_data in all_participants:
                    participant_data['is_connected'] = connection_manager.is_participant_connected(
                        room_id, participant_data['id']
                    )
                
                # Emit updated status after disconnect
                emit('connection_status_update', {
                    'connected_participants': connected_count,
                    'total_participants': len(all_participants),
                    'is_secure': connected_count >= 2,
                    'participants': all_participants
                }, room=room_id)
                
                logger.info(f"🔌❌ Socket disconnected: participant {participant_id} from room {room_id} (cleaned up)")
                
        except Exception as e:
            logger.error(f"Error handling disconnection: {e}")
    
    @socketio.on('join_room')
    def on_join_room():
        """Explicit join room event (already handled in connect)"""
        try:
            from flask import session
            room_id = session.get('room_id')
            if room_id:
                emit('joined_room', {'room_id': room_id})
        except Exception as e:
            logger.error(f"Error handling join_room: {e}")
    
    @socketio.on('message_send')
    def on_message_send(data):
        """Handle incoming message"""
        try:
            from flask import session
            room_id = session.get('room_id')
            participant_id = session.get('participant_id')
            device_id = session.get('device_id')
            
            if not all([room_id, participant_id, device_id]):
                logger.warning("Message rejected: Missing session data")
                return
            
            # Validate device access
            if not Participant.validate_device_access(room_id, participant_id, device_id):
                logger.warning(f"Message rejected: Invalid device access")
                return
            
            # Validate room status
            room = Room.get_room(room_id)
            if not room or room['status'] not in ['active', 'locked']:
                logger.warning(f"Message rejected: Room {room_id} not available")
                emit('room_closed', {'reason': 'room_unavailable'})
                return
            
            # Extract message data
            if not data or 'ciphertext' not in data:
                logger.warning("Message rejected: Missing ciphertext")
                return
            
            try:
                # Data should contain base64-encoded ciphertext, nonce, tag
                ciphertext = base64.b64decode(data['ciphertext'])
                nonce = base64.b64decode(data['nonce'])
                tag = base64.b64decode(data['tag'])
            except Exception as e:
                logger.warning(f"Message rejected: Invalid encryption data - {e}")
                return
            
            msg_type = data.get('msg_type', 'text')
            attachment_id = data.get('attachment_id')
            
            # Get client IP
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            
            # Store encrypted message
            message = Message.create_message(
                room_id, participant_id, ciphertext, nonce, tag, msg_type, client_ip
            )
            
            if not message:
                logger.error("Failed to store message")
                emit('message_error', {'error': 'Failed to send message'})
                return
            
            # Link attachment if provided
            if attachment_id and msg_type == 'image':
                try:
                    query = """
                    UPDATE attachments 
                    SET message_id = %s
                    WHERE id = %s AND room_id = %s AND available = TRUE
                    """
                    db.execute(query, (message['id'], attachment_id, room_id))
                except Exception as e:
                    logger.error(f"Error linking attachment: {e}")
            
            # Get participant info for broadcast
            participant = Participant.get_participant(participant_id)
            
            # Prepare message for broadcast
            broadcast_data = {
                'message_id': message['id'],
                'room_id': room_id,
                'participant_id': participant_id,
                'display_name': participant['display_name'] if participant else 'Anonymous',
                'role': participant['role'] if participant else 'unknown',
                'ciphertext': data['ciphertext'],  # Keep as base64 for client
                'nonce': data['nonce'],
                'tag': data['tag'],
                'msg_type': msg_type,
                'attachment_id': attachment_id,
                'created_at': message['created_at']
            }
            
            # Broadcast to all clients in room
            emit('message', broadcast_data, room=room_id)
            logger.info(f"💬 Message sent in room {room_id} by {participant['display_name'] or 'Anonymous'} ({msg_type})")
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            emit('message_error', {'error': 'Internal server error'})
    
    @socketio.on('destroy_room')
    def on_destroy_room():
        """Handle room destruction"""
        try:
            from flask import session
            room_id = session.get('room_id')
            participant_id = session.get('participant_id')
            
            if not room_id:
                return
            
            # Close room
            if Room.close_room(room_id, reason='destroyed'):
                # Notify all clients in room
                emit('room_closed', {'reason': 'destroyed', 'message': 'Room has been destroyed'}, room=room_id)
                logger.info(f"💥 Room {room_id} destroyed by participant {participant_id} via socket")
            else:
                logger.error(f"Failed to destroy room {room_id} via socket")
                emit('error', {'message': 'Failed to destroy room'})
                
        except Exception as e:
            logger.error(f"Error handling room destruction: {e}")
    
    @socketio.on('ping')
    def on_ping():
        """Handle ping for keepalive"""
        emit('pong', {'timestamp': int(time.time() * 1000)})
    
    @socketio.on('announce_participant_name')
    def on_announce_participant_name(data):
        """Handle participant name announcement for verification"""
        try:
            from flask import session
            room_id = session.get('room_id')
            participant_id = session.get('participant_id')
            
            if not room_id or not participant_id:
                return
            
            display_name = data.get('display_name')
            role = data.get('role')
            
            if not display_name or not role:
                return
            
            # Broadcast to other participants in room (excluding sender)
            emit('participant_name_announced', {
                'display_name': display_name,
                'participant_id': participant_id,
                'role': role
            }, room=room_id, include_self=False)
            
            logger.info(f"👋 Participant {participant_id} ({role}) announced name '{display_name}' in room {room_id}")
            
        except Exception as e:
            logger.error(f"Error handling name announcement: {e}")
    
    @socketio.on('verify_participant')
    def on_verify_participant(data):
        """Handle participant verification response"""
        try:
            from flask import session
            room_id = session.get('room_id')
            verifier_id = session.get('participant_id')
            
            if not room_id or not verifier_id:
                return
            
            target_participant_id = data.get('target_participant_id')
            accepted = data.get('accepted')
            verifier_name = data.get('verifier_name')
            
            if target_participant_id is None or accepted is None:
                return
            
            if accepted:
                # Send verification success to all participants in room
                emit('participant_verified', {
                    'verifier_name': verifier_name,
                    'verifier_id': verifier_id,
                    'target_participant_id': target_participant_id
                }, room=room_id)
                
                logger.info(f"✅ Participant {verifier_id} verified participant {target_participant_id} in room {room_id}")
            else:
                # Send rejection to all participants
                emit('participant_rejected', {
                    'verifier_name': verifier_name,
                    'verifier_id': verifier_id,
                    'target_participant_id': target_participant_id
                }, room=room_id)
                
                logger.info(f"❌ Participant {verifier_id} rejected participant {target_participant_id} in room {room_id}")
                
                # Destroy room after rejection
                Room.close_room(room_id, reason='participant_rejected')
                emit('room_closed', {'reason': 'participant_rejected', 'message': 'Room closed due to participant rejection'}, room=room_id)
            
        except Exception as e:
            logger.error(f"Error handling participant verification: {e}")
    
    return socketio