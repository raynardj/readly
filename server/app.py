import abc
from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi import Query
from authlib.integrations.starlette_client import OAuth
import base64
from websockets.exceptions import ConnectionClosed
from traceback import format_exc

import spacy

from tts import to_speech
from constants import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, READLY_SECRET_KEY

from logger import logger
from session_manage import HTTPSSessionMiddleware, WebSocketAuthManager, require_auth
from redis_cache import set_auth_user, get_auth_user
from sql_data import build_engine
from crud_data import (
    create_text_entry,
    get_text_entry,
    get_user_text_entries,
    user_login,
    create_tts_request,
    get_tts_requests,
)

import time

app = FastAPI()

# session management for both HTTP and WebSocket requests
app.add_middleware(HTTPSSessionMiddleware, secret_key=READLY_SECRET_KEY)
socket_auth_manager = WebSocketAuthManager(secret_key=READLY_SECRET_KEY)

engine, init_db, drop_db = build_engine()

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# load only sentence tokenizer
sentence_tokenizer = spacy.load("en_core_web_sm", disable=["ner", "parser"])
sentence_tokenizer.add_pipe("sentencizer")


@app.get("/login")
async def login(request: Request):
    extension_id = request.query_params.get("extension_id")
    key = request.query_params.get("key")

    base_url = str(request.base_url).rstrip("/")
    if key is None:
        redirect_uri = f"{base_url}/auth?extension_id={extension_id}"
    else:
        redirect_uri = f"{base_url}/auth?extension_id={extension_id}&key={key}"

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
    )


@app.get("/auth")
async def auth(
    request: Request,
    extension_id: str = Query(None),
    key: str = Query(None),
):
    try:
        token = await oauth.google.authorize_access_token(request)
        userinfo = await oauth.google.userinfo(token=token)
    except Exception as e:
        logger.error(f"Auth error: {str(e)}")
        logger.error(f"Session state: {request.session.get('oauth_state')}")
        raise

    # Add user login
    user_sub = userinfo["sub"]
    user_email = userinfo["email"]
    user_name = userinfo.get("name", "")
    user_login(engine, user_sub, user_email, user_name)

    base_url = str(request.base_url).rstrip("/")
    if key is None:
        redirect_uri = f"{base_url}/redirect?extension_id={extension_id}"
    else:
        redirect_uri = f"{base_url}/redirect?extension_id={extension_id}&key={key}"
    response = RedirectResponse(url=redirect_uri)
    request.session["user"] = userinfo
    return response


@app.get("/redirect")
async def redirect(request: Request):
    extension_id = request.query_params.get("extension_id")
    key = request.query_params.get("key")
    if key is None:
        return RedirectResponse(url=f"chrome-extension://{extension_id}/profile.html")
    else:
        return RedirectResponse(url=f"chrome-extension://{extension_id}/read.html?key={key}")


@app.get("/close_window")
async def close_window(request: Request):
    return HTMLResponse(content="<script>window.close();</script>")


async def get_current_user(request: Request):
    userinfo = request.session.get("user")
    return userinfo


@app.get("/logout")
async def logout(request: Request, extension_id: str = Query(None)):
    request.session.clear()
    base_url = str(request.base_url).rstrip("/")
    if extension_id is None:
        return RedirectResponse(url=f"{base_url}/login")
    else:
        return RedirectResponse(url=f"{base_url}/login?extension_id={extension_id}")


@app.get("/")
@require_auth
async def read_root():
    return {"message": "Hello"}


@app.get("/my_profile")
@require_auth
async def my_profile(request: Request):
    """
    Return the current user's profile
    """
    user = request.session.get("user")
    user["token"] = request.cookies.get("session")[:20]
    return user


class EventType:
    SPEAK = "speak"


@app.post("/text_entry/create/")
@require_auth
async def text_entry_create(
    request: Request,
):
    """
    Create a new text entry
    """
    data = await request.json()
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
    return res


@app.get("/text_entry/get/{text_id}/")
@require_auth
async def text_entry_get(
    request: Request,
    text_id: str,
):
    text_entry = get_text_entry(engine, text_id)
    if text_entry is None:
        return JSONResponse(status_code=404, content={"error": "Text entry not found"})
    return text_entry


@app.post("/sentence_measure/{text_id}/")
@require_auth
async def sentence_measure(
    request: Request,
    text_id: str,
):
    """
    Cut the text into sentences
    """
    user = request.session.get("user")

    user_email = user.get("email")
    text_entry = get_text_entry(engine, text_id)
    if text_entry is None:
        logger.warning(f"404 - {user_email} - Text entry not found")
        return JSONResponse(status_code=404, content={"error": "Text entry not found"})
    if not text_entry.full_text:
        logger.warning(f"400 - {user_email} - No text provided")
        return JSONResponse(status_code=400, content={"error": "No text provided"})

    text = text_entry.full_text
    sentences = []
    for sentence in sentence_tokenizer(text).sents:
        sentence_text = sentence.text
        if len(sentence_text.strip()) > 0:
            sentences.append(sentence_text)

    return {
        "text_id": text_id,
        "sentences": sentences,
        "sentence_lengths": [len(sentence) for sentence in sentences],
        "user_email": user_email,
        "num_sentences": len(sentences),
    }


async def speak_event(
    websocket: WebSocket,
    data: dict,
    user: dict,
):
    """
    Handle the speak event
    """
    text_data = data["text_data"]
    sentences = text_data["sentences"]
    text_id = text_data["text_id"]

    # my decision is not to set the speed here but use the default one
    # on frontend, the speed is controlled by the slider
    # speed: float = data.get("speed", 1.0)
    speed = 1.0
    play_idx = data.get("play_idx", 0)
    sentence_text = sentences[play_idx]

    audio_id = f"{text_id}-{play_idx:03d}"
    email = user.get("email")
    logger.info(f"⭐️ <{email}> : {audio_id}")
    start_time = time.time()
    audio_bytes = to_speech(sentence_text)
    processing_time_ms = int((time.time() - start_time) * 1000)

    # We need to keep track of the TTS requests
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

    await websocket.send_json(
        {
            "event_type": "audio_chunk",
            "audio_id": audio_id,
            "play_idx": play_idx,
            "speed": speed,
            "data": base64.b64encode(audio_bytes).decode("utf-8"),
        }
    )


@app.websocket("/speak")
@socket_auth_manager.auth
async def text_to_speech_socket(websocket: WebSocket):
    """
    WebSocket endpoint for text-to-speech streaming
    """
    await websocket.accept()

    user = websocket.state.user.get("user")
    if user is None:
        logger.error("No user found in websocket state")
        await websocket.close()
        return
    # logger.info(f"💎 Connected user: {user.get('email')}")

    try:
        while True:
            # Receive text from client
            data = await websocket.receive_json()
            # logger.info(f"💎 Received data: {data}")
            event_type = data["event_type"]
            if event_type == EventType.SPEAK:
                await speak_event(websocket, data, user)
            else:
                logger.warning(f"Unknown event type: {event_type}")

    except ConnectionClosed:  # Changed from WebSocketDisconnect
        logger.info(f"Client disconnected: {user.get('email')}")
    except Exception as e:
        logger.error(f"Error for user {user.get('email')}: {str(e)}")
        logger.error(f"🔌 Traceback: {format_exc()}")
        await websocket.close()


# ============== for dashboard =================
@app.get("/text_entries/")
@require_auth
async def get_text_entries(request: Request):
    """
    Get all text entries for the current user
    """
    user = request.session.get("user")
    entries = get_user_text_entries(engine, user["sub"])
    return entries


@app.get("/tts_requests/")
@require_auth
async def get_tts_requests_api(request: Request):
    user = request.session.get("user")
    requests = get_tts_requests(engine, user["sub"])
    return requests
