import { DEFAULT_SERVER_URL } from './constants.js';
import { login_redirect, get_server_url } from './user.js';


const render_profile = (profile) => {
    let { picture, name, email, email_verified } = profile;
    document.getElementById('profile-picture').src = picture;
    document.getElementById('full-name').textContent = name;
    document.getElementById('email').textContent = email;

    if (email_verified) {
        document.getElementById('verified-badge').style.display = 'inline';
    }
}

const render_error = (error_msg) => {
    console.error(error_msg);
    document.getElementById('full-name').textContent = 'Not logged in';
    document.getElementById('email').textContent = 'Please try again later';
    document.getElementById('verified-badge').style.display = 'none';
}


chrome.storage.sync.get(['serverURL'], function (result) {
    const serverURL = result.serverURL || DEFAULT_SERVER_URL

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
        .then(render_profile)
        .catch(error => {
            render_error(error.message);
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

