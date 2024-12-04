// This is the background script for the Readly extension.
chrome.runtime.onInstalled.addListener(() => {
    console.log("Readly background running.");
});

const getTextAndOpenNewTab = () => {
    // Function to get text from the current tab and open a new tab
    const selectedText = window.getSelection().toString();
    if (selectedText) {
        chrome.runtime.sendMessage({ text: selectedText });
    }
}


// Listen for messages to open a new tab
chrome.runtime.onMessage.addListener(async (request, sender, sendResponse) => {
    console.log('Text message received:', request);
    if (request.text) {
        // Generate a unique key

        let uuid = crypto.randomUUID().substring(0, 8);
        const storageKey = 'readly_' + uuid;

        let store_data = {
            ts: new Date().toISOString().replace('T', ' ').substring(0, 19),
            text: request.text,
            url: sender.tab.url,
            storageKey: storageKey,
        }
        console.log({ store_data, storageKey })
        // Store the text with the unique key
        chrome.storage.local.set({ [storageKey]: store_data }, () => {
            // Open new tab with just the key as parameter
            const readUrl = chrome.runtime.getURL('read.html') +
                `?key=${encodeURIComponent(storageKey)}`;
            chrome.tabs.create({ url: readUrl });
        });
    }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'processSelectedText') {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const currentTab = tabs[0];
            console.log('Current tab:', currentTab);
            try {
                chrome.scripting.executeScript({
                    target: { tabId: currentTab.id },
                    function: getTextAndOpenNewTab
                }).catch(err => console.error('Script execution failed:', err));
            } catch (err) {
                console.error('Failed to execute script:', err);
            }
        });
    }
});
