/*
This is the JS code that runs in the context of the web page.
Not background, for the background script, see background.js
*/
document.addEventListener('keydown', (event) => {
    // Check for Ctrl + ` (backtick)
    if ((event.ctrlKey || event.metaKey) && event.key === '`') {
        console.log('Keyboard shortcut detected');
        // Since we're in a content script
        // we need to send a message to the background script
        chrome.runtime.sendMessage({ action: 'processSelectedText' });
    }
}); 