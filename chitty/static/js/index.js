// Index page functionality
class IndexPage {
    constructor() {
        this.currentRoom = null;
        this.roomToken = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.checkUrlParams();
    }

    bindEvents() {
        // Host button
        const hostBtn = document.getElementById('hostBtn');
        if (hostBtn) {
            hostBtn.addEventListener('click', () => {
                window.chittyChat.showModal('hostModal');
                // Don't create room yet - wait for Accept button
                this.resetHostModal();
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
            acceptRoomBtn.addEventListener('click', () => this.createAndAcceptRoom());
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
            roomIdInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.joinRoom();
                }
            });
        }

        // Copy room code button
        const copyRoomBtn = document.getElementById('copyRoomBtn');
        if (copyRoomBtn) {
            copyRoomBtn.addEventListener('click', () => this.copyRoomInfo());
        }
    }

    resetHostModal() {
        // Generate a temporary room ID for display (not created yet)
        const tempRoomId = this.generateTempRoomId();
        document.getElementById('roomIdDisplay').textContent = tempRoomId;
        document.getElementById('roomIdDisplay').setAttribute('data-temp-id', tempRoomId);

        // Show copy button
        const copyBtn = document.getElementById('copyRoomBtn');
        if (copyBtn) {
            copyBtn.style.display = 'inline-flex';
        }
    }

    generateTempRoomId() {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let result = '';
        for (let i = 0; i < 4; i++) {
            result += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return result;
    }

    async createAndAcceptRoom() {
        try {
            window.chittyChat.showLoading('Creating and activating room...');

            // Get the temporary room ID we displayed
            const tempRoomId = document.getElementById('roomIdDisplay').getAttribute('data-temp-id');

            // Create room with the specific ID
            const response = await window.chittyChat.makeRequest('/api/v1/rooms', {
                method: 'POST',
                body: JSON.stringify({
                    room_id: tempRoomId
                })
            });

            this.currentRoom = response.room_id;
            this.roomToken = response.room_token;

            // Immediately accept the room
            const acceptResponse = await window.chittyChat.makeRequest(`/api/v1/rooms/${this.currentRoom}/accept`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.roomToken}`
                }
            });

            if (acceptResponse.success) {
                // Room activated successfully
                window.chittyChat.showNotification('Room created and activated!', 'success');

                // Store host token for the room
                const tokenToStore = acceptResponse.participant_token || this.roomToken;
                sessionStorage.setItem(`participant_token_${this.currentRoom}`, tokenToStore);
                sessionStorage.setItem(`role_${this.currentRoom}`, 'host');
                if (acceptResponse.participant_id) {
                    sessionStorage.setItem(`participant_id_${this.currentRoom}`, acceptResponse.participant_id);
                }
                if (acceptResponse.room_key) {
                    sessionStorage.setItem(`room_key_${this.currentRoom}`, acceptResponse.room_key);
                }

                // Navigate to room
                setTimeout(() => {
                    window.location.href = `/room/${this.currentRoom}`;
                }, 1000);
            }

        } catch (error) {
            console.error('Create and accept room error:', error);
            window.chittyChat.showNotification('Failed to create room: ' + error.message, 'error');
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

    copyRoomInfo() {
        const roomId = document.getElementById('roomIdDisplay').textContent;
        const joinUrl = `${window.location.origin}/join/${roomId}`;

        // Create formatted text for copying
        const textToCopy = `Join my ChittyChattyChat room!\n\nRoom Code: ${roomId}\nDirect Link: ${joinUrl}`;

        // Copy to clipboard
        navigator.clipboard.writeText(textToCopy).then(() => {
            window.chittyChat.showNotification('Room info copied to clipboard!', 'success');

            // Visual feedback on button
            const copyBtn = document.getElementById('copyRoomBtn');
            if (copyBtn) {
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = '✅ Copied!';
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                }, 2000);
            }
        }).catch(() => {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = textToCopy;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            window.chittyChat.showNotification('Room info copied!', 'success');
        });
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

    checkUrlParams() {
        // Check if there's a room ID in the URL
        const urlParams = new URLSearchParams(window.location.search);
        const roomId = urlParams.get('room');

        if (roomId && window.chittyChat.validateRoomId(roomId)) {
            // Auto-fill the join modal and show it
            setTimeout(() => {
                document.getElementById('roomIdInput').value = roomId;
                window.chittyChat.showModal('joinModal');
            }, 500);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.indexPage = new IndexPage();
});