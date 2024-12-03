import abc
from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi import Query
from authlib.integrations.starlette_client import OAuth
import uuid
import base64
from io import BytesIO
from websockets.exceptions import ConnectionClosed
from hashlib import md5
from traceback import format_exc

import spacy

from tts import to_speech
from constants import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, READLY_SECRET_KEY

from logger import logger
from session_manage import HTTPSSessionMiddleware, WebSocketAuthManager
from redis_cache import set_auth_user, get_auth_user


app = FastAPI()

# session management for both HTTP and WebSocket requests
app.add_middleware(HTTPSSessionMiddleware, secret_key=READLY_SECRET_KEY)
socket_auth_manager = WebSocketAuthManager(secret_key=READLY_SECRET_KEY)

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
async def read_root():
    return {"message": "Hello"}


@app.get("/my_profile")
async def my_profile(request: Request, user: dict = Depends(get_current_user)):
    """
    Return the current user's profile
    """
    user["token"] = request.cookies.get("session")[:20]
    return user


class EventType:
    SPEAK = "speak"


@app.post("/sentence_measure")
async def sentence_measure(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Cut the text into sentences
    """
    user_email = user.get("email")
    data = await request.json()
    if not data.get("text"):
        logger.warning(f"400 - {user_email} - No text provided")
        return JSONResponse(status_code=400, content={"error": "No text provided"})

    text = data["text"]
    sentences = []
    for sentence in sentence_tokenizer(text).sents:
        sentence_text = sentence.text
        if len(sentence_text.strip()) > 0:
            sentences.append(sentence_text)

    text_id = "text-" + md5(text.encode()).hexdigest()[:8]
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
    audio_bytes = to_speech(sentence_text)

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
