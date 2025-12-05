/**
 * Common JavaScript Utilities for Hywel Dda IPAR
 * Clean, functional utilities without decorative animations
 */

/* ============================================
   Toast Notification System
   ============================================ */
window.ToastManager = {
    container: null,
    
    init() {
        if (!this.container) {
            this.container = document.getElementById('toast-container');
            if (!this.container) {
                this.container = document.createElement('div');
                this.container.id = 'toast-container';
                this.container.className = 'toast-container';
                document.body.appendChild(this.container);
            }
        }
    },
    
    show(type, title, message, duration = 5000) {
        this.init();
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const iconMap = {
            success: 'fas fa-check',
            error: 'fas fa-times',
            warning: 'fas fa-exclamation',
            info: 'fas fa-info'
        };
        
        toast.innerHTML = `
            <div class="toast-icon">
                <i class="${iconMap[type] || iconMap.info}"></i>
            </div>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                ${message ? `<div class="toast-message">${message}</div>` : ''}
            </div>
            <button class="toast-dismiss" aria-label="Dismiss">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Add dismiss handler
        const dismissBtn = toast.querySelector('.toast-dismiss');
        dismissBtn.addEventListener('click', () => this.dismiss(toast));
        
        this.container.appendChild(toast);
        
        // Auto dismiss
        if (duration > 0) {
            setTimeout(() => this.dismiss(toast), duration);
        }
        
        return toast;
    },
    
    success(title, message, duration) {
        return this.show('success', title, message, duration);
    },
    
    error(title, message, duration = 8000) {
        return this.show('error', title, message, duration);
    },
    
    warning(title, message, duration) {
        return this.show('warning', title, message, duration);
    },
    
    info(title, message, duration) {
        return this.show('info', title, message, duration);
    },
    
    dismiss(toast) {
        if (!toast || !toast.parentElement) return;
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 200);
    },
    
    clear() {
        if (!this.container) return;
        const toasts = this.container.querySelectorAll('.toast');
        toasts.forEach(toast => this.dismiss(toast));
    }
};

/* ============================================
   Loading State Manager
   ============================================ */
window.LoadingManager = {
    overlay: null,
    
    init() {
        this.overlay = document.getElementById('loading-overlay');
    },
    
    show(message = 'Loading...') {
        if (!this.overlay) this.init();
        if (!this.overlay) return;
        
        const messageEl = this.overlay.querySelector('.loading-message');
        if (messageEl) {
            messageEl.textContent = message;
        }
        
        this.overlay.classList.add('active');
    },
    
    hide() {
        if (!this.overlay) return;
        this.overlay.classList.remove('active');
    }
};

/* ============================================
   Button Loading States
   ============================================ */
window.ButtonLoader = {
    show(button, text = null) {
        if (typeof button === 'string') {
            button = document.getElementById(button);
        }
        if (!button) return;
        
        button.dataset.originalText = button.innerHTML;
        button.classList.add('btn-loading');
        button.disabled = true;
        
        if (text) {
            button.textContent = text;
        }
    },
    
    hide(button) {
        if (typeof button === 'string') {
            button = document.getElementById(button);
        }
        if (!button) return;
        
        button.classList.remove('btn-loading');
        button.disabled = false;
        
        if (button.dataset.originalText) {
            button.innerHTML = button.dataset.originalText;
            delete button.dataset.originalText;
        }
    }
};

/* ============================================
   Mobile Navigation
   ============================================ */
function initMobileNavigation() {
    const toggle = document.getElementById('mobile-menu-toggle');
    const menu = document.getElementById('mobile-menu');
    
    if (!toggle || !menu) return;
    
    let isOpen = false;
    
    function toggleMenu() {
        isOpen = !isOpen;
        
        if (isOpen) {
            menu.classList.add('open');
            toggle.setAttribute('aria-expanded', 'true');
            const icon = toggle.querySelector('i');
            if (icon) {
                icon.classList.remove('fa-bars');
                icon.classList.add('fa-times');
            }
        } else {
            menu.classList.remove('open');
            toggle.setAttribute('aria-expanded', 'false');
            const icon = toggle.querySelector('i');
            if (icon) {
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            }
        }
    }
    
    toggle.addEventListener('click', (e) => {
        e.preventDefault();
        toggleMenu();
    });
    
    // Close on outside click
    document.addEventListener('click', (e) => {
        if (isOpen && !menu.contains(e.target) && !toggle.contains(e.target)) {
            toggleMenu();
        }
    });
    
    // Close on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isOpen) {
            toggleMenu();
            toggle.focus();
        }
    });
    
    // Close menu on link click
    menu.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            if (isOpen) toggleMenu();
        });
    });
    
    // Close on resize if desktop
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (window.innerWidth >= 768 && isOpen) {
                toggleMenu();
            }
        }, 100);
    });
}

/* ============================================
   HTMX Integration
   ============================================ */
function initHTMXHandlers() {
    // Loading state on request
    document.addEventListener('htmx:beforeRequest', (event) => {
        const trigger = event.detail.elt;
        
        // Add loading state to buttons
        if (trigger.tagName === 'BUTTON' || trigger.type === 'submit') {
            ButtonLoader.show(trigger);
        }
    });
    
    // Remove loading state after request
    document.addEventListener('htmx:afterRequest', (event) => {
        const trigger = event.detail.elt;
        
        if (trigger.tagName === 'BUTTON' || trigger.type === 'submit') {
            ButtonLoader.hide(trigger);
        }
    });
    
    // Handle errors
    document.addEventListener('htmx:responseError', (event) => {
        const status = event.detail.xhr.status;
        let title = 'Request Failed';
        let message = 'An error occurred. Please try again.';
        
        switch (status) {
            case 400:
                title = 'Bad Request';
                message = 'Please check your input and try again.';
                break;
            case 401:
                title = 'Authentication Required';
                message = 'Please log in to continue.';
                break;
            case 403:
                title = 'Access Denied';
                message = 'You don\'t have permission for this action.';
                break;
            case 404:
                title = 'Not Found';
                message = 'The requested resource could not be found.';
                break;
            case 500:
                title = 'Server Error';
                message = 'An internal error occurred. Please try again later.';
                break;
        }
        
        ToastManager.error(title, message);
    });
}

/* ============================================
   Keyboard Shortcuts
   ============================================ */
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Only trigger with Alt key
        if (!e.altKey) return;
        
        switch (e.key.toLowerCase()) {
            case 'h':
                e.preventDefault();
                window.location.href = '/api/documents/ui/chat';
                break;
            case 'd':
                e.preventDefault();
                window.location.href = '/documents';
                break;
            case 's':
                e.preventDefault();
                window.location.href = '/api/documents/ui/search';
                break;
            case 'u':
                e.preventDefault();
                window.location.href = '/documents/upload';
                break;
        }
    });
}

/* ============================================
   Modal Utilities
   ============================================ */
window.ModalManager = {
    open(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        
        // Focus first focusable element
        const focusable = modal.querySelector('button, input, textarea, select, a[href]');
        if (focusable) {
            setTimeout(() => focusable.focus(), 100);
        }
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.close(modalId);
            }
        });
    },
    
    close(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }
};

// Global function for inline onclick handlers
function openModal(modalId) {
    ModalManager.open(modalId);
}

function closeModal(modalId) {
    ModalManager.close(modalId);
}

/* ============================================
   Form Utilities
   ============================================ */
function initFormEnhancements() {
    // Auto-resize textareas
    document.querySelectorAll('textarea[data-auto-resize]').forEach(textarea => {
        function resize() {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        }
        
        textarea.addEventListener('input', resize);
        resize();
    });
    
    // Form validation feedback
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            const invalids = form.querySelectorAll(':invalid');
            if (invalids.length > 0) {
                invalids[0].focus();
            }
        });
    });
}

/* ============================================
   Copy to Clipboard
   ============================================ */
window.copyToClipboard = async function(text, successMessage = 'Copied to clipboard') {
    try {
        await navigator.clipboard.writeText(text);
        ToastManager.success('Success', successMessage, 2000);
    } catch (err) {
        ToastManager.error('Failed', 'Could not copy to clipboard');
    }
};

/* ============================================
   Initialize on DOM Ready
   ============================================ */
document.addEventListener('DOMContentLoaded', () => {
    initMobileNavigation();
    initHTMXHandlers();
    initKeyboardShortcuts();
    initFormEnhancements();
    
    // Initialize toast container
    ToastManager.init();
});

/* ============================================
   Escape key handler for modals
   ============================================ */
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        // Close any open modals
        document.querySelectorAll('.modal-backdrop[style*="flex"]').forEach(modal => {
            ModalManager.close(modal.id);
        });
    }
});

