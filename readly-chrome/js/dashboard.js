import { get_server_url, get_user_profile } from './user.js';

async function loadTextEntries() {
    try {
        const serverUrl = await get_server_url();
        const userProfile = await get_user_profile();

        const response = await fetch(`${serverUrl}/text_entries/`, {
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Failed to load text entries');
        }

        const entries = await response.json();
        const listContainer = document.getElementById('list-of-links');

        entries.forEach(entry => {
            const li = document.createElement('li');
            li.className = 'nav-item';

            const link = document.createElement('a');
            link.className = 'nav-link text-truncate';
            link.href = `/read.html?key=${entry.text_id}`;
            link.style.maxWidth = '100%';

            const icon = document.createElement('i');
            icon.className = 'fas fa-book me-2';

            let displayText = entry.url ? new URL(entry.url).hostname : 'Text Entry';
            if (entry.full_text) {
                displayText = entry.full_text.substring(0, 20).trim() + '...';
            }
            const text = document.createTextNode(displayText);

            link.appendChild(icon);
            link.appendChild(text);
            li.appendChild(link);
            listContainer.appendChild(li);
        });
    } catch (error) {
        console.error('Error loading text entries:', error);
    }
}

async function loadTTSRequests() {
    try {
        const serverUrl = await get_server_url();
        const response = await fetch(`${serverUrl}/tts_requests/`, {
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Failed to load TTS requests');
        }

        const requests = await response.json();

        console.log({ log: 'TTS Requests Tracking', requests });

        // Update the dashboard statistics
        document.getElementById('total-requests').textContent = requests.length;

        let totalChars = 0;
        requests.forEach(req => {
            totalChars += req.sentence_text.length;
        });
        document.getElementById('total-characters').textContent =
            totalChars.toLocaleString();

        // Calculate average processing time
        const avgProcessingTime = requests.reduce((acc, req) =>
            acc + (req.processing_time_ms || 0), 0) / requests.length;
        document.getElementById('processing-time').textContent =
            `${Math.round(avgProcessingTime)}ms`;


    } catch (error) {
        console.error('Error loading TTS requests:', error);
    }
}


// Initialize the dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadTextEntries();
    loadTTSRequests();
});
