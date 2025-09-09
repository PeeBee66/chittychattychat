// Admin Panel JavaScript

class AdminPanel {
    constructor() {
        this.init();
    }
    
    init() {
        this.setupAutoRefresh();
        this.setupTimers();
        this.setupTableSorting();
    }
    
    setupAutoRefresh() {
        // Auto-refresh dashboard every 2 minutes
        if (window.location.pathname === '/') {
            setTimeout(() => {
                this.refreshPage();
            }, 120000);
        }
    }
    
    setupTimers() {
        // Update countdown timers every minute
        this.updateTimers();
        setInterval(() => {
            this.updateTimers();
        }, 60000);
    }
    
    updateTimers() {
        document.querySelectorAll('.timer[data-seconds]').forEach(timer => {
            let seconds = parseInt(timer.dataset.seconds);
            seconds -= 60; // Subtract 1 minute
            
            if (seconds <= 0) {
                timer.innerHTML = '⏰ Expired';
                timer.classList.add('expired');
                timer.removeAttribute('data-seconds');
            } else {
                const hours = Math.floor(seconds / 3600);
                const minutes = Math.floor((seconds % 3600) / 60);
                timer.innerHTML = `${hours}h ${minutes}m`;
                timer.dataset.seconds = seconds;
            }
        });
    }
    
    setupTableSorting() {
        // Add click handlers to table headers for sorting
        const headers = document.querySelectorAll('.rooms-table th');
        headers.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => {
                this.sortTable(header);
            });
        });
    }
    
    sortTable(header) {
        const table = header.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const columnIndex = Array.from(header.parentNode.children).indexOf(header);
        const isAscending = !header.classList.contains('sort-asc');
        
        // Clear previous sort indicators
        header.parentNode.querySelectorAll('th').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });
        
        // Add sort indicator
        header.classList.add(isAscending ? 'sort-asc' : 'sort-desc');
        
        // Sort rows
        rows.sort((a, b) => {
            const aCell = a.children[columnIndex];
            const bCell = b.children[columnIndex];
            
            if (!aCell || !bCell) return 0;
            
            let aValue = aCell.textContent.trim();
            let bValue = bCell.textContent.trim();
            
            // Handle numeric values
            if (!isNaN(aValue) && !isNaN(bValue)) {
                aValue = parseFloat(aValue);
                bValue = parseFloat(bValue);
            }
            
            // Handle dates
            if (aValue.includes('-') && aValue.includes(':')) {
                aValue = new Date(aValue);
                bValue = new Date(bValue);
            }
            
            let result;
            if (aValue < bValue) {
                result = -1;
            } else if (aValue > bValue) {
                result = 1;
            } else {
                result = 0;
            }
            
            return isAscending ? result : -result;
        });
        
        // Re-append sorted rows
        rows.forEach(row => tbody.appendChild(row));
    }
    
    refreshPage() {
        // Smooth refresh with loading indicator
        document.body.style.opacity = '0.7';
        setTimeout(() => {
            window.location.reload();
        }, 500);
    }
    
    formatTimestamp(date) {
        return new Date(date).toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `admin-notification notification-${type}`;
        notification.innerHTML = `
            <span class="notification-message">${message}</span>
            <button class="notification-close">&times;</button>
        `;
        
        // Styles
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 10px;
            color: white;
            font-weight: 600;
            z-index: 3000;
            display: flex;
            align-items: center;
            gap: 15px;
            animation: slideInFromRight 0.3s ease;
            max-width: 400px;
            word-wrap: break-word;
        `;
        
        switch (type) {
            case 'success':
                notification.style.backgroundColor = '#28a745';
                break;
            case 'error':
                notification.style.backgroundColor = '#dc3545';
                break;
            case 'warning':
                notification.style.backgroundColor = '#ffc107';
                notification.style.color = '#212529';
                break;
            default:
                notification.style.backgroundColor = '#667eea';
        }
        
        // Close button
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.style.cssText = `
            background: none;
            border: none;
            color: inherit;
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0;
            margin-left: auto;
        `;
        
        closeBtn.addEventListener('click', () => {
            this.removeNotification(notification);
        });
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                this.removeNotification(notification);
            }
        }, 5000);
    }
    
    removeNotification(notification) {
        notification.style.animation = 'slideOutToRight 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 300);
    }
}

// Copy to clipboard functionality
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            window.adminPanel.showNotification('Copied to clipboard!', 'success');
        }).catch(() => {
            window.adminPanel.showNotification('Failed to copy to clipboard', 'error');
        });
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            window.adminPanel.showNotification('Copied to clipboard!', 'success');
        } catch (err) {
            window.adminPanel.showNotification('Failed to copy to clipboard', 'error');
        }
        document.body.removeChild(textArea);
    }
}

// Add click-to-copy functionality to room IDs, device IDs, and IP addresses
document.addEventListener('DOMContentLoaded', () => {
    // Initialize admin panel
    window.adminPanel = new AdminPanel();
    
    // Add click-to-copy for room IDs
    document.querySelectorAll('.room-id-badge').forEach(badge => {
        badge.style.cursor = 'pointer';
        badge.title = 'Click to copy';
        badge.addEventListener('click', () => {
            copyToClipboard(badge.textContent);
        });
    });
    
    // Add click-to-copy for device IDs
    document.querySelectorAll('.device-id').forEach(deviceId => {
        deviceId.style.cursor = 'pointer';
        deviceId.title = 'Click to copy';
        deviceId.addEventListener('click', () => {
            copyToClipboard(deviceId.textContent);
        });
    });
    
    // Add click-to-copy for IP addresses
    document.querySelectorAll('.ip-address').forEach(ipAddress => {
        ipAddress.style.cursor = 'pointer';
        ipAddress.title = 'Click to copy';
        ipAddress.addEventListener('click', () => {
            copyToClipboard(ipAddress.textContent);
        });
    });
    
    // Highlight search terms in URLs
    const urlParams = new URLSearchParams(window.location.search);
    const searchTerm = urlParams.get('search');
    if (searchTerm) {
        highlightText(document.body, searchTerm);
    }
});

// Text highlighting function
function highlightText(element, term) {
    const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );
    
    const textNodes = [];
    let node;
    
    while (node = walker.nextNode()) {
        textNodes.push(node);
    }
    
    textNodes.forEach(textNode => {
        const text = textNode.textContent;
        const regex = new RegExp(`(${term})`, 'gi');
        
        if (regex.test(text)) {
            const highlighted = text.replace(regex, '<mark>$1</mark>');
            const span = document.createElement('span');
            span.innerHTML = highlighted;
            textNode.parentNode.replaceChild(span, textNode);
        }
    });
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInFromRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutToRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    .rooms-table th.sort-asc::after {
        content: ' ↑';
        color: #fff;
    }
    
    .rooms-table th.sort-desc::after {
        content: ' ↓';
        color: #fff;
    }
    
    mark {
        background-color: #ffeb3b;
        color: #000;
        padding: 2px 4px;
        border-radius: 3px;
    }
    
    .admin-notification .notification-close:hover {
        opacity: 0.7;
    }
`;
document.head.appendChild(style);