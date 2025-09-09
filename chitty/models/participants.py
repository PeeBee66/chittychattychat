import uuid
from datetime import datetime
from typing import Optional, Dict, List
from .db import db
import logging
import psycopg2.extras
psycopg2.extras.register_uuid()

logger = logging.getLogger(__name__)

class Participant:
    @staticmethod
    def create_participant(room_id: str, role: str, device_id: str, ip_address: str) -> Optional[Dict]:
        """Create a new participant"""
        try:
            query = """
            INSERT INTO participants (room_id, role, device_id, ip_address, joined_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, room_id, role, device_id, joined_at
            """
            result = db.execute_one(query, (
                room_id, role, uuid.UUID(device_id), ip_address, datetime.utcnow()
            ))
            if result:
                return {
                    'id': result['id'],
                    'room_id': result['room_id'],
                    'role': result['role'],
                    'device_id': str(result['device_id']),
                    'joined_at': result['joined_at'].isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error creating participant: {e}")
            return None
    
    @staticmethod
    def get_participant(participant_id: int) -> Optional[Dict]:
        """Get participant by ID"""
        try:
            query = """
            SELECT id, room_id, role, device_id, display_name, ip_address, joined_at
            FROM participants 
            WHERE id = %s
            """
            result = db.execute_one(query, (participant_id,))
            if result:
                return {
                    'id': result['id'],
                    'room_id': result['room_id'],
                    'role': result['role'],
                    'device_id': str(result['device_id']),
                    'display_name': result['display_name'],
                    'ip_address': str(result['ip_address']) if result['ip_address'] else None,
                    'joined_at': result['joined_at'].isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error getting participant {participant_id}: {e}")
            return None
    
    @staticmethod
    def get_participant_by_device(room_id: str, device_id: str) -> Optional[Dict]:
        """Get participant by room and device ID"""
        try:
            query = """
            SELECT id, room_id, role, device_id, display_name, ip_address, joined_at
            FROM participants 
            WHERE room_id = %s AND device_id = %s
            """
            result = db.execute_one(query, (room_id, uuid.UUID(device_id)))
            if result:
                return {
                    'id': result['id'],
                    'room_id': result['room_id'],
                    'role': result['role'],
                    'device_id': str(result['device_id']),
                    'display_name': result['display_name'],
                    'ip_address': str(result['ip_address']) if result['ip_address'] else None,
                    'joined_at': result['joined_at'].isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error getting participant by device: {e}")
            return None
    
    @staticmethod
    def count_participants(room_id: str) -> int:
        """Count participants in a room"""
        try:
            query = "SELECT COUNT(*) as count FROM participants WHERE room_id = %s"
            result = db.execute_one(query, (room_id,))
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Error counting participants: {e}")
            return 0
    
    @staticmethod
    def remove_participant(participant_id: int) -> bool:
        """Remove a participant from the database"""
        try:
            query = "DELETE FROM participants WHERE id = %s"
            db.execute(query, (participant_id,))
            logger.info(f"🗑️ Participant {participant_id} removed from database")
            return True
        except Exception as e:
            logger.error(f"Error removing participant {participant_id}: {e}")
            return False
    
    @staticmethod
    def cleanup_inactive_participants(room_id: str, active_participant_ids: list) -> int:
        """Remove participants from room who are not in the active list"""
        try:
            if not active_participant_ids:
                # Remove all participants
                query = "DELETE FROM participants WHERE room_id = %s"
                result = db.execute(query, (room_id,))
            else:
                # Remove participants not in active list
                placeholders = ','.join(['%s'] * len(active_participant_ids))
                query = f"DELETE FROM participants WHERE room_id = %s AND id NOT IN ({placeholders})"
                result = db.execute(query, [room_id] + active_participant_ids)
            
            removed_count = getattr(result, 'rowcount', 0)
            if removed_count > 0:
                logger.info(f"🧹 Cleaned up {removed_count} inactive participants from room {room_id}")
            return removed_count
        except Exception as e:
            logger.error(f"Error cleaning up inactive participants: {e}")
            return 0
    
    @staticmethod
    def get_room_participants(room_id: str) -> List[Dict]:
        """Get all participants in a room"""
        try:
            query = """
            SELECT id, room_id, role, device_id, display_name, ip_address, joined_at
            FROM participants 
            WHERE room_id = %s
            ORDER BY joined_at
            """
            results = db.execute(query, (room_id,))
            participants = []
            if results:
                for row in results:
                    participants.append({
                        'id': row['id'],
                        'room_id': row['room_id'],
                        'role': row['role'],
                        'device_id': str(row['device_id']),
                        'display_name': row['display_name'],
                        'ip_address': str(row['ip_address']) if row['ip_address'] else None,
                        'joined_at': row['joined_at'].isoformat()
                    })
            return participants
        except Exception as e:
            logger.error(f"Error getting room participants: {e}")
            return []
    
    @staticmethod
    def set_display_name(participant_id: int, display_name: str) -> bool:
        """Set participant's display name"""
        try:
            query = """
            UPDATE participants 
            SET display_name = %s
            WHERE id = %s
            RETURNING id
            """
            result = db.execute_one(query, (display_name, participant_id))
            return result is not None
        except Exception as e:
            logger.error(f"Error setting display name: {e}")
            return False
    
    @staticmethod
    def validate_device_access(room_id: str, participant_id: int, device_id: str) -> bool:
        """Validate that device_id matches participant's device for room access"""
        try:
            query = """
            SELECT id FROM participants 
            WHERE room_id = %s AND id = %s AND device_id = %s
            """
            result = db.execute_one(query, (room_id, participant_id, uuid.UUID(device_id)))
            return result is not None
        except Exception as e:
            logger.error(f"Error validating device access: {e}")
            return False