// Chat page functionality
class ChatPage {
    constructor() {
        this.roomId = window.ROOM_ID;
        this.socket = null;
        this.participantToken = null;
        this.participantId = null;
        this.role = null;
        this.roomKey = null;
        this.displayName = null;
        this.selectedFile = null;
        this.timerInterval = null;
        this.messages = new Map();
        
        this.init();
    }
    
    async init() {
        // Check if crypto is available
        if (!window.chatCrypto) {
            window.chittyChat.showNotification('Encryption service unavailable. This app requires HTTPS for security.', 'error');
            setTimeout(() => {
                window.location.href = '/';
            }, 5000);
            return;
        }
        
        this.loadSessionData();
        this.bindEvents();
        this.setupSessionCleanup();
        this.connectSocket();
        
        // Check if participant already has a display name
        await this.checkExistingDisplayName();
    }
    
    setupSessionCleanup() {
        // Clean up session when browser closes or tab is refreshed
        window.addEventListener('beforeunload', (e) => {
            // Clean up session storage for this room
            if (this.roomId) {
                console.log('🧹 Cleaning up session on browser close');
                sessionStorage.removeItem(`participant_token_${this.roomId}`);
                sessionStorage.removeItem(`participant_id_${this.roomId}`);
                sessionStorage.removeItem(`role_${this.roomId}`);
                sessionStorage.removeItem(`room_key_${this.roomId}`);
            }
            
            // Disconnect socket gracefully
            if (this.socket) {
                this.socket.disconnect();
            }
        });
        
        // Handle visibility change (tab switching)
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                console.log('🌙 Tab hidden - maintaining connection');
            } else {
                console.log('🌞 Tab visible - checking connection');
                // Reconnect if needed
                if (this.socket && !this.socket.connected) {
                    console.log('🔄 Reconnecting socket...');
                    this.connectSocket();
                }
            }
        });
    }
    
    loadSessionData() {
        this.participantToken = sessionStorage.getItem(`participant_token_${this.roomId}`);
        this.participantId = sessionStorage.getItem(`participant_id_${this.roomId}`);
        this.role = sessionStorage.getItem(`role_${this.roomId}`);
        
        // Load room key if available
        const roomKeyB64 = sessionStorage.getItem(`room_key_${this.roomId}`);
        if (roomKeyB64) {
            try {
                if (!window.chatCrypto) {
                    throw new Error('Encryption service not available');
                }
                this.roomKey = window.chatCrypto.base64ToArrayBuffer(roomKeyB64);
                console.log('Room key loaded successfully, length:', this.roomKey.byteLength);
            } catch (error) {
                console.error('Failed to load room key from session storage:', error);
                this.roomKey = null;
            }
        } else {
            console.warn('No room key found in session storage for room:', this.roomId);
        }
        
        if (!this.participantToken) {
            window.chittyChat.showNotification('No valid session found. Redirecting...', 'error');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
            return;
        }
    }
    
    async checkExistingDisplayName() {
        try {
            // Get room info to check if participant already has a display name
            const response = await window.chittyChat.makeRequest(`/api/v1/rooms/${this.roomId}`, {
                headers: {
                    'Authorization': `Bearer ${this.participantToken}`
                }
            });
            
            // Find current participant
            const currentParticipant = response.participants.find(p => p.id == this.participantId);
            
            if (currentParticipant && currentParticipant.display_name) {
                // Already has a display name
                this.displayName = currentParticipant.display_name;
                
                // Hide name modal
                const nameModal = document.getElementById('nameModal');
                if (nameModal) {
                    nameModal.classList.remove('show');
                    document.body.style.overflow = '';
                }
                
                // Enable message input
                const messageInput = document.getElementById('messageInput');
                const sendBtn = document.getElementById('sendBtn');
                if (messageInput) messageInput.disabled = false;
                if (sendBtn) sendBtn.disabled = false;
                
                window.chittyChat.showNotification(`Welcome back, ${this.displayName}!`, 'success');
            } else {
                // No display name yet, show name selection
                this.loadNames();
            }
        } catch (error) {
            console.error('Failed to check existing display name:', error);
            // Fall back to name selection
            this.loadNames();
        }
    }
    
    bindEvents() {
        // Message input
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            messageInput.addEventListener('input', () => {
                this.autoResizeTextarea(messageInput);
            });
        }
        
        // Send button
        const sendBtn = document.getElementById('sendBtn');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendMessage());
        }
        
        // Attach button
        const attachBtn = document.getElementById('attachBtn');
        if (attachBtn) {
            attachBtn.addEventListener('click', () => {
                document.getElementById('fileInput').click();
            });
        }
        
        // File input
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
        }
        
        // Cancel upload
        const cancelUpload = document.getElementById('cancelUpload');
        if (cancelUpload) {
            cancelUpload.addEventListener('click', () => this.cancelFileUpload());
        }
        
        // Destroy button
        const destroyBtn = document.getElementById('destroyBtn');
        if (destroyBtn) {
            destroyBtn.addEventListener('click', () => this.showDestroyConfirmation());
        }
        
        // Name selection
        this.bindNameSelection();
        
        // Verification modal  
        this.bindVerificationModal();
        
        // Confirmation modal
        this.bindConfirmationModal();
    }
    
    bindNameSelection() {
        const confirmNameBtn = document.getElementById('confirmNameBtn');
        if (confirmNameBtn) {
            confirmNameBtn.addEventListener('click', () => this.confirmNameSelection());
        }
    }
    
    bindVerificationModal() {
        const verifyYes = document.getElementById('verifyYes');
        const verifyNo = document.getElementById('verifyNo');
        
        if (verifyYes) {
            verifyYes.addEventListener('click', () => this.verifyParticipant(true));
        }
        
        if (verifyNo) {
            verifyNo.addEventListener('click', () => this.verifyParticipant(false));
        }
    }
    
    bindConfirmationModal() {
        const confirmYes = document.getElementById('confirmYes');
        const confirmNo = document.getElementById('confirmNo');
        
        if (confirmYes) {
            confirmYes.addEventListener('click', () => {
                window.chittyChat.hideModal('confirmModal');
                if (this.pendingAction) {
                    this.pendingAction();
                    this.pendingAction = null;
                }
            });
        }
        
        if (confirmNo) {
            confirmNo.addEventListener('click', () => {
                window.chittyChat.hideModal('confirmModal');
                this.pendingAction = null;
            });
        }
    }
    
    async loadNames() {
        try {
            const response = await window.chittyChat.makeRequest('/api/v1/names/suggest', {
                headers: {
                    'Authorization': `Bearer ${this.participantToken}`
                }
            });
            this.displayNameOptions(response.names);
        } catch (error) {
            console.error('Failed to load names:', error);
            window.chittyChat.showNotification('Failed to load name options', 'error');
        }
    }
    
    displayNameOptions(names) {
        const nameOptions = document.getElementById('nameOptions');
        if (!nameOptions) return;
        
        nameOptions.innerHTML = '';
        
        names.forEach(name => {
            const option = document.createElement('div');
            option.className = 'name-option';
            option.textContent = name;
            option.addEventListener('click', () => {
                // Remove selection from others
                document.querySelectorAll('.name-option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                // Select this one
                option.classList.add('selected');
                this.selectedName = name;
                
                // Enable confirm button
                const confirmBtn = document.getElementById('confirmNameBtn');
                if (confirmBtn) {
                    confirmBtn.disabled = false;
                }
            });
            nameOptions.appendChild(option);
        });
    }
    
    async confirmNameSelection() {
        if (!this.selectedName) return;
        
        try {
            window.chittyChat.showLoading('Setting display name...');
            
            const response = await window.chittyChat.makeRequest(`/api/v1/rooms/${this.roomId}/name`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.participantToken}`
                },
                body: JSON.stringify({
                    display_name: this.selectedName
                })
            });
            
            if (response.success) {
                this.displayName = this.selectedName;
                
                // Force close the modal even if it's required
                const nameModal = document.getElementById('nameModal');
                if (nameModal) {
                    nameModal.classList.remove('show');
                    document.body.style.overflow = '';
                }
                
                // Enable message input
                const messageInput = document.getElementById('messageInput');
                const sendBtn = document.getElementById('sendBtn');
                if (messageInput) messageInput.disabled = false;
                if (sendBtn) sendBtn.disabled = false;
                
                // Focus message input
                if (messageInput) messageInput.focus();
                
                // Announce name to other participants for verification
                if (this.socket) {
                    this.socket.emit('announce_participant_name', {
                        display_name: this.displayName,
                        participant_id: this.participantId,
                        role: this.role
                    });
                }
                
                window.chittyChat.showNotification(`Welcome, ${this.displayName}!`, 'success');
            }
            
        } catch (error) {
            console.error('Failed to set display name:', error);
            window.chittyChat.showNotification('Failed to set display name: ' + error.message, 'error');
        } finally {
            window.chittyChat.hideLoading();
        }
    }
    
    connectSocket() {
        if (!this.participantToken) return;
        
        this.socket = io({
            auth: {
                token: this.participantToken
            }
        });
        
        this.socket.on('connect', () => {
            console.log('Connected to chat server');
            this.updateRoomStatus('Connected');
            
            // Show name selection modal if no display name
            if (!this.displayName) {
                window.chittyChat.showModal('nameModal');
            }
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from chat server');
            this.updateRoomStatus('Disconnected');
            window.chittyChat.showNotification('Connection lost. Trying to reconnect...', 'warning');
        });
        
        this.socket.on('room_locked', (data) => {
            this.updateRoomStatus('🔒 Room Locked');
            window.chittyChat.showNotification('Room is now locked to 2 participants', 'success');
        });
        
        this.socket.on('timer_update', (data) => {
            this.startTimer(data.time_left_seconds);
        });
        
        this.socket.on('message', (data) => {
            this.handleIncomingMessage(data);
        });
        
        this.socket.on('room_closed', (data) => {
            this.handleRoomClosed(data);
        });
        
        this.socket.on('message_error', (data) => {
            window.chittyChat.showNotification('Message failed: ' + data.error, 'error');
        });
        
        this.socket.on('error', (error) => {
            console.error('Socket error:', error);
            window.chittyChat.showNotification('Connection error: ' + error, 'error');
        });
        
        // Participant verification events
        this.socket.on('participant_name_announced', (data) => {
            this.handleParticipantNameAnnouncement(data);
        });
        
        this.socket.on('participant_verified', (data) => {
            this.handleParticipantVerified(data);
        });
        
        this.socket.on('participant_rejected', (data) => {
            this.handleParticipantRejected(data);
        });
        
        // Connection status events
        this.socket.on('participant_connected', (data) => {
            this.handleParticipantConnected(data);
        });
        
        this.socket.on('participant_disconnected', (data) => {
            this.handleParticipantDisconnected(data);
        });
        
        this.socket.on('connection_status_update', (data) => {
            this.updateConnectionStatus(data);
        });
    }
    
    updateRoomStatus(status) {
        const statusEl = document.getElementById('roomStatus');
        if (statusEl) {
            statusEl.textContent = status;
        }
    }
    
    startTimer(seconds) {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        let timeLeft = seconds;
        
        const updateTimer = () => {
            const timerEl = document.getElementById('timer');
            if (timerEl) {
                timerEl.textContent = window.chittyChat.formatTime(timeLeft);
            }
            
            if (timeLeft <= 0) {
                clearInterval(this.timerInterval);
                return;
            }
            
            timeLeft--;
        };
        
        updateTimer(); // Initial update
        this.timerInterval = setInterval(updateTimer, 1000);
    }
    
    async sendMessage() {
        const messageInput = document.getElementById('messageInput');
        if (!messageInput || !this.socket || !this.roomKey) {
            console.error('Cannot send message - missing requirements:', {
                messageInput: !!messageInput,
                socket: !!this.socket,
                roomKey: !!this.roomKey,
                roomKeyType: typeof this.roomKey,
                roomKeyLength: this.roomKey ? this.roomKey.byteLength : 'N/A'
            });
            return;
        }
        
        const message = messageInput.value.trim();
        if (!message && !this.selectedFile) return;
        
        try {
            let messageData = {};
            
            if (this.selectedFile) {
                // Handle file upload
                messageData = await this.handleFileUpload(message || '📎 Image');
            } else {
                // Handle text message
                if (!window.chatCrypto) {
                    throw new Error('Encryption service not available. Please refresh the page.');
                }
                
                console.log('Encrypting message with room key:', this.roomKey.byteLength, 'bytes');
                const encrypted = await window.chatCrypto.encryptMessage(message, this.roomKey);
                messageData = {
                    ciphertext: encrypted.ciphertext,
                    nonce: encrypted.nonce,
                    tag: encrypted.tag,
                    msg_type: 'text'
                };
            }
            
            // Send via socket
            this.socket.emit('message_send', messageData);
            
            // Clear input
            messageInput.value = '';
            this.autoResizeTextarea(messageInput);
            
            // Clear file if any
            this.cancelFileUpload();
            
        } catch (error) {
            console.error('Send message error:', error);
            window.chittyChat.showNotification('Failed to send message: ' + error.message, 'error');
        }
    }
    
    async handleFileUpload(caption) {
        if (!this.selectedFile) return null;
        
        try {
            window.chittyChat.showLoading('Uploading image...');
            
            // Initialize upload
            const initResponse = await window.chittyChat.makeRequest('/api/v1/uploads/init', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.participantToken}`
                },
                body: JSON.stringify({
                    filename: this.selectedFile.name,
                    file_size: this.selectedFile.size,
                    mime_type: this.selectedFile.type
                })
            });
            
            // Upload file to MinIO
            const uploadResponse = await fetch(initResponse.upload_url, {
                method: 'PUT',
                body: this.selectedFile,
                headers: {
                    'Content-Type': this.selectedFile.type
                }
            });
            
            if (!uploadResponse.ok) {
                throw new Error('File upload failed');
            }
            
            // Complete upload
            await window.chittyChat.makeRequest('/api/v1/uploads/complete', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.participantToken}`
                },
                body: JSON.stringify({
                    attachment_id: initResponse.attachment_id
                })
            });
            
            // Encrypt caption
            if (!window.chatCrypto) {
                throw new Error('Encryption service not available. Please refresh the page.');
            }
            const encrypted = await window.chatCrypto.encryptMessage(caption, this.roomKey);
            
            return {
                ciphertext: encrypted.ciphertext,
                nonce: encrypted.nonce,
                tag: encrypted.tag,
                msg_type: 'image',
                attachment_id: initResponse.attachment_id
            };
            
        } catch (error) {
            console.error('File upload error:', error);
            throw error;
        } finally {
            window.chittyChat.hideLoading();
        }
    }
    
    handleFileSelection(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        // Validate file
        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
        if (!allowedTypes.includes(file.type)) {
            window.chittyChat.showNotification('Only image files are allowed', 'warning');
            return;
        }
        
        if (file.size > 10 * 1024 * 1024) {
            window.chittyChat.showNotification('File too large. Maximum size is 10MB', 'warning');
            return;
        }
        
        this.selectedFile = file;
        this.showFilePreview(file);
    }
    
    showFilePreview(file) {
        const uploadArea = document.getElementById('uploadArea');
        const preview = document.getElementById('uploadPreview');
        const fileName = document.getElementById('uploadFileName');
        
        if (!uploadArea || !preview || !fileName) return;
        
        // Show preview
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.src = e.target.result;
            fileName.textContent = file.name;
            uploadArea.style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
    
    cancelFileUpload() {
        this.selectedFile = null;
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        
        if (uploadArea) uploadArea.style.display = 'none';
        if (fileInput) fileInput.value = '';
    }
    
    async handleIncomingMessage(data) {
        try {
            // Check if chatCrypto is available
            if (!window.chatCrypto) {
                throw new Error('Encryption service not available');
            }
            
            // Decrypt message
            const decrypted = await window.chatCrypto.decryptMessage({
                ciphertext: data.ciphertext,
                nonce: data.nonce,
                tag: data.tag
            }, this.roomKey);
            
            // Add to messages
            const messageElement = this.createMessageElement({
                id: data.message_id,
                text: decrypted,
                sender: data.display_name || 'Anonymous',
                timestamp: new Date(data.created_at),
                isOwn: data.participant_id === parseInt(this.participantId),
                type: data.msg_type,
                attachmentId: data.attachment_id
            });
            
            this.addMessageToChat(messageElement);
            
        } catch (error) {
            console.error('Failed to decrypt message:', error);
            // Show encrypted message placeholder
            const messageElement = this.createMessageElement({
                id: data.message_id,
                text: '[Unable to decrypt message]',
                sender: data.display_name || 'Anonymous',
                timestamp: new Date(data.created_at),
                isOwn: data.participant_id === parseInt(this.participantId),
                type: 'text',
                error: true
            });
            
            this.addMessageToChat(messageElement);
        }
    }
    
    createMessageElement(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.isOwn ? 'own' : 'other'}`;
        messageDiv.id = `message-${message.id}`;
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        
        if (message.type === 'image' && message.attachmentId && !message.error) {
            // Create image message
            const textDiv = document.createElement('div');
            textDiv.textContent = message.text;
            bubble.appendChild(textDiv);
            
            const img = document.createElement('img');
            img.className = 'message-image';
            img.alt = 'Shared image';
            img.style.maxWidth = '100%';
            img.style.borderRadius = '10px';
            img.style.marginTop = '10px';
            
            // Load image via attachment URL
            this.loadAttachmentImage(img, message.attachmentId);
            
            bubble.appendChild(img);
        } else {
            // Text message
            bubble.textContent = message.text;
            if (message.error) {
                bubble.style.fontStyle = 'italic';
                bubble.style.opacity = '0.7';
            }
        }
        
        const meta = document.createElement('div');
        meta.className = 'message-meta';
        
        const sender = document.createElement('span');
        sender.textContent = message.sender;
        
        const timestamp = document.createElement('span');
        timestamp.textContent = this.formatTimestamp(message.timestamp);
        
        meta.appendChild(sender);
        meta.appendChild(timestamp);
        
        messageDiv.appendChild(bubble);
        messageDiv.appendChild(meta);
        
        return messageDiv;
    }
    
    async loadAttachmentImage(imgElement, attachmentId) {
        try {
            const response = await window.chittyChat.makeRequest(`/api/v1/uploads/${attachmentId}/url`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.participantToken}`
                }
            });
            
            imgElement.src = response.download_url;
        } catch (error) {
            console.error('Failed to load attachment:', error);
            imgElement.alt = 'Failed to load image';
        }
    }
    
    addMessageToChat(messageElement) {
        const messagesList = document.getElementById('messagesList');
        if (!messagesList) return;
        
        messagesList.appendChild(messageElement);
        
        // Scroll to bottom
        const container = document.getElementById('messagesContainer');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }
    
    formatTimestamp(date) {
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    }
    
    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 100) + 'px';
    }
    
    showDestroyConfirmation() {
        document.getElementById('confirmTitle').textContent = 'Destroy Chat Room';
        document.getElementById('confirmMessage').textContent = 
            'Are you sure you want to destroy this chat room? This action cannot be undone and will end the conversation for both participants.';
        
        this.pendingAction = () => this.destroyRoom();
        window.chittyChat.showModal('confirmModal');
    }
    
    destroyRoom() {
        if (this.socket) {
            this.socket.emit('destroy_room');
        }
    }
    
    handleRoomClosed(data) {
        const reason = data.reason || 'unknown';
        let message = 'The chat room has been closed.';
        
        if (reason === 'destroyed') {
            message = 'The chat room has been destroyed.';
        } else if (reason === 'expired') {
            message = 'The chat room has expired after 24 hours.';
        }
        
        // Clear timer
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        // Show notification and redirect
        window.chittyChat.showNotification(message, 'info');
        
        setTimeout(() => {
            window.location.href = '/';
        }, 3000);
    }
    
    // Set room key (called externally)
    setRoomKey(roomKeyBytes) {
        this.roomKey = roomKeyBytes;
    }
    
    // Handle participant name announcement for verification
    handleParticipantNameAnnouncement(data) {
        const { display_name, participant_id, role } = data;
        
        // Don't verify ourselves
        if (participant_id == this.participantId) return;
        
        // Show verification modal
        const verificationName = document.getElementById('verificationName');
        const verificationMessage = document.getElementById('verificationMessage');
        const verificationModal = document.getElementById('verificationModal');
        
        if (verificationName && verificationMessage && verificationModal) {
            verificationName.textContent = display_name;
            verificationMessage.textContent = `The ${role} joined the room with the name:`;
            verificationModal.classList.add('show');
            document.body.style.overflow = 'hidden';
            
            // Store the participant data for verification response
            this.pendingVerification = { participant_id, display_name, role };
        }
    }
    
    // Handle verification response
    verifyParticipant(accepted) {
        if (!this.pendingVerification) return;
        
        const verificationModal = document.getElementById('verificationModal');
        if (verificationModal) {
            verificationModal.classList.remove('show');
            document.body.style.overflow = '';
        }
        
        // Send verification response via socket
        if (this.socket) {
            this.socket.emit('verify_participant', {
                target_participant_id: this.pendingVerification.participant_id,
                accepted: accepted,
                verifier_name: this.displayName
            });
        }
        
        if (accepted) {
            window.chittyChat.showNotification(`You verified ${this.pendingVerification.display_name}`, 'success');
        } else {
            window.chittyChat.showNotification(`You rejected ${this.pendingVerification.display_name}`, 'warning');
        }
        
        this.pendingVerification = null;
    }
    
    // Handle when someone verifies this participant
    handleParticipantVerified(data) {
        const { verifier_name, target_participant_id } = data;
        
        // Only show notification if we are the target
        if (target_participant_id == this.participantId) {
            window.chittyChat.showNotification(`${verifier_name} verified your identity`, 'success');
        }
    }
    
    // Handle when someone rejects this participant
    handleParticipantConnected(data) {
        const { participant_id, role, display_name } = data;
        console.log(`Participant connected: ${role} (${display_name || 'No name yet'})`);
        
        if (display_name) {
            window.chittyChat.showNotification(`${display_name} joined the chat`, 'info');
        }
    }
    
    handleParticipantDisconnected(data) {
        const { participant_id, role, display_name } = data;
        console.log(`Participant disconnected: ${role} (${display_name || 'Unknown'})`);
        
        if (display_name && participant_id != this.participantId) {
            window.chittyChat.showNotification(`${display_name} left the chat`, 'warning');
        }
    }
    
    updateConnectionStatus(data) {
        const { connected_participants, total_participants, is_secure, participants } = data;
        
        // Update security status
        const lockIcon = document.getElementById('lockIcon');
        const securityText = document.getElementById('securityText');
        
        if (lockIcon && securityText) {
            if (is_secure) {
                lockIcon.textContent = '🔒';
                lockIcon.classList.add('secure');
                securityText.textContent = 'Secure chat active';
                securityText.classList.add('secure');
            } else {
                lockIcon.textContent = '🔓';
                lockIcon.classList.remove('secure');
                securityText.textContent = `Waiting for participants... (${connected_participants}/${total_participants})`;
                securityText.classList.remove('secure');
            }
        }
        
        // Update participant dots
        const participant1Dot = document.querySelector('#participant1 .participant-dot');
        const participant2Dot = document.querySelector('#participant2 .participant-dot');
        const participant1Label = document.querySelector('#participant1 .participant-label');
        const participant2Label = document.querySelector('#participant2 .participant-label');
        
        // Reset all dots to offline
        if (participant1Dot) {
            participant1Dot.className = 'participant-dot offline';
        }
        if (participant2Dot) {
            participant2Dot.className = 'participant-dot offline';
        }
        
        // Update participant labels and status based on data
        let hostParticipant = participants.find(p => p.role === 'host');
        let guestParticipant = participants.find(p => p.role === 'guest');
        
        if (hostParticipant) {
            if (participant1Label) {
                participant1Label.textContent = hostParticipant.display_name || 'Host';
            }
            if (participant1Dot && hostParticipant.is_connected) {
                participant1Dot.className = 'participant-dot online';
            }
        }
        
        if (guestParticipant) {
            if (participant2Label) {
                participant2Label.textContent = guestParticipant.display_name || 'Guest';
            }
            if (participant2Dot && guestParticipant.is_connected) {
                participant2Dot.className = 'participant-dot online';
            }
        }
        
        console.log(`Connection status: ${connected_participants}/${total_participants} participants, secure: ${is_secure}`);
    }
    
    handleParticipantRejected(data) {
        const { verifier_name, target_participant_id } = data;
        
        // Only show notification if we are the target
        if (target_participant_id == this.participantId) {
            window.chittyChat.showNotification(`${verifier_name} rejected your identity. The room will be destroyed.`, 'error');
            
            // Auto-destroy room after rejection
            setTimeout(() => {
                this.destroyRoom();
            }, 3000);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.chatPage = new ChatPage();
    
    // Room key should be loaded from session storage
    // If not available (shouldn't happen), generate a fallback
    if (!window.chatPage.roomKey) {
        console.warn('No room key found in session, generating fallback key');
        const roomKey = window.crypto.getRandomValues(new Uint8Array(32));
        window.chatPage.setRoomKey(roomKey);
    }
});