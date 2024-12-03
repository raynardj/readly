// Default server URL
const DEFAULT_SERVER_URL = 'https://localhost:8000';

const extension_id = chrome.runtime.id;

const jump_to_google_login = (result) => {
    const serverUrl = result.serverUrl || DEFAULT_SERVER_URL;
    // Open login URL in new tab
    chrome.tabs.create({ url: `${serverUrl}/login?extension_id=${extension_id}`, active: true });
}

// Load saved settings when the page loads
document.addEventListener('DOMContentLoaded', () => {
    // Get the saved server URL or use default
    chrome.storage.sync.get(['serverUrl'], (result) => {
        const serverUrl = result.serverUrl || DEFAULT_SERVER_URL;
        document.getElementById('serverUrl').value = serverUrl;
    });

    // Handle form submission
    document.querySelector('form').addEventListener('submit', (e) => {
        e.preventDefault();
        const serverUrl = document.getElementById('serverUrl').value;

        // Save to Chrome storage
        chrome.storage.sync.set({ serverUrl }, () => {
            // Show success message (optional)
            alert('Settings saved successfully!');
        });
    });

    // Handle login button click
    document.getElementById('loginButton').addEventListener('click', () => {
        chrome.storage.sync.get(['serverUrl'], jump_to_google_login);
    });
});
