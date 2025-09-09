import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import secrets
import logging

logger = logging.getLogger(__name__)

class CryptoService:
    def __init__(self):
        self.master_key = self._get_master_key()
        
    def _get_master_key(self) -> bytes:
        """Get master key from environment"""
        master_key_b64 = os.getenv('MASTER_KEY')
        if not master_key_b64:
            raise ValueError("MASTER_KEY environment variable is required")
        try:
            key = base64.b64decode(master_key_b64)
            if len(key) != 32:
                raise ValueError("Master key must be 32 bytes")
            return key
        except Exception as e:
            raise ValueError(f"Invalid master key format: {e}")
    
    def generate_room_key(self) -> bytes:
        """Generate a new 32-byte room key"""
        return secrets.token_bytes(32)
    
    def encrypt_room_key(self, room_key: bytes) -> bytes:
        """Encrypt room key with master key (envelope encryption)"""
        try:
            aesgcm = AESGCM(self.master_key)
            nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
            ciphertext = aesgcm.encrypt(nonce, room_key, None)
            # Prepend nonce to ciphertext
            return nonce + ciphertext
        except Exception as e:
            logger.error(f"Error encrypting room key: {e}")
            raise
    
    def decrypt_room_key(self, encrypted_room_key: bytes) -> bytes:
        """Decrypt room key with master key"""
        try:
            nonce = encrypted_room_key[:12]  # First 12 bytes are nonce
            ciphertext = encrypted_room_key[12:]  # Rest is ciphertext
            aesgcm = AESGCM(self.master_key)
            room_key = aesgcm.decrypt(nonce, ciphertext, None)
            return room_key
        except Exception as e:
            logger.error(f"Error decrypting room key: {e}")
            raise
    
    def encrypt_message(self, room_key: bytes, plaintext: str) -> tuple[bytes, bytes, bytes]:
        """Encrypt a message with room key, returns (ciphertext, nonce, tag)"""
        try:
            aesgcm = AESGCM(room_key)
            nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            # For AES-GCM, the tag is included in the ciphertext
            # We'll extract it for separate storage
            actual_ciphertext = ciphertext[:-16]  # All but last 16 bytes
            tag = ciphertext[-16:]  # Last 16 bytes are the tag
            return actual_ciphertext, nonce, tag
        except Exception as e:
            logger.error(f"Error encrypting message: {e}")
            raise
    
    def decrypt_message(self, room_key: bytes, ciphertext: bytes, nonce: bytes, tag: bytes) -> str:
        """Decrypt a message with room key"""
        try:
            aesgcm = AESGCM(room_key)
            # Reconstruct full ciphertext with tag
            full_ciphertext = ciphertext + tag
            plaintext_bytes = aesgcm.decrypt(nonce, full_ciphertext, None)
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Error decrypting message: {e}")
            raise
    
    def generate_device_id(self) -> str:
        """Generate a UUID4 device ID"""
        import uuid
        return str(uuid.uuid4())

# Global crypto service instance
crypto_service = CryptoService()