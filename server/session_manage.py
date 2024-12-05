from base64 import b64encode, b64decode
import json
import hmac
import hashlib
import functools
from typing import Any, Dict, Optional, Callable

from logger import logger
from redis_cache import set_auth_user, get_auth_user


def serialize_json(data: Dict[str, Any]) -> str:
    data_bytes = json.dumps(data).encode()
    return b64encode(data_bytes).decode()


def deserialize_json(data_b64: str) -> Dict[str, Any]:
    data_bytes = b64decode(data_b64)
    return json.loads(data_bytes)


def load_session(token: Optional[str], secret_key: bytes) -> Dict:
    """Load and verify session from cookie"""
    if not token:
        return {}

    try:
        # split token into data and signature
        data_b64, signature = token.split(".")
        expected_signature = create_signature(secret_key, data_b64)
        if not hmac.compare_digest(signature.encode(), expected_signature):
            return {}

        data = deserialize_json(data_b64)

        return data

    except (ValueError, json.JSONDecodeError):
        return {}


def create_signature(secret_key: bytes, data: str) -> bytes:
    """
    Create HMAC signature for data
    The signature contains the data and the secret key
    without the secret key, it is infeasible to tamper with the data
    """
    return (
        hmac.new(
            secret_key,
            data.encode(),
            hashlib.sha256,
        )
        .hexdigest()
        .encode()
    )


class HTTPSSessionMiddleware:
    def __init__(
        self,
        app,
        secret_key: str,
        session_cookie: str = "session",
        max_age: int = 15 * 24 * 60 * 60,  # 15 days
    ):
        self.app = app
        self.secret_key = secret_key.encode("utf-8")
        self.session_cookie = session_cookie
        self.max_age = max_age

    async def __call__(self, scope, receive, send):
        """Process the request through middleware"""
        if scope["type"] != "http":
            return

        session = scope.get("session", {})
        scope["session"] = session


class WebSocketAuthManager:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode("utf-8")

    def create_session_token(self, user_data: Dict) -> str:
        """
        Create a signed session token for WebSocket authentication
        """
        data_b64 = serialize_json(user_data)
        signature = create_signature(self.secret_key, data_b64)
        return f"{data_b64}.{signature.decode()}"

    # def set_cookie(self, response: Response, user_data: Dict) -> None:
    #     """Set the session cookie in the response"""
    #     token = self.create_session_token(user_data)
    #     response.set_cookie(
    #         key="ws_session",
    #         value=token,
    #         httponly=True,
    #         secure=True,
    #         samesite="lax",
    #     )

    def verify_session_token(self, token: str, sub: str) -> Dict[str, Any]:
        """
        Verify and decode a session token
        """
        user_data = get_auth_user(token)
        if not user_data:
            return {}
        if not user_data.get("user"):
            return {}
        if user_data["user"].get("sub") != sub:
            return {}
        return user_data

    async def auth_error_event(self, websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json({"event_type": "authentication_error"})
        await websocket.close()

    def auth(self, func: Callable) -> Callable:
        """
        Decorator to authenticate WebSocket requests
        """

        @functools.wraps(func)
        async def wrapper(websocket: WebSocket, *args, **kwargs):
            token = websocket.query_params.get("token")
            sub = websocket.query_params.get("sub")

            if not token:
                logger.error("No session token provided")
                await self.auth_error_event(websocket)
                return

            user_data = self.verify_session_token(token, sub)
            if not user_data:
                logger.error(f"Invalid session token: {token}")
                await self.auth_error_event(websocket)
                return

            websocket.state.user = user_data
            return await func(websocket, *args, **kwargs)

        return wrapper
