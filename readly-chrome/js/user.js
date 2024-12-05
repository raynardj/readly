import { DEFAULT_SERVER_URL } from './constants.js';


async function get_server_url() {
    return new Promise((resolve) => {
        chrome.storage.sync.get(['serverUrl'], (result) => {
            resolve(result.serverUrl || DEFAULT_SERVER_URL);
        });
    });
}

async function login_redirect() {
    let server_url = await get_server_url();
    let parsed_query = new URLSearchParams(window.location.search);

    let key = parsed_query.get("key");
    let redirect_url;
    console.log({ log: "redirect_url", key, server_url })
    if (key) {
        redirect_url = `${server_url}/login?extension_id=${chrome.runtime.id}&key=${key}`;

    } else {
        redirect_url = `${server_url}/login?extension_id=${chrome.runtime.id}`;
    }
    window.location.href = redirect_url;
}


async function get_user_profile() {
    /*
    Get the user profile from the server
    */
    const server_url = await get_server_url();
    const response = await fetch(`${server_url}/my_profile`, {
        credentials: "include",
    });
    const data = await response.json();
    if (response.status === 200) {
        return data;
    } else if (response.status === 401) {

        await login_redirect();
    }
    throw new Error(data.error);
}

export { get_server_url, get_user_profile, login_redirect };
