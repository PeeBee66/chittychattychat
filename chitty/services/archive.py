import logging
from datetime import datetime
from typing import Dict, List
from models.rooms import Room
from models.messages import Message
from models.participants import Participant
from services.crypto import crypto_service
from services.storage import storage_service
from models.db import db

logger = logging.getLogger(__name__)

class ArchiveService:
    @staticmethod
    def archive_room(room_id: str) -> bool:
        """Archive a room's complete conversation"""
        try:
            # Get room info
            room = Room.get_room(room_id)
            if not room:
                logger.error(f"Room {room_id} not found for archiving")
                return False
            
            # Get participants
            participants = Participant.get_room_participants(room_id)
            
            # Get encrypted messages
            encrypted_messages = Message.get_room_messages(room_id, limit=10000)
            
            # Decrypt room key
            room_key_enc = ArchiveService._get_room_key(room_id)
            if not room_key_enc:
                logger.error(f"No room key found for {room_id}")
                return False
            
            room_key = crypto_service.decrypt_room_key(room_key_enc)
            
            # Decrypt messages
            decrypted_messages = []
            for msg in encrypted_messages:
                try:
                    decrypted_text = crypto_service.decrypt_message(
                        room_key, msg['body_ct'], msg['nonce'], msg['tag']
                    )
                    decrypted_messages.append({
                        'id': msg['id'],
                        'participant_id': msg['participant_id'],
                        'display_name': msg['display_name'],
                        'role': msg['role'],
                        'created_at': msg['created_at'],
                        'message': decrypted_text,
                        'msg_type': msg['msg_type'],
                        'ip_address': msg['ip_address']
                    })
                except Exception as e:
                    logger.error(f"Failed to decrypt message {msg['id']}: {e}")
                    # Include encrypted message for audit
                    decrypted_messages.append({
                        'id': msg['id'],
                        'participant_id': msg['participant_id'],
                        'display_name': msg['display_name'],
                        'role': msg['role'],
                        'created_at': msg['created_at'],
                        'message': '[DECRYPTION_FAILED]',
                        'msg_type': msg['msg_type'],
                        'ip_address': msg['ip_address'],
                        'error': str(e)
                    })
            
            # Create archive data
            archive_data = {
                'room': room,
                'participants': participants,
                'messages': decrypted_messages,
                'archived_at': datetime.utcnow().isoformat(),
                'message_count': len(decrypted_messages),
                'participant_count': len(participants)
            }
            
            # Generate archive key
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            archive_key = f"archives/{room_id}/{timestamp}.json"
            
            # Store in MinIO
            if storage_service.store_archive(archive_key, archive_data):
                # Update room with archive key
                if Room.archive_room(room_id, archive_key):
                    logger.info(f"Successfully archived room {room_id}")
                    return True
                else:
                    logger.error(f"Failed to mark room {room_id} as archived")
                    return False
            else:
                logger.error(f"Failed to store archive for room {room_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error archiving room {room_id}: {e}")
            return False
    
    @staticmethod
    def _get_room_key(room_id: str) -> bytes:
        """Get encrypted room key from database"""
        try:
            query = "SELECT room_key_enc FROM room_keys WHERE room_id = %s"
            result = db.execute_one(query, (room_id,))
            return bytes(result['room_key_enc']) if result else None
        except Exception as e:
            logger.error(f"Error getting room key: {e}")
            return None
    
    @staticmethod
    def get_archived_transcript(room_id: str) -> Dict:
        """Get archived transcript for admin view"""
        try:
            # Get room info
            room = Room.get_room(room_id)
            if not room or not room['archive_key']:
                return None
            
            # Get archive from MinIO
            archive_data = storage_service.get_archive(room['archive_key'])
            return archive_data
            
        except Exception as e:
            logger.error(f"Error getting archived transcript: {e}")
            return None
    
    @staticmethod
    def process_expired_rooms():
        """Process and archive expired rooms (background task)"""
        try:
            expired_rooms = Room.get_expired_rooms()
            for room_id in expired_rooms:
                logger.info(f"Processing expired room: {room_id}")
                
                # Close the room first
                if Room.close_room(room_id, reason='expired'):
                    # Archive the room
                    ArchiveService.archive_room(room_id)
                    
        except Exception as e:
            logger.error(f"Error processing expired rooms: {e}")

# Global archive service instance
archive_service = ArchiveService()