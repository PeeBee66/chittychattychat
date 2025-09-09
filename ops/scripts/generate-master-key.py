#!/usr/bin/env python3
"""
Generate a master key for ChittyChattyChat encryption
"""

import secrets
import base64

def generate_master_key():
    """Generate a 32-byte master key and return as base64"""
    key_bytes = secrets.token_bytes(32)
    key_b64 = base64.b64encode(key_bytes).decode('utf-8')
    return key_b64

if __name__ == "__main__":
    key = generate_master_key()
    print("Generated master key:")
    print(key)
    print()
    print("Add this to your .env file:")
    print(f"MASTER_KEY={key}")
    print()
    print("⚠️  Keep this key secure! It's used to encrypt all room keys.")
    print("⚠️  If lost, all existing encrypted messages will be unrecoverable.")