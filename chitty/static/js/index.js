// Index page functionality
class IndexPage {
    constructor() {
        this.currentRoom = null;
        this.roomToken = null;
        this.init();
    }
    
    init() {
        this.bindEvents();
    }
    
    bindEvents() {
        // Host button
        const hostBtn = document.getElementById('hostBtn');
        if (hostBtn) {
            hostBtn.addEventListener('click', () => {
                window.chittyChat.showModal('hostModal');
                this.createRoom(); // Auto-create room when modal opens
            });
        }
        
        // Join button
        const joinBtn = document.getElementById('joinBtn');
        if (joinBtn) {
            joinBtn.addEventListener('click', () => {
                window.chittyChat.showModal('joinModal');
            });
        }
        
        // Accept room button
        const acceptRoomBtn = document.getElementById('acceptRoomBtn');
        if (acceptRoomBtn) {
            acceptRoomBtn.addEventListener('click', () => this.acceptRoom());
        }
        
        // Cancel room button
        const cancelRoomBtn = document.getElementById('cancelRoomBtn');
        if (cancelRoomBtn) {
            cancelRoomBtn.addEventListener('click', () => this.cancelRoom());
        }
        
        // Join room button
        const joinRoomBtn = document.getElementById('joinRoomBtn');
        if (joinRoomBtn) {
            joinRoomBtn.addEventListener('click', () => this.joinRoom());
        }
        
        // Room ID input
        const roomIdInput = document.getElementById('roomIdInput');
        if (roomIdInput) {
            // Don't convert to uppercase - room IDs are case-sensitive
            
            roomIdInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.joinRoom();
                }
            });
        }
    }
    
    async createRoom() {
        try {
            window.chittyChat.showLoading('Creating room...');
            
            const response = await window.chittyChat.makeRequest('/api/v1/rooms', {
                method: 'POST'
            });
            
            this.currentRoom = response.room_id;
            this.roomToken = response.room_token;
            
            // Update UI with room ID
            document.getElementById('roomIdDisplay').textContent = response.room_id;
            
        } catch (error) {
            console.error('Create room error:', error);
            window.chittyChat.showNotification('Failed to create room: ' + error.message, 'error');
            window.chittyChat.hideModal('hostModal');
        } finally {
            window.chittyChat.hideLoading();
        }
    }
    
    async acceptRoom() {
        try {
            if (!this.currentRoom || !this.roomToken) {
                throw new Error('No room to accept');
            }
            
            window.chittyChat.showLoading('Activating room...');
            
            const response = await window.chittyChat.makeRequest(`/api/v1/rooms/${this.currentRoom}/accept`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.roomToken}`
                }
            });
            
            if (response.success) {
                // Room activated successfully - go directly to the room
                window.chittyChat.showNotification('Room activated! Joining room...', 'success');
                window.chittyChat.hideModal('hostModal');
                
                // Store host token for the room (use updated token if provided)
                const tokenToStore = response.participant_token || this.roomToken;
                sessionStorage.setItem(`participant_token_${this.currentRoom}`, tokenToStore);
                sessionStorage.setItem(`role_${this.currentRoom}`, 'host');
                if (response.participant_id) {
                    sessionStorage.setItem(`participant_id_${this.currentRoom}`, response.participant_id);
                }
                if (response.room_key) {
                    sessionStorage.setItem(`room_key_${this.currentRoom}`, response.room_key);
                }
                
                // Navigate directly to room
                setTimeout(() => {
                    window.location.href = `/room/${this.currentRoom}`;
                }, 1000);
            }
            
        } catch (error) {
            console.error('Accept room error:', error);
            window.chittyChat.showNotification('Failed to activate room: ' + error.message, 'error');
        } finally {
            window.chittyChat.hideLoading();
        }
    }
    
    cancelRoom() {
        // Reset the modal
        this.currentRoom = null;
        this.roomToken = null;
        window.chittyChat.hideModal('hostModal');
    }
    
    async joinRoom() {
        try {
            const roomIdInput = document.getElementById('roomIdInput');
            const roomId = roomIdInput.value.trim();
            
            if (!roomId) {
                window.chittyChat.showNotification('Please enter a room ID', 'warning');
                return;
            }
            
            if (!window.chittyChat.validateRoomId(roomId)) {
                window.chittyChat.showNotification('Room ID must be 4 characters (A-Z, a-z, 0-9)', 'warning');
                return;
            }
            
            window.chittyChat.showLoading('Joining room...');
            
            const response = await window.chittyChat.makeRequest(`/api/v1/rooms/${roomId}/join`, {
                method: 'POST'
            });
            
            // Store participant token for the room
            sessionStorage.setItem(`participant_token_${roomId}`, response.participant_token);
            sessionStorage.setItem(`participant_id_${roomId}`, response.participant_id);
            sessionStorage.setItem(`role_${roomId}`, response.role);
            if (response.room_key) {
                sessionStorage.setItem(`room_key_${roomId}`, response.room_key);
            }
            
            // Navigate to room
            window.location.href = `/room/${roomId}`;
            
        } catch (error) {
            console.error('Join room error:', error);
            let errorMessage = error.message;
            
            if (errorMessage.includes('not found')) {
                errorMessage = 'Room not found. Please check the Room ID.';
            } else if (errorMessage.includes('expired')) {
                errorMessage = 'This room has expired.';
            } else if (errorMessage.includes('full')) {
                errorMessage = 'This room is full (2 participants maximum).';
            } else if (errorMessage.includes('not available')) {
                errorMessage = 'This room is not available for joining.';
            }
            
            window.chittyChat.showNotification(errorMessage, 'error');
        } finally {
            window.chittyChat.hideLoading();
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.indexPage = new IndexPage();
});