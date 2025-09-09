import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from .db import db
import logging

logger = logging.getLogger(__name__)

class Room:
    @staticmethod
    def generate_room_id() -> str:
        """Generate a 4-character room ID from A-Za-z0-9"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=4))
    
    @staticmethod
    def create_room() -> Dict:
        """Create a new room in pending state"""
        max_attempts = 10
        for _ in range(max_attempts):
            room_id = Room.generate_room_id()
            try:
                query = """
                INSERT INTO rooms (room_id, status, created_at)
                VALUES (%s, 'pending', %s)
                RETURNING room_id, created_at
                """
                result = db.execute_one(query, (room_id, datetime.utcnow()))
                if result:
                    return {
                        'room_id': result['room_id'],
                        'created_at': result['created_at'].isoformat(),
                        'status': 'pending'
                    }
            except Exception as e:
                if "duplicate key" in str(e).lower():
                    continue  # Try another room_id
                logger.error(f"Error creating room: {e}")
                raise
        
        raise Exception("Failed to generate unique room ID after multiple attempts")
    
    @staticmethod
    def accept_room(room_id: str) -> bool:
        """Accept a room and set it to active with 24h expiry"""
        try:
            expires_at = datetime.utcnow() + timedelta(hours=24)
            query = """
            UPDATE rooms 
            SET status = 'active', accepted_at = %s, expires_at = %s
            WHERE room_id = %s AND status = 'pending'
            RETURNING room_id
            """
            result = db.execute_one(query, (datetime.utcnow(), expires_at, room_id))
            return result is not None
        except Exception as e:
            logger.error(f"Error accepting room {room_id}: {e}")
            return False
    
    @staticmethod
    def get_room(room_id: str) -> Optional[Dict]:
        """Get room by ID"""
        try:
            query = """
            SELECT room_id, status, created_at, accepted_at, expires_at, closed_at, archive_key
            FROM rooms 
            WHERE room_id = %s
            """
            result = db.execute_one(query, (room_id,))
            if result:
                return {
                    'room_id': result['room_id'],
                    'status': result['status'],
                    'created_at': result['created_at'].isoformat() if result['created_at'] else None,
                    'accepted_at': result['accepted_at'].isoformat() if result['accepted_at'] else None,
                    'expires_at': result['expires_at'].isoformat() if result['expires_at'] else None,
                    'closed_at': result['closed_at'].isoformat() if result['closed_at'] else None,
                    'archive_key': result['archive_key']
                }
            return None
        except Exception as e:
            logger.error(f"Error getting room {room_id}: {e}")
            return None
    
    @staticmethod
    def close_room(room_id: str, reason: str = 'manual') -> bool:
        """Close a room and mark it for archiving"""
        try:
            query = """
            UPDATE rooms 
            SET status = 'closed', closed_at = %s
            WHERE room_id = %s AND status IN ('active', 'locked')
            RETURNING room_id
            """
            result = db.execute_one(query, (datetime.utcnow(), room_id))
            return result is not None
        except Exception as e:
            logger.error(f"Error closing room {room_id}: {e}")
            return False
    
    @staticmethod
    def lock_room(room_id: str) -> bool:
        """Lock a room when 2 participants join"""
        try:
            query = """
            UPDATE rooms 
            SET status = 'locked'
            WHERE room_id = %s AND status = 'active'
            RETURNING room_id
            """
            result = db.execute_one(query, (room_id,))
            return result is not None
        except Exception as e:
            logger.error(f"Error locking room {room_id}: {e}")
            return False
    
    @staticmethod
    def unlock_room(room_id: str) -> bool:
        """Unlock a room when participants leave"""
        try:
            query = """
            UPDATE rooms 
            SET status = 'active'
            WHERE room_id = %s AND status = 'locked'
            RETURNING room_id
            """
            result = db.execute_one(query, (room_id,))
            return result is not None
        except Exception as e:
            logger.error(f"Error unlocking room {room_id}: {e}")
            return False
    
    @staticmethod
    def get_expired_rooms() -> List[str]:
        """Get rooms that have expired"""
        try:
            query = """
            SELECT room_id 
            FROM rooms 
            WHERE status IN ('active', 'locked') 
            AND expires_at < %s
            """
            results = db.execute(query, (datetime.utcnow(),))
            return [row['room_id'] for row in results] if results else []
        except Exception as e:
            logger.error(f"Error getting expired rooms: {e}")
            return []
    
    @staticmethod
    def archive_room(room_id: str, archive_key: str) -> bool:
        """Mark room as archived with archive key"""
        try:
            query = """
            UPDATE rooms 
            SET status = 'archived', archive_key = %s
            WHERE room_id = %s AND status = 'closed'
            RETURNING room_id
            """
            result = db.execute_one(query, (archive_key, room_id))
            return result is not None
        except Exception as e:
            logger.error(f"Error archiving room {room_id}: {e}")
            return False