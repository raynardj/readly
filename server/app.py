import abc

# from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket
# from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
# from fastapi import Query

from authlib.integrations.starlette_client import OAuth
import base64
from websockets.exceptions import ConnectionClosed
from traceback import format_exc
import asyncio

import spacy

from tts import to_speech
from constants import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, READLY_SECRET_KEY

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

# from session_manage import HTTPSSessionMiddleware, WebSocketAuthManager
from sql_data import build_engine
from crud_data import (
    create_text_entry,
    get_text_entry,
    get_user_text_entries,
    user_login,
    create_tts_request,
    get_tts_requests,
    object_to_dict,
)

import time

app = TCPServer()

app.use(JWT, secret_key=READLY_SECRET_KEY)

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


def await_coroutine(coroutine):
    """
    Helper function to await a coroutine in a synchronous context
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(coroutine)
        return result
    except Exception as e:
        logger.error(f"🔌 Traceback: {format_exc()}")
        logger.error(f"Error in await_coroutine: {str(e)}")
        return None


@app.get("/login")
def login(request: Request):
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
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    # hd = request.query_params.get("hd")
    # prompt = request.query_params.get("prompt")
    print(
        {
            "code": code,
            "state": state,
        }
    )

    try:
        token = await_coroutine(oauth.google.authorize_access_token(request))
        userinfo = await_coroutine(oauth.google.userinfo(token=token))
    except Exception as e:
        logger.error(f"🔌 Traceback: {format_exc()}")
        logger.error(f"Auth error: {str(e)}")
        raise

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
    extension_id = request.query_params.get("extension_id")
    key = request.query_params.get("key")
    if key is None:
        return RedirectResponse(url=f"chrome-extension://{extension_id}/profile.html")
    else:
        return RedirectResponse(url=f"chrome-extension://{extension_id}/read.html?key={key}")


@app.get("/close_window")
def close_window(request: Request):
    return HTMLResponse(content="<script>window.close();</script>")


def get_current_user(request: Request):
    userinfo = request.session.get("user")
    return userinfo


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    extension_id = request.query_params.get("extension_id")
    if extension_id is None:
        return RedirectResponse(url=f"{request.base_url}/login")
    else:
        return RedirectResponse(url=f"{request.base_url}/login?extension_id={extension_id}")


@app.get("/")
@require_auth
def read_root():
    return {"message": "Hello"}


@app.get("/my_profile")
@require_auth
def my_profile(request: Request):
    """
    Return the current user's profile
    """
    user = request.session.get("user")
    user["token"] = request.cookies.get("session")[:20]
    return JSONResponse(user)


class EventType:
    SPEAK = "speak"


@app.post("/text_entry/create/")
def text_entry_create(
    request: Request,
):
    """
    Create a new text entry
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
    Cut the text into sentences
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


# async def speak_event(
#     websocket: WebSocket,
#     data: dict,
#     user: dict,
# ):
#     """
#     Handle the speak event
#     """
#     text_data = data["text_data"]
#     sentences = text_data["sentences"]
#     text_id = text_data["text_id"]

#     # my decision is not to set the speed here but use the default one
#     # on frontend, the speed is controlled by the slider
#     # speed: float = data.get("speed", 1.0)
#     speed = 1.0
#     play_idx = data.get("play_idx", 0)
#     sentence_text = sentences[play_idx]

#     audio_id = f"{text_id}-{play_idx:03d}"
#     email = user.get("email")
#     logger.info(f"⭐️ <{email}> : {audio_id}")
#     start_time = time.time()
#     audio_bytes = to_speech(sentence_text)
#     processing_time_ms = int((time.time() - start_time) * 1000)

#     # We need to keep track of the TTS requests
#     # Like the number of requests, the total characters, and the average processing time
#     create_tts_request(
#         engine,
#         text_entry_id=text_id,
#         user_sub=user["sub"],
#         sentence_text=sentence_text,
#         sentence_index=play_idx,
#         audio_id=audio_id,
#         character_count=len(sentence_text),
#         processing_time_ms=processing_time_ms,
#     )

#     await websocket.send_json(
#         {
#             "event_type": "audio_chunk",
#             "audio_id": audio_id,
#             "play_idx": play_idx,
#             "speed": speed,
#             "data": base64.b64encode(audio_bytes).decode("utf-8"),
#         }
#     )


# @app.websocket("/speak")
# @socket_auth_manager.auth
# async def text_to_speech_socket(websocket: WebSocket):
#     """
#     WebSocket endpoint for text-to-speech streaming
#     """
#     await websocket.accept()

#     user = websocket.state.user.get("user")
#     if user is None:
#         logger.error("No user found in websocket state")
#         await websocket.close()
#         return
#     # logger.info(f"💎 Connected user: {user.get('email')}")

#     try:
#         while True:
#             # Receive text from client
#             data = await websocket.receive_json()
#             # logger.info(f"💎 Received data: {data}")
#             event_type = data["event_type"]
#             if event_type == EventType.SPEAK:
#                 await speak_event(websocket, data, user)
#             else:
#                 logger.warning(f"Unknown event type: {event_type}")

#     except ConnectionClosed:  # Changed from WebSocketDisconnect
#         logger.info(f"Client disconnected: {user.get('email')}")
#     except Exception as e:
#         logger.error(f"Error for user {user.get('email')}: {str(e)}")
#         logger.error(f"🔌 Traceback: {format_exc()}")
#         await websocket.close()


# # ============== for dashboard =================
@app.get("/text_entries/")
@require_auth
def get_text_entries(request: Request):
    """
    Get all text entries for the current user
    """
    user = request.session.get("user")
    entries = get_user_text_entries(engine, user["sub"])

    return JSONResponse(entries)


# @app.get("/tts_requests/")
# @require_auth
# async def get_tts_requests_api(request: Request):
#     user = request.session.get("user")
#     requests = get_tts_requests(engine, user["sub"])
#     return requests


if __name__ == "__main__":
    app.run(logger_level="DEBUG", cert_file="cert.pem", key_file="key.pem")
