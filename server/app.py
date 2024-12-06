# from fastapi import FastAPI, Request, HTTPException, Depends
# from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
# from fastapi import Query


import base64
from traceback import format_exc
import argparse

from tts import to_speech
from constants import READLY_SECRET_KEY

from logger import logger
from tcp_server import (
    TCPServer,
    Request,
    JSONResponse,
    RedirectResponse,
    HTMLResponse,
    require_auth,
    JWT,
)

from sql_data import build_engine

# the CRUD operations for the database
from crud_data import (
    create_text_entry,
    get_text_entry,
    get_user_text_entries,
    user_login,
    create_tts_request,
    get_tts_requests,
    object_to_dict,
)

from utils import await_coroutine, sentence_tokenizer, oauth

import time

parser = argparse.ArgumentParser()
parser.add_argument("--log_level", type=str, default="INFO")
parser.add_argument("--n_workers", type=int, default=2)
args = parser.parse_args()

app = TCPServer(n_workers=args.n_workers)

app.use(JWT, secret_key=READLY_SECRET_KEY)

engine, init_db, drop_db = build_engine()


@app.get("/")
@require_auth
def read_root():
    return JSONResponse({"message": "Hello"})


@app.get("/naked")
def naked(request: Request):
    return JSONResponse({"message": "This is a naked endpoint, not protected by auth"})


@app.get("/login")
def login(request: Request):
    """
    Initiates the Google OAuth login flow.

    Args:
        request (Request): The incoming request object containing query parameters
            - extension_id: Chrome extension ID
            - key: Optional key parameter

    Returns:
        RedirectResponse: Redirects to Google OAuth consent screen
    """
    extension_id = request.query_params.get("extension_id")
    key = request.query_params.get("key")

    if key is None:
        redirect_uri = f"{request.base_url}/auth?extension_id={extension_id}"
    else:
        redirect_uri = f"{request.base_url}/auth?extension_id={extension_id}&key={key}"

    coroutine = oauth.google.authorize_redirect(
        request,
        redirect_uri,
    )

    url = await_coroutine(coroutine).headers.get("Location")
    if url is None:
        return JSONResponse({"error": "500 Internal Server Error"}, status=500)
    return RedirectResponse(url=url)


@app.get("/auth")
def auth(request: Request):
    """
    Handles the OAuth callback from Google authentication.

    Args:
        request (Request): The incoming request containing:
            - code: OAuth authorization code
            - state: OAuth state parameter
            - extension_id: Chrome extension ID
            - key: Optional key parameter

    Returns:
        RedirectResponse: Redirects to extension page with user session

    Raises:
        Exception: If authentication fails
    """
    try:
        token = await_coroutine(oauth.google.authorize_access_token(request))
        userinfo = await_coroutine(oauth.google.userinfo(token=token))
    except Exception as e:
        logger.error(f"🔌 Traceback: {format_exc()}")
        logger.error(f"Auth error: {str(e)}")
        raise

    if userinfo is None:
        return JSONResponse({"error": "500 Internal Server Error"}, status=500)

    # Add user login
    user_sub = userinfo["sub"]
    user_email = userinfo["email"]
    user_name = userinfo.get("name", "")
    user_login(engine, user_sub, user_email, user_name)

    extension_id = request.query_params.get("extension_id")
    key = request.query_params.get("key")
    if key is None:
        redirect_uri = f"{request.base_url}/redirect?extension_id={extension_id}"
    else:
        redirect_uri = f"{request.base_url}/redirect?extension_id={extension_id}&key={key}"
    response = RedirectResponse(url=redirect_uri)
    request.session["user"] = userinfo
    return response


@app.get("/redirect")
def redirect(request: Request):
    """
    Redirects user back to Chrome extension after successful authentication.

    Args:
        request (Request): The incoming request containing:
            - extension_id: Chrome extension ID
            - key: Optional key parameter

    Returns:
        RedirectResponse: Redirects to appropriate extension page
    """
    extension_id = request.query_params.get("extension_id")
    key = request.query_params.get("key")
    if key is None:
        return RedirectResponse(url=f"chrome-extension://{extension_id}/profile.html")
    else:
        return RedirectResponse(url=f"chrome-extension://{extension_id}/read.html?key={key}")


@app.get("/close_window")
def close_window(request: Request):
    """
    Returns HTML that closes the current browser window.

    Args:
        request (Request): The incoming request

    Returns:
        HTMLResponse: Script to close window
    """
    return HTMLResponse(content="<script>window.close();</script>")


@app.get("/logout")
def logout(request: Request):
    """
    Logs out the current user by clearing their session.

    Args:
        request (Request): The incoming request containing:
            - extension_id: Optional Chrome extension ID

    Returns:
        RedirectResponse: Redirects to login page
    """
    request.session.clear()
    extension_id = request.query_params.get("extension_id")
    if extension_id is None:
        return RedirectResponse(url=f"{request.base_url}/login")
    else:
        return RedirectResponse(url=f"{request.base_url}/login?extension_id={extension_id}")


@app.get("/my_profile")
@require_auth
def my_profile(request: Request):
    """
    Returns the current user's profile information.

    Args:
        request (Request): The authenticated request

    Returns:
        JSONResponse: User profile data including:
            - Google profile information
            - Truncated session token
    """
    user = request.session.get("user")
    user["token"] = request.cookies.get("session")[:20]
    return JSONResponse(user)


class EventType:
    SPEAK = "speak"


@app.post("/text_entry/create/")
@require_auth
def text_entry_create(
    request: Request,
):
    """
    Creates a new text entry in the database.

    Args:
        request (Request): The authenticated request containing:
            - text_id: Unique identifier for the text
            - text: The full text content
            - url: Optional source URL

    Returns:
        JSONResponse: Created text entry object
    """
    data = request.json()
    user = request.session.get("user")
    user_sub = user["sub"]

    # Now create the text entry
    full_text = data["text"]
    logger.info(f"💎 {user_sub} - {full_text}")
    res = create_text_entry(
        engine,
        data["text_id"],
        user_sub,
        full_text=full_text,
        url=data.get("url"),
    )
    return JSONResponse(object_to_dict(res))


@app.get("/text_entry/get/")
@require_auth
def text_entry_get(
    request: Request,
):
    """
    Retrieves a specific text entry by ID.

    Args:
        request (Request): The authenticated request containing:
            - text_id: ID of text entry to retrieve

    Returns:
        JSONResponse: Text entry object if found

    Raises:
        400: If text_id is missing
        404: If text entry not found
    """
    text_id = request.query_params.get("text_id")
    if not text_id:
        return JSONResponse({"error": "text_id is required"}, status=400)

    text_entry = get_text_entry(engine, text_id)
    if text_entry is None:
        return JSONResponse({"error": "Text entry not found"}, status=404)
    return JSONResponse(object_to_dict(text_entry))


@app.post("/sentence_measure/")
@require_auth
def sentence_measure(
    request: Request,
):
    """
    Splits text into sentences and returns sentence metrics.

    Args:
        request (Request): The authenticated request containing:
            - text_id: ID of text to process

    Returns:
        JSONResponse: Object containing:
            - text_id: Original text ID
            - sentences: List of sentence strings
            - sentence_lengths: List of sentence character counts
            - user_email: Email of requesting user
            - num_sentences: Total number of sentences

    Raises:
        400: If text_id missing or no text content
        404: If text entry not found
    """
    data = request.json()
    text_id = data.get("text_id")
    if not text_id:
        logger.debug("400 - text_id is required")
        return JSONResponse({"error": "text_id is required"}, status=400)

    user = request.session.get("user")

    user_email = user.get("email")
    text_entry = get_text_entry(engine, text_id)
    logger.debug(object_to_dict(text_entry))
    if text_entry is None:
        logger.warning(f"404 - {user_email} - Text entry not found")
        return JSONResponse({"error": "Text entry not found"}, status=404)
    if not text_entry.full_text:
        logger.debug(f"400 - {user_email} - No text provided")
        return JSONResponse({"error": "No text provided"}, status=400)

    text = text_entry.full_text
    sentences = []
    for sentence in sentence_tokenizer(text).sents:
        sentence_text = sentence.text
        if len(sentence_text.strip()) > 0:
            sentences.append(sentence_text)

    return JSONResponse(
        {
            "text_id": text_id,
            "sentences": sentences,
            "sentence_lengths": [len(sentence) for sentence in sentences],
            "user_email": user_email,
            "num_sentences": len(sentences),
        }
    )


@app.post("/speak")
@require_auth
def speak(
    request: Request,
):
    """
    Converts text to speech for a specific sentence.

    Args:
        request (Request): The authenticated request containing:
            - text_data: Object with sentences and text_id
            - play_idx: Index of sentence to convert (default: 0)

    Returns:
        JSONResponse: Object containing:
            - audio_id: Unique ID for the audio
            - play_idx: Index of converted sentence
            - data: Base64 encoded audio bytes
    """

    data = request.json()
    user = request.session.get("user")
    text_data = data["text_data"]
    sentences = text_data["sentences"]
    text_id = text_data["text_id"]

    play_idx = data.get("play_idx", 0)
    sentence_text = sentences[play_idx]

    audio_id = f"{text_id}-{play_idx:03d}"
    email = user.get("email")
    logger.info(f"⭐️ <{email}> : {audio_id}")
    start_time = time.time()
    audio_bytes = to_speech(sentence_text)
    processing_time_ms = int((time.time() - start_time) * 1000)

    # We need to keep track of the TTS requests (for dashboard and possibly billing)
    # Like the number of requests, the total characters, and the average processing time
    create_tts_request(
        engine,
        text_entry_id=text_id,
        user_sub=user["sub"],
        sentence_text=sentence_text,
        sentence_index=play_idx,
        audio_id=audio_id,
        character_count=len(sentence_text),
        processing_time_ms=processing_time_ms,
    )

    return JSONResponse(
        {
            "audio_id": audio_id,
            "play_idx": play_idx,
            "data": base64.b64encode(audio_bytes).decode("utf-8"),
        }
    )


# # ============== for dashboard =================
@app.get("/text_entries/")
@require_auth
def get_text_entries(request: Request):
    """
    Retrieves all text entries for the current user.

    Args:
        request (Request): The authenticated request

    Returns:
        JSONResponse: List of text entry objects
    """
    user = request.session.get("user")
    entries = get_user_text_entries(engine, user["sub"])

    return JSONResponse(entries)


@app.get("/tts_requests/")
@require_auth
def get_tts_requests_api(request: Request):
    """
    Retrieves all text-to-speech requests for the current user.

    Args:
        request (Request): The authenticated request

    Returns:
        JSONResponse: List of TTS request objects
    """
    user = request.session.get("user")
    requests = get_tts_requests(engine, user["sub"])
    return JSONResponse(requests)


app.run(
    logger_level=args.log_level,
    cert_file="cert.pem",
    key_file="key.pem",
)
