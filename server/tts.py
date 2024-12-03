# curl --request POST \
#      --header "Content-Type: application/json" \
#      --header "Authorization: Token DEEPGRAM_API_KEY" \
#      --output your_output_file.mp3 \
#      --data '{"text":"Hello, how can I help you today?"}' \
#      --url "https://api.deepgram.com/v1/speak?model=aura-asteria-en"


# The above is the example curl code for TTS on deepgram.

from typing import Iterator
from logger import logger
import httpx

from constants import DEEPGRAM_API_KEY, SPEAK_URL


def to_speech(
    text: str,
    voice: str = "aura-asteria-en",
) -> bytes:
    url = f"{SPEAK_URL}?model={voice}"
    logger.info(f"[SPEAK] @{voice}: {text}")

    response = httpx.post(
        url,
        headers={
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"text": text},
    )

    response.raise_for_status()

    return response.content
