import { COLORS } from './constants.js';

const updateSentenceVisibility = (play_idx) => {
    const sentences = document.querySelectorAll('.sentence-box');
    const totalSentences = sentences.length;

    sentences.forEach((sentence, idx) => {
        sentence.classList.remove('active', 'before');

        if (idx === play_idx) {
            /*
            Active sentence in the middle, the followings will happen:
            - No blur
            - Opacity is 1
            - Font size is 1.5rem
            - Font weight is 600
            */
            sentence.classList.add('active');
            sentence.style.transform = 'translateY(-50%)';
            sentence.style.top = '50%';
            sentence.style.opacity = '1';
            sentence.style.background = 'rgba(255, 255, 255, 0.6)';
            sentence.style.fontSize = '1.0rem';
            sentence.style.fontWeight = '600';
            sentence.style.zIndex = totalSentences;
            sentence.style.filter = 'blur(0px)';  // No blur for active sentence
        } else if (idx < play_idx) {
            /*
            Previous sentences, the followings will happen:
            - stack upwards with decreasing z-index
            - Increasing blur based on distance
            - Decreasing opacity based on distance
            - Decreasing font size based on distance
            - Increasing font weight based on distance
            */
            let distance = play_idx - idx;
            let opacity = Math.max(0.1, 1 - (distance * 0.3));
            let translate = -100 * distance;
            let blurAmount = Math.min(8, distance * 2);
            sentence.classList.add('before');
            sentence.style.transform = `translateY(${translate}%)`;
            sentence.style.top = '50%';
            sentence.style.opacity = opacity;
            sentence.style.background = 'rgba(255, 255, 255, 0.6)';
            sentence.style.fontSize = '0.8rem';
            sentence.style.fontWeight = '400';
            sentence.style.zIndex = totalSentences - distance - 1;
            sentence.style.filter = `blur(${blurAmount}px)`;
        } else {
            /*
            Future sentences, the followings will happen:
            - stack downwards with decreasing z-index
            - Increasing blur based on distance
            - Decreasing opacity based on distance
            - Decreasing font size based on distance
            - Increasing font weight based on distance
            */
            let distance = idx - play_idx;
            let opacity = Math.max(0.1, 1 - (distance * 0.3));
            let translate = 100 * distance;
            let blurAmount = Math.min(8, distance * 2);
            sentence.style.transform = `translateY(${translate}%)`;
            sentence.style.top = '50%';
            sentence.style.opacity = opacity;
            sentence.style.background = 'rgba(255, 255, 255, 0.6)';
            sentence.style.fontSize = '0.8rem';
            sentence.style.fontWeight = '400';
            sentence.style.zIndex = totalSentences - distance - 1;
            sentence.style.filter = `blur(${blurAmount}px)`;
        }
    });
}

const generateProgressSegments = () => {
    /*
    Generate the progress bar segments
    */
    const container = document.getElementById('progressSegments');
    const numSegments = 1000;

    let progress_segments = [];

    for (let i = 0; i < numSegments; i++) {
        const segment = document.createElement('div');
        segment.className = 'progress-segment';
        segment.setAttribute('data-index', i);
        segment.style.width = '0.1%';
        segment.style.height = '100%';
        segment.style.background = COLORS.default;
        container.appendChild(segment);
        progress_segments.push(segment);
    }
    return progress_segments;
};

export { updateSentenceVisibility, generateProgressSegments };