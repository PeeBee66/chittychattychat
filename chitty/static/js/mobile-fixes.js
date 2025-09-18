// Mobile-specific JavaScript fixes
(function() {
    'use strict';

    // Detect mobile devices
    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);

    // Fix viewport height on mobile browsers
    function setViewportHeight() {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }

    // Call on load and resize
    setViewportHeight();
    window.addEventListener('resize', setViewportHeight);
    window.addEventListener('orientationchange', setViewportHeight);

    // Prevent zoom on input focus for iOS
    if (isIOS) {
        document.addEventListener('DOMContentLoaded', function() {
            const inputs = document.querySelectorAll('input[type="text"], input[type="password"], textarea, select');
            inputs.forEach(input => {
                input.style.fontSize = '16px';
            });
        });
    }

    // Handle input focus to prevent keyboard issues
    if (isMobile) {
        document.addEventListener('DOMContentLoaded', function() {
            const messageInput = document.getElementById('messageInput');
            const messagesContainer = document.querySelector('.messages-container');

            if (messageInput) {
                // Store original height
                let originalHeight = null;

                messageInput.addEventListener('focus', function() {
                    if (isIOS) {
                        // Store current scroll position
                        originalHeight = window.innerHeight;

                        // Delay to let keyboard appear
                        setTimeout(() => {
                            // Scroll input into view
                            messageInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }, 300);
                    }
                });

                messageInput.addEventListener('blur', function() {
                    if (isIOS) {
                        // Restore scroll position
                        window.scrollTo(0, 0);
                    }
                });

                // Auto-resize textarea
                messageInput.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = Math.min(this.scrollHeight, 120) + 'px';

                    // Keep messages scrolled to bottom
                    if (messagesContainer) {
                        const messagesList = messagesContainer.querySelector('.messages-list');
                        if (messagesList) {
                            messagesList.scrollTop = messagesList.scrollHeight;
                        }
                    }
                });
            }

            // Fix button tap delays
            const buttons = document.querySelectorAll('.btn');
            buttons.forEach(button => {
                button.addEventListener('touchstart', function() {
                    this.classList.add('touch-active');
                });
                button.addEventListener('touchend', function() {
                    this.classList.remove('touch-active');
                });
            });
        });
    }

    // Smooth scroll for messages
    document.addEventListener('DOMContentLoaded', function() {
        const messagesList = document.querySelector('.messages-list');
        if (messagesList) {
            // Smooth scroll to bottom when new message added
            const scrollToBottom = () => {
                messagesList.scrollTo({
                    top: messagesList.scrollHeight,
                    behavior: 'smooth'
                });
            };

            // Observer for new messages
            const observer = new MutationObserver(scrollToBottom);
            observer.observe(messagesList, { childList: true });
        }
    });

    // Handle modal positioning on mobile
    if (isMobile) {
        document.addEventListener('DOMContentLoaded', function() {
            const modals = document.querySelectorAll('.modal');
            modals.forEach(modal => {
                modal.addEventListener('touchmove', function(e) {
                    // Prevent background scrolling when modal is open
                    if (modal.classList.contains('active')) {
                        const modalContent = modal.querySelector('.modal-content');
                        if (modalContent && !modalContent.contains(e.target)) {
                            e.preventDefault();
                        }
                    }
                });
            });
        });
    }

    // Prevent double-tap zoom
    let lastTouchEnd = 0;
    document.addEventListener('touchend', function(event) {
        const now = Date.now();
        if (now - lastTouchEnd <= 300) {
            event.preventDefault();
        }
        lastTouchEnd = now;
    }, { passive: false });

    // Add mobile class to body
    if (isMobile) {
        document.body.classList.add('is-mobile');
        if (isIOS) {
            document.body.classList.add('is-ios');
        }
    }

})();