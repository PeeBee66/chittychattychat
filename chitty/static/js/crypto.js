// Client-side encryption utilities using Web Crypto API
class ChatCrypto {
    constructor() {
        this.roomKey = null;
        this.checkCryptoSupport();
    }
    
    // Check if Web Crypto API is available
    checkCryptoSupport() {
        if (!window.crypto || !window.crypto.subtle) {
            console.error('Web Crypto API not supported in this browser');
            console.error('Current context:', {
                isSecureContext: window.isSecureContext,
                protocol: window.location.protocol,
                hostname: window.location.hostname
            });
            throw new Error('Encryption not supported in this browser. HTTPS required for Web Crypto API.');
        }
    }
    
    // Generate a random room key
    async generateRoomKey() {
        return await window.crypto.getRandomValues(new Uint8Array(32));
    }
    
    // Set room key from base64 encoded string
    setRoomKeyFromBase64(base64Key) {
        this.roomKey = this.base64ToArrayBuffer(base64Key);
    }
    
    // Import room key for AES-GCM
    async importRoomKey(roomKeyBytes) {
        if (!roomKeyBytes) {
            throw new Error('Room key bytes is null or undefined');
        }
        
        if (!(roomKeyBytes instanceof ArrayBuffer) && !(roomKeyBytes instanceof Uint8Array)) {
            throw new Error('Room key must be ArrayBuffer or Uint8Array');
        }
        
        try {
            return await window.crypto.subtle.importKey(
                'raw',
                roomKeyBytes,
                { name: 'AES-GCM' },
                false,
                ['encrypt', 'decrypt']
            );
        } catch (error) {
            console.error('Failed to import room key:', error);
            console.error('Room key type:', typeof roomKeyBytes);
            console.error('Room key length:', roomKeyBytes.byteLength || roomKeyBytes.length);
            throw new Error('Failed to import encryption key');
        }
    }
    
    // Encrypt message with room key
    async encryptMessage(message, roomKeyBytes) {
        try {
            const encoder = new TextEncoder();
            const data = encoder.encode(message);
            
            // Generate random nonce
            const nonce = window.crypto.getRandomValues(new Uint8Array(12));
            
            // Import key
            const key = await this.importRoomKey(roomKeyBytes);
            
            // Encrypt
            const ciphertext = await window.crypto.subtle.encrypt(
                { name: 'AES-GCM', iv: nonce },
                key,
                data
            );
            
            // Split ciphertext and tag (last 16 bytes)
            const ciphertextArray = new Uint8Array(ciphertext);
            const actualCiphertext = ciphertextArray.slice(0, -16);
            const tag = ciphertextArray.slice(-16);
            
            return {
                ciphertext: this.arrayBufferToBase64(actualCiphertext),
                nonce: this.arrayBufferToBase64(nonce),
                tag: this.arrayBufferToBase64(tag)
            };
        } catch (error) {
            console.error('Encryption error:', error);
            throw new Error('Failed to encrypt message');
        }
    }
    
    // Decrypt message with room key
    async decryptMessage(encryptedData, roomKeyBytes) {
        try {
            const ciphertext = this.base64ToArrayBuffer(encryptedData.ciphertext);
            const nonce = this.base64ToArrayBuffer(encryptedData.nonce);
            const tag = this.base64ToArrayBuffer(encryptedData.tag);
            
            // Reconstruct full ciphertext with tag
            const fullCiphertext = new Uint8Array(ciphertext.byteLength + tag.byteLength);
            fullCiphertext.set(new Uint8Array(ciphertext), 0);
            fullCiphertext.set(new Uint8Array(tag), ciphertext.byteLength);
            
            // Import key
            const key = await this.importRoomKey(roomKeyBytes);
            
            // Decrypt
            const decrypted = await window.crypto.subtle.decrypt(
                { name: 'AES-GCM', iv: nonce },
                key,
                fullCiphertext
            );
            
            const decoder = new TextDecoder();
            return decoder.decode(decrypted);
        } catch (error) {
            console.error('Decryption error:', error);
            throw new Error('Failed to decrypt message');
        }
    }
    
    // Utility: Convert ArrayBuffer to base64
    arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
    }
    
    // Utility: Convert base64 to ArrayBuffer
    base64ToArrayBuffer(base64) {
        if (!base64) {
            throw new Error('Base64 string is null or undefined');
        }
        
        try {
            const binary = window.atob(base64);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            return bytes.buffer;
        } catch (error) {
            console.error('Failed to decode base64:', error);
            throw new Error('Invalid base64 string');
        }
    }
    
    // Generate a random device ID
    generateDeviceId() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
    
    // Get or create device ID
    getDeviceId() {
        let deviceId = localStorage.getItem('device_id');
        if (!deviceId) {
            deviceId = this.generateDeviceId();
            localStorage.setItem('device_id', deviceId);
        }
        return deviceId;
    }
}

// Global crypto instance
function initializeChatCrypto() {
    try {
        // Check if we're in a secure context first
        if (!window.isSecureContext && window.location.hostname !== 'localhost') {
            throw new Error('HTTPS required for encryption features');
        }
        
        window.chatCrypto = new ChatCrypto();
        console.log('ChatCrypto initialized successfully');
        return true;
    } catch (error) {
        console.error('Failed to initialize ChatCrypto:', error);
        console.error('This usually means HTTPS is required for encryption features');
        window.chatCrypto = null;
        return false;
    }
}

// Initialize when DOM is loaded to ensure proper timing
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeChatCrypto);
} else {
    initializeChatCrypto();
}