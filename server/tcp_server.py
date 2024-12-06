"""
TCP Server for Readly

This is the CORE part of the code I want to focus on for CS560 Mastery

The structure of this file is fairly straight forward

So bytes come in to the server and bytes go out from the server

Those these bytes(when turned to strings) contain many pieces of information we need.

So `Request` is to manage the parsing of the bytes into a more usable object. Store many informations into the object.

And `Response` is to manage the conversion of the return value of the handler into bytes.

TCPServer is a contineously running server that listen to the incoming requests and send out responses.
It's to simulate usual python web frameworks like Flask or FastAPI.

JWT is the middleware that manages the session for authenticated user and work with google oauth.
"""

import socket
import ssl
from typing import Callable, Dict, List, Optional, Any, Union
import json
from datetime import datetime
from urllib.parse import parse_qs
import traceback as tb
import threading

from logger import logger
from jwt_utils import (
    serialize_json,
    create_signature,
    load_session,
)

# Vanilla Request class


class Request:
    """
    A class to parse the raw request string into a Request object
    """

    def __init__(self, raw_request: str):
        """
        Parse the raw request string into a Request object

        This is just a coding syntax that we can have easy access to the many meta
        info/body data for the request packet
        """
        self.headers: Dict[str, str] = {}
        self.method: str = ""
        self.path: str = ""
        self.body: str = ""
        self.cookies: Dict[str, str] = {}
        self.query_params: Dict[str, str] = {}
        self.session: Dict[str, Any] = {}
        self.base_url: str = ""
        self._parse_request(raw_request)

    def _parse_request(self, raw_request: str):
        """
        Parse the raw request string into a Request object
        """
        logger.debug(f"[RAW REQUEST]: {raw_request}")
        lines = raw_request.split("\r\n")
        if not lines:
            return
        logger.debug(f"[LINE 0]:{lines[0]}")
        method, path, _ = lines[0].split(" ")
        self.method = method

        if "?" in path:
            self.path, query = path.split("?", 1)
            _query_params = parse_qs(query)
            # parsed query params are list of strings under each key
            # mostly we only have one value for each key, so we set up
            # params as a dictionary with the first value of each key
            self.query_params = {k: v[0] if v else "" for k, v in _query_params.items()}
            if len(self.query_params) > 0:
                logger.debug(f"[🔍 PARSED QUERY PARAMS]: {self.query_params}")
        else:
            self.path = path

        idx = 1
        while idx < len(lines) and lines[idx]:
            if ": " in lines[idx]:
                logger.debug(f"[LINE {idx} ':']: {str(lines[idx])[:200]}")
                key, value = lines[idx].split(": ", 1)
                self.headers[key.lower()] = value
                if key.lower() == "cookie":
                    logger.debug(f"[LINE {idx} 'cookie']: {value[:20]}...")
                    self._parse_cookies(value)
            idx += 1

        if idx < len(lines):
            logger.debug(f"[LINE {idx} 'body']: {len(lines[idx + 1:])} lines, {str(lines[idx + 1:])[:20]}")
            self.body = "\n".join(lines[idx + 1 :])

    def _parse_cookies(self, cookie_string: str):
        for cookie in cookie_string.split("; "):
            if "=" in cookie:
                key, value = cookie.split("=", 1)
                self.cookies[key] = value
        if len(self.cookies) > 0:
            logger.debug(f"[🍪 PARSED COOKIES]: keys: {self.cookies.keys()}")

    def json(self) -> Dict[str, Any]:
        """
        Parse the body as JSON format data
        We'll get a dictionary object
        """
        try:
            return json.loads(self.body)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {self.body}")
            return {}


# Vanilla Response class


class Response:
    def __init__(self, content: str = "", status: int = 200, content_type: str = "text/html"):
        self.content = content
        self.status = status
        self.headers: Dict[str, str] = {
            "Content-Type": content_type,
            "Date": datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT"),
        }
        self.cookies: Dict[str, str] = {}
        self.base_url: str = ""

    def set_cookie(self, key: str, value: str):
        self.cookies[key] = value

    def to_bytes(self) -> bytes:
        status_text = {200: "OK", 404: "Not Found", 500: "Internal Server Error"}.get(self.status, "")

        headers = [f"HTTP/1.1 {self.status} {status_text}"]

        for key, value in self.headers.items():
            headers.append(f"{key}: {value}")

        for key, value in self.cookies.items():
            # logger.debug(f"Set-Cookie: {key}={value}")
            headers.append(f"Set-Cookie: {key}={value}")

        response = "\r\n".join(headers) + "\r\n\r\n" + self.content
        return response.encode()


class JSONResponse(Response):
    """
    An inherited class from Response to return a JSON response
    """

    def __init__(self, content: Union[Dict[str, Any], Any], status: int = 200):
        super().__init__(json.dumps(content), status, "application/json")


class RedirectResponse(Response):
    """
    An inherited class from Response to return a redirect response
    """

    def __init__(self, url: str, status: int = 302):
        super().__init__("", status, "text/html")
        self.headers["Location"] = url


class HTMLResponse(Response):
    """
    An inherited class from Response to return an HTML response
    """

    def __init__(self, content: str, status: int = 200):
        super().__init__(content, status, "text/html")


def require_auth(func):
    """
    A decorator to check if the user is authenticated.
    It simulates the usual python network frameworks' practice
    For example, we can do
    @app.get("/")
    @require_auth
    def home(request: Request):
        return Response("Hello, World!")
    """

    def wrapper(request: Request, *args, **kwargs):
        if "user" not in request.session:
            logger.error("Unauthorized Visit")
            logger.error(f"Session: {request.session}")
            logger.error(f"Cookies:")
            for key, value in request.cookies.items():
                logger.error(f"{key}: {str(value)[:20]}...")

            response = JSONResponse({"error": "Unauthorized"}, status=401)
            response.set_cookie("session", "")
            return response
        user = request.session["user"]
        logger.debug(f"Authorized Visit: {user}")
        return func(request, *args, **kwargs)

    wrapper.__name__ = func.__name__

    return wrapper


class TCPServer:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        ssl_context: Optional[ssl.SSLContext] = None,
        n_workers: int = 2,
    ):
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.n_workers = n_workers
        # let's settle for GET and POST for now
        # ignore other methods (eg. PUT, DELETE, etc.)
        self.routes: Dict[str, Dict[str, Callable]] = {
            "GET": {},
            "POST": {},
        }
        self.middlewares: List[Callable] = []
        self.jwt: Optional[JWT] = None

    def use(self, middleware: Callable, **kwargs):
        """
        Add a middleware to the server
        When initialized,
        the middleware will be called with the server instance and other keyword arguments
        """
        middleware_obj = middleware(self, **kwargs)
        self.middlewares.append(middleware_obj)
        if isinstance(middleware_obj, JWT):
            logger.debug("JWT middleware detected")
            self.jwt = middleware_obj

    def get(self, path: str):
        """
        Decorate a function to be a GET handler for the given path
        """

        def decorator(handler: Callable):
            self.routes["GET"][path] = handler
            return handler

        return decorator

    def post(self, path: str):
        """
        Decorate a function to be a POST handler for the given path
        """

        def decorator(handler: Callable):
            self.routes["POST"][path] = handler
            return handler

        return decorator

    def _receive_request(self, client_socket: socket.socket) -> Request:
        """
        Receive the request from the client socket

        This code is to break the raw request into header and body
        And depends on the `Content-Length` header to determine the end of the body
        So we're sure we get the whole request.

        There is some header extraction logic here, but the main header extraction
        is done in the Request object. Might be some room for optimization here.
        """
        header_data = b""
        while b"\r\n\r\n" not in header_data:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            header_data += chunk

        header_part, body_part = header_data.split(b"\r\n\r\n", 1)
        headers_text = header_part.decode()
        content_length = 0
        for line in headers_text.split("\r\n"):
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":")[1].strip())
                break

        body_data = body_part
        remaining = content_length - len(body_part)
        while remaining > 0:
            chunk = client_socket.recv(min(remaining, 4096))
            if not chunk:
                break
            body_data += chunk
            remaining -= len(chunk)

        full_data = header_part + b"\r\n\r\n" + body_data

        return Request(full_data.decode())

    def _handle_request(self, client_socket: socket.socket):
        if self.ssl_context:
            try:
                client_socket = self.ssl_context.wrap_socket(client_socket, server_side=True)
            except ssl.SSLError as e:
                logger.error(f"HTTPS/ SSL: {e}")
                client_socket.close()
                return None

        request: Request = self._receive_request(client_socket)

        if self.jwt is not None:
            request.session = self.jwt._load_session(request)
            logger.debug(f"Loaded session: {request.session}")

        if "host" in request.headers:
            host = request.headers["host"]

            request.base_url = f"{self.protocol}://{host}"

        handler = self.routes.get(request.method, {}).get(request.path)
        if handler:
            for middleware in self.middlewares:
                handler = middleware(handler)
            try:
                response = handler(request)
            except Exception as e:
                logger.error(tb.format_exc())
                response = Response(f"500 Internal Server Error: {str(e)}", status=500)
        else:
            logger.error(f"No handler found for {request.method} {request.path}")
            response = Response("404 Not Found", status=404)
        response_bytes: bytes = response.to_bytes()
        client_socket.send(response_bytes)
        logger.info(f"[{request.method}]{response.status} : {request.path}")
        client_socket.close()

    def _worker(self):
        """Worker thread to handle client connections"""
        while True:
            try:
                client_socket, _ = self.server_socket.accept()
                self._handle_request(client_socket)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                logger.error(tb.format_exc())

    def run(
        self,
        logger_level: str = "INFO",
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
    ):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if cert_file and key_file:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
            protocol = "https"
        else:
            protocol = "http"
        self.protocol = protocol

        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        logger.setLevel(logger_level)
        logger.info("Readly TCP Server for CS560 Mastery")
        logger.info(f"Server running on {protocol}://{self.host}:{self.port}")

        logger.info(f"Routes:")

        for method, routes in self.routes.items():
            for path, handler in routes.items():
                logger.info(f"{method} {path}: {handler.__name__}")

        # Create worker threads
        workers = []
        for i in range(self.n_workers):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            workers.append(worker)
            logger.info(f"Started worker thread {i+1}")

        # Keep main thread alive
        try:
            for worker in workers:
                worker.join()
        except KeyboardInterrupt:
            logger.info("Shutting down server...")
            self.server_socket.close()


class JWT:
    """
    JWT middleware to handle session
    JWT (JSON Web Token) is used to cache the authentication effort
    Eg. we use token in the cookie to avoid re-authenticating the user through google oauth
    """

    def __init__(
        self,
        server: TCPServer,
        secret_key: str,
        session_key_name: str = "session",
    ):
        self.server: TCPServer = server
        self.secret_key: str = secret_key
        self.session_key_name: str = session_key_name

    def _load_session(self, request: Request) -> Dict:
        """Load and verify session from cookie"""
        cookie = request.cookies.get(self.session_key_name)
        return load_session(cookie, self.secret_key.encode("utf-8"))

    def delete_session(self, response: Response) -> None:
        response.set_cookie(self.session_key_name, "")

    def save_session(self, session: Dict, response: Response) -> None:
        """Save session data to cookie"""
        if not session:
            self.delete_session(response)
            return

        data_b64 = serialize_json(session)
        signature = create_signature(self.secret_key.encode("utf-8"), data_b64)
        cookie_value = f"{data_b64}.{signature.decode()}"
        logger.debug(f"set cookie: {cookie_value[:20]}")

        response.set_cookie(
            key=self.session_key_name,
            value=cookie_value,
        )

    def __call__(self, callback: Callable) -> Callable:
        """
        Create a middleware wrapper to handle session
        """

        def wrapper(request: Request) -> Response:
            """
            Middleware wrapper to handle session
            """
            session = self._load_session(request)
            request.session = session

            response = callback(request)
            self.save_session(request.session, response)
            return response

        wrapper.__name__ = callback.__name__

        return wrapper


if __name__ == "__main__":
    app = TCPServer()

    @app.get("/")
    def home(request: Request) -> Response:
        return Response("This is a tcp server")

    @app.get("/hello")
    def hello(request: Request) -> Response:
        name = request.query_params.get("name", ["World"])[0]
        response = Response(f"Hello, {name}!")
        response.set_cookie("last_visit", datetime.now().isoformat())
        return response

    @app.post("/echo")
    def echo(request: Request) -> Response:
        data = json.loads(request.body)
        return JSONResponse(data)

    app.run(logger_level="DEBUG", cert_file="cert.pem", key_file="key.pem")
