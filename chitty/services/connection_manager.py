"""
Simple connection manager to track active WebSocket connections
"""
import logging
from typing import Dict, Set
from threading import Lock

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active WebSocket connections"""
    
    def __init__(self):
        self._connections: Dict[str, Dict[int, str]] = {}  # room_id -> {participant_id: session_id}
        self._sessions: Dict[str, Dict] = {}  # session_id -> {room_id, participant_id, role}
        self._lock = Lock()
    
    def add_connection(self, session_id: str, room_id: str, participant_id: int, role: str):
        """Add a connection"""
        with self._lock:
            # Add to room connections
            if room_id not in self._connections:
                self._connections[room_id] = {}
            self._connections[room_id][participant_id] = session_id
            
            # Add session info
            self._sessions[session_id] = {
                'room_id': room_id,
                'participant_id': participant_id,
                'role': role
            }
            
            logger.info(f"📡 Connection added: {role} participant {participant_id} in room {room_id}")
    
    def remove_connection(self, session_id: str):
        """Remove a connection"""
        with self._lock:
            if session_id in self._sessions:
                session_info = self._sessions[session_id]
                room_id = session_info['room_id']
                participant_id = session_info['participant_id']
                role = session_info['role']
                
                # Remove from room connections
                if room_id in self._connections:
                    self._connections[room_id].pop(participant_id, None)
                    if not self._connections[room_id]:  # Empty room
                        del self._connections[room_id]
                
                # Remove session
                del self._sessions[session_id]
                
                logger.info(f"📡 Connection removed: {role} participant {participant_id} from room {room_id}")
                return session_info
        return None
    
    def get_room_connections(self, room_id: str) -> Dict[int, str]:
        """Get all connections for a room"""
        with self._lock:
            return self._connections.get(room_id, {}).copy()
    
    def get_connection_count(self, room_id: str) -> int:
        """Get count of connected participants in a room"""
        with self._lock:
            return len(self._connections.get(room_id, {}))
    
    def is_participant_connected(self, room_id: str, participant_id: int) -> bool:
        """Check if a participant is connected"""
        with self._lock:
            return participant_id in self._connections.get(room_id, {})

# Global instance
connection_manager = ConnectionManager()