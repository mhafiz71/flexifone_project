/**
 * FlexiFone Notifications System
 * This script provides functions to show toast notifications throughout the application
 */

// Main function to show toast notifications
function showToast(message, type = 'info') {
    // Dispatch a custom event that will be caught by the base template
    document.dispatchEvent(new CustomEvent('showToast', {
        detail: {
            message: message,
            type: type // 'success', 'error', 'info', 'warning'
        }
    }));
}

// Helper functions for specific notification types
const notifications = {
    // Payment notifications
    payment: {
        success: (amount) => showToast(`Payment of ₵${amount} processed successfully!`, 'success'),
        failed: (reason) => showToast(`Payment failed: ${reason}`, 'error'),
        pending: () => showToast('Your payment is being processed...', 'info')
    },
    
    // Account notifications
    account: {
        created: () => showToast('Your account has been created successfully!', 'success'),
        updated: () => showToast('Your account has been updated successfully!', 'success'),
        planCompleted: (product) => showToast(`Congratulations! You've completed your payment plan for the ${product}!`, 'success')
    },
    
    // Application notifications
    application: {
        submitted: () => showToast('Your application has been submitted successfully!', 'success'),
        approved: () => showToast('Your credit application has been approved!', 'success'),
        rejected: (reason) => showToast(`Your application was not approved: ${reason}`, 'error'),
        pending: () => showToast('Your application is being reviewed...', 'info')
    },
    
    // General notifications
    general: {
        success: (message) => showToast(message, 'success'),
        error: (message) => showToast(message, 'error'),
        info: (message) => showToast(message, 'info'),
        warning: (message) => showToast(message, 'warning')
    }
};

// Export the notifications object for use in other scripts
window.notifications = notifications;