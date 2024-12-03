import { get_user_profile, get_server_url, login_redirect } from './user.js';
import { updateSentenceVisibility, generateProgressSegments } from './visual_effects.js';
import { COLORS, WS_SERVER_URL, TRANSMISSION_RETRY_TIME, BUFFER_SENTENCES } from './constants.js';
// Get the key from URL parameters
const urlParams = new URLSearchParams(window.location.search);
const storageKey = urlParams.get('key');


let player_state = {
    playing: false,
    play_idx: 0,
    speed: 1.0,
    metadata: null,
    on_transmission: {},
};

const fetch_text_metadata = async (text) => {
    /*
    Fetch the text metadata from the server

    We use sentence tokenizer to cut the text into sentences
    and then measure the length of each sentence
    */
    let server_url = await get_server_url();
    const response = await fetch(server_url + '/sentence_measure', {
        method: 'POST',
        body: JSON.stringify({ text }),
    });
    let metadata = await response.json();
    build_progress_marks(metadata);
    console.info(player_state);
    return metadata;
}

const build_progress_marks = (metadata) => {
    /*
    Build the progress bar
    for metadata in the player_state
    we have sentence_lengths to mark the length of each sentence
    */
    let { num_sentences, sentence_lengths, sentences } = metadata;
    let total_length = sentence_lengths.reduce((a, b) => a + b, 0);
    let progress_marks = [];
    let marched = 0;
    let target_text = document.querySelector('#targetText');
    target_text.textContent = '';
    for (let player_idx = 0; player_idx < num_sentences; player_idx++) {
        let start_pct = marched / total_length; // start percentage
        marched += sentence_lengths[player_idx]; // end percentage
        let end_pct = marched / total_length;
        let sentence = sentences[player_idx];

        let sentence_text = document.createElement('p');
        sentence_text.textContent = sentence;
        sentence_text.classList.add('lead');
        sentence_text.classList.add('sentence-box')
        let play_idx_str = player_idx.toString().padStart(3, '0');
        sentence_text.id = `sentence-${play_idx_str}`;
        target_text.appendChild(sentence_text);

        progress_marks.push({
            length: sentence_lengths[player_idx],
            player_idx,
            total_length,
            start_pct,
            end_pct,
            sentence,
        });
    }
    player_state.progress_marks = progress_marks;

    updateSentenceVisibility(player_state.play_idx);
    return progress_marks;
}

if (storageKey) {
    // Retrieve the text using the key
    chrome.storage.local.get([storageKey], async function (result) {
        const data = result[storageKey];
        let { text, ts, url } = data;
        let user_profile = await get_user_profile();
        player_state.token = user_profile.token;
        player_state.sub = user_profile.sub;
        // console.log(user_profile);
        // Use the text
        console.log(data);
        document.querySelector('#targetText').textContent = data.text;
        let metadata = await fetch_text_metadata(data.text);
        player_state.metadata = metadata;
    });
}


document.addEventListener('DOMContentLoaded', () => {
    const audioPlayer = document.getElementById('audioPlayer');
    const playPauseBtn = document.getElementById('playPauseBtn');
    const backwardBtn = document.getElementById('backwardBtn');
    const forwardBtn = document.getElementById('forwardBtn');
    const progressBar = document.querySelector('.progress-bar');
    const progressContainer = document.getElementById('audioProgress');

    let progress_segments = generateProgressSegments();

    const set_progress_color = (from_idx, to_idx, color) => {
        /*
        Progress bar are 1000 segements in granularity
        Set the color for a segment range
        */
        for (let i = from_idx; i < to_idx; i++) {
            progress_segments[i].style.background = color;
        }
    };

    const set_progress_segment_color = (play_idx, color) => {
        /*
        Set the color for a progress segment
        (a sentence worth of audio chunk)
        */
        let progress_mark = player_state.progress_marks[play_idx];
        let { start_pct, end_pct } = progress_mark;
        let from_idx = Math.floor(start_pct * 1000);
        let to_idx = Math.floor(end_pct * 1000);
        set_progress_color(from_idx, to_idx, color);
    }

    const get_audio_id = (text_id, play_idx) => {
        let play_idx_str = play_idx.toString().padStart(3, '0');
        return `${text_id}-${play_idx_str}`;
    }

    const event_type_audio_chunk = async (message) => {
        let { audio_id, play_idx, data } = message;

        /*
        🔈🔈🔈🔈🔈
        This is the event type for where we receive the audio chunk
        Convert base64 to audio bytes
        and save to cache
        */
        chrome.storage.local.set({ [audio_id]: data });
        if (play_idx !== player_state.play_idx) {
            set_progress_segment_color(play_idx, COLORS.loaded);
        }
    }

    const message_event_handler = async (data) => {
        let { event_type } = data;
        if (event_type === 'audio_chunk') {
            await event_type_audio_chunk(data);
        } else if (event_type === 'authentication_error') {
            await login_redirect();
        } else {
            console.error(`[🔌🚨 SOCKET: ERROR]unknown event type: ${event_type}`);
        }
    }

    const set_up_socket_message = (socket) => {
        socket.onmessage = async (event) => {
            const message = JSON.parse(event.data);
            console.info(`[🔌🎵 SOCKET: MESSAGE]`);
            console.log(message);
            await message_event_handler(message);
        }
    }

    const build_socket = () => {
        /*
        Build a WebSocket connection to the server
        */
        const socket = new WebSocket(
            WS_SERVER_URL + `/speak?token=${player_state.token}&sub=${player_state.sub}`
        );

        console.log('[🔌 SOCKET:CONNECTING]');

        set_up_socket_message(socket);
        socket.onopen = () => {
            console.log('[🔌✨ SOCKET:OPENED]');
            player_state.socket_ready = true;
        }
        socket.onerror = (error) => {
            console.error('[🔌🚨 SOCKET:ERROR]', error);
            player_state.playing = false;
            player_state.socket_ready = false;
        };

        socket.onclose = () => {
            console.log('[🔌💤 SOCKET:CLOSED]');
            player_state.playing = false;
            player_state.socket_ready = false;
        };

        return socket;
    }

    const get_socket = () => {
        if (player_state.socket === undefined) {
            player_state.socket = build_socket();
        } else if (player_state.socket.readyState === WebSocket.CLOSED) {
            console.info("[🔌✨ SOCKET:RESTART]");
            player_state.socket = build_socket();
        }
        return player_state.socket;
    }

    const build_audio_chunk_buffer = async (play_idx, speed) => {
        /*
        Build the buffer for the audio chunk
        by sending the `speak` event to the server
        When ever the audio chunk shots back,
        it will be handled by the message_event_handler
        and saved to the chrome storage
        */
        let socket = get_socket();
        // Wait for socket to be ready before sending
        while (!player_state.socket_ready) {
            console.debug("[🔌 SOCKET:WAITING] socket ready");
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        console.info(`[🔌 SOCKET: speak]${play_idx} ${speed}x`);
        socket.send(JSON.stringify({
            event_type: 'speak',
            text_data: player_state.metadata,
            speed,
            play_idx,
        }));
        player_state.on_transmission[play_idx] = new Date().getTime();
    }

    const make_sure_chunk_buffer = async (play_idx) => {
        /*
        Check if the audio chunk buffer is built
        */
        console.info(`[🍄 CHECK: BUFFER]${play_idx}`);
        let { metadata, speed } = player_state;
        let { text_id } = metadata;
        let audio_id = get_audio_id(text_id, play_idx);
        let audio_data_loaded = await chrome.storage.local.get(audio_id);
        let audio_data = audio_data_loaded[audio_id];
        let audio_data_ready = audio_data !== undefined;

        let last_transmission = player_state.on_transmission[play_idx];
        if (audio_data_ready) {
            if (play_idx === player_state.play_idx) {
                return;
            } else {
                set_progress_segment_color(play_idx, COLORS.loaded);
            }
        } else if (last_transmission === undefined || new Date().getTime() - last_transmission > TRANSMISSION_RETRY_TIME) {
            /*
            if the audio chunk is never attempted before,
            and it has been n seconds since the last transmission,
            send the speak event to the server to build the audio chunk
            */
            await build_audio_chunk_buffer(play_idx, speed);
        }
    }

    const build_buffer_on_progress = async () => {
        let { num_sentences } = player_state.metadata;
        let { play_idx } = player_state;
        console.info(`[CHECK / BUILD] buffer on progress ${play_idx} / ${num_sentences}`);
        for (let i = play_idx; i < Math.min(num_sentences, play_idx + BUFFER_SENTENCES); i++) {
            /*
            Buffer the audio chunks for the next n sentences
            */
            await make_sure_chunk_buffer(i);
        }
    }

    const play_audio = async () => {
        let { metadata, play_idx, speed } = player_state;
        let { text_id } = metadata;
        let audio_id = get_audio_id(text_id, play_idx);
        let audio_data = await chrome.storage.local.get(audio_id)[audio_id];

        while (audio_data === undefined) {
            await new Promise(resolve => setTimeout(resolve, 100));
            let audio_url_data = await chrome.storage.local.get(audio_id);
            audio_data = audio_url_data[audio_id];
            console.warn(`[⏰ WAITING]${audio_id}`);
        }

        set_progress_segment_color(play_idx, COLORS.playing);
        updateSentenceVisibility(play_idx);

        console.info(`[🔊 PLAY] ${audio_id}`);
        let audio_blob = base64ToBlob(audio_data, 'audio/wav');
        let audio_url = URL.createObjectURL(audio_blob);

        audioPlayer.querySelector('source').src = audio_url;
        audioPlayer.load();
        audioPlayer.playbackRate = speed;
        audioPlayer.play();
    }

    const player_end_callback = async () => {
        /*
        If the player button says it is not playing
        do nothing
        */
        if (!player_state.playing) {
            return;
        }
        /*
        If the player is not at the last sentence
        play the next sentence
        */
        if (player_state.play_idx < player_state.metadata.num_sentences - 1) {
            // change the color of the current progress segment back to loaded
            set_progress_segment_color(player_state.play_idx, COLORS.loaded);
            player_state.play_idx += 1;
            await build_buffer_on_progress();
            play_audio();
        }
    }

    audioPlayer.addEventListener('ended', player_end_callback);

    const has_audio_bytes = () => {
        /*
        Check if the audio bytes are cached
        */
        return audioPlayer.duration > 0;
    }


    // Play/Pause toggle
    const togglePlayPause = async () => {
        /*
        Toggle the play/pause state
        */

        console.info("[TOGGLE] play/pause");
        player_state.playing = !player_state.playing;
        if (player_state.playing) {
            playPauseBtn.classList.remove('btn-primary');
            playPauseBtn.classList.add('btn-outline-secondary');
            await build_buffer_on_progress();
            if (has_audio_bytes()) {
                // resume from the last play point
                console.info("[RESUME] play");
                audioPlayer.play();
            } else {
                // trigger new play
                console.info("[NEW] play");
                play_audio();
            }
        } else {
            playPauseBtn.classList.remove('btn-outline-secondary');
            playPauseBtn.classList.add('btn-primary');
            audioPlayer.pause();
        }
    }

    const base64ToBlob = (base64, type) => {
        /*
        Helper function to convert base64 to Blob
        */
        const binaryString = window.atob(base64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return new Blob([bytes], { type: type });
    }

    const previousSentence = () => {
        /*
        Go to the previous sentence
        */
        if (player_state.play_idx > 0) {
            // change the color of the current progress segment back to loaded
            set_progress_segment_color(player_state.play_idx, COLORS.loaded);
            player_state.play_idx -= 1;
            build_buffer_on_progress();
            play_audio();
        }
    }

    const nextSentence = () => {
        /*
        Go to the next sentence
        */
        if (player_state.play_idx < player_state.metadata.num_sentences - 1) {
            // change the color of the current progress segment back to loaded
            set_progress_segment_color(player_state.play_idx, COLORS.loaded);
            player_state.play_idx += 1;
            build_buffer_on_progress();
            play_audio();
        }
    }

    // Set progress when clicking on progress bar
    function setProgress(e) {
        const clickTarget = e.target;
        if (!clickTarget.classList.contains('progress-segment')) {
            return;
        }

        const segmentIndex = parseInt(clickTarget.getAttribute('data-index'));
        const clickPosition = segmentIndex / 1000; // Convert to percentage (0-1)

        // Find the sentence that contains this position
        const targetSentence = player_state.progress_marks.find(mark =>
            clickPosition >= mark.start_pct && clickPosition <= mark.end_pct
        );

        if (targetSentence) {
            // change the color of the current progress segment back to loaded
            set_progress_segment_color(player_state.play_idx, COLORS.loaded);

            // Update play index and play the new sentence
            player_state.play_idx = targetSentence.player_idx;
            build_buffer_on_progress();
            play_audio();
        }
    }

    // Update playback speed
    function updatePlaybackSpeed(speed) {
        const speedDisplay = document.getElementById('speedDisplay');
        player_state.speed = parseFloat(speed);
        speedDisplay.textContent = speed + 'x';
        console.log(`[⚡️SPEED] ${speed}`);

        if (audioPlayer.playbackRate !== speed) {
            audioPlayer.playbackRate = speed;
        }
    }

    // Event listeners
    playPauseBtn.addEventListener('click', togglePlayPause);
    backwardBtn.addEventListener('click', previousSentence);
    forwardBtn.addEventListener('click', nextSentence);
    // audioPlayer.addEventListener('timeupdate', updateProgress);
    progressContainer.addEventListener('click', setProgress);
    document.getElementById('speedSlider').addEventListener('input', (e) => {
        updatePlaybackSpeed(e.target.value);
    });
});