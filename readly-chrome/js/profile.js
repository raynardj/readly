import { login_redirect, get_server_url } from './user.js';


chrome.storage.sync.get(['serverURL'], function (result) {
    const serverURL = result.serverURL || 'https://localhost:8000'

    console.log({ serverURL })

    fetch(`${serverURL}/my_profile`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        },
        credentials: 'include'
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(profile => {
            console.log({ profile })
            document.getElementById('profile-picture').src = profile.picture;
            document.getElementById('full-name').textContent = profile.name;
            document.getElementById('email').textContent = profile.email;

            // Show verified badge
            if (profile.email_verified) {
                document.getElementById('verified-badge').style.display = 'inline';
            }
        })
        .catch(error => {
            console.error('Error fetching profile:', error);
            // Add user-friendly error handling
            document.getElementById('profile-picture').src = 'default-avatar.png';
            document.getElementById('full-name').textContent = 'Error loading profile';
            document.getElementById('email').textContent = 'Please try again later';
            document.getElementById('verified-badge').style.display = 'none';

            // clear current cookie
            // chrome.storage.sync.remove("oauth_token");
            login_redirect();
        });
});


document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('settings-btn').addEventListener('click', () => {
        console.log('jump to settings')
        chrome.tabs.create({ url: `/settings.html`, active: true });
    });

    document.getElementById('logout-btn').addEventListener('click', async () => {
        console.log('logout')

        let extension_id = chrome.runtime.id;
        let server_url = await get_server_url();
        window.location.href = `${server_url}/logout?extension_id=${extension_id}`;
    });
});

