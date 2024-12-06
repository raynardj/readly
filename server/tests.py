from tcp_server import Request, Response
import socket
from json import dumps
import concurrent.futures
from typing import Optional
from datetime import datetime
import pandas as pd

# I'm using very popular httpx as the client to test the server
# it's a good measure to test the server, to see if the server is up to the standard of HTTP protocol
import httpx

from glow.colors import cprint

PROTOCOL = "https"
PORT = 8000
HOST = "localhost"

test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

STATUS_CODES = {
    200: "OK (the request was SUCCESSFUL)",
    302: "Found (REDIRECT to a different URL)",
    401: "Unauthorized (the user is NOT authorized)",
    404: "Not Found (the resource was NOT found)",
    405: "Method Not Allowed (the method is NOT allowed for the requested resource)",
    500: "Internal Server Error (the server encountered an ERROR while processing the request)",
}


def response_to_raw(response: httpx.Response) -> str:
    """
    Return in the format of HTTP response
    Print as much detail from other network layers as possible
    """
    # Build the raw HTTP response string
    raw_response = f"HTTP/{response.http_version} {response.status_code} {response.reason_phrase}\r\n"

    for name, value in response.headers.items():
        raw_response += f"{name}: {value}\r\n"
    raw_response += "\r\n"
    raw_response += response.text

    return raw_response


USUAL_HEADERS = {
    "Host": "localhost:8000",
    "Connection": "keep-alive",
    "sec-ch-ua": '"Not;A=Brand";v="24", "Chromium";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
}


def client_core(method, path, headers=None, json=None):
    client = httpx.Client(verify=False, cert=("cert.pem", "key.pem"))
    url = f"{PROTOCOL}://{HOST}:{PORT}{path}"
    response = client.request(method, url, headers=headers, json=json)
    return response


def test_endpoint(path, method, headers=None, json=None):
    cprint("================ REQUEST ================", "header")
    cprint(f"[{method}] '{path}'", "header")
    if headers is not None:
        for key, value in headers.items():
            cprint(f"{key}: {value}", "header")

    if json is not None:
        print()
        cprint("BODY DATA", "header")
        cprint(dumps(json, indent=4), "header")

    response = client_core(method, path, headers, json)

    cprint("================ RESPONSE ================", "green")
    cprint(f"STATUS: {response.status_code}: {STATUS_CODES[response.status_code]}", "green")
    cprint("\nRAW RESPONSE:", "green")
    cprint(response_to_raw(response), "green")
    print()
    return response


LOGOUT_HEADER = dict(
    **USUAL_HEADERS,
    Cookie="_xsrf=2|e8ec40bb|be67f97ce63626c0817f331d876587e5|1719595733; session=eyJ1c2VyIjogeyJzdWIiOiAiMTEyMjA4MjUzNzk3MTM1ODU1NDY4IiwgIm5hbWUiOiAiWGlhb2NoZW4gWmhhbmciLCAiZ2l2ZW5fbmFtZSI6ICJYaWFvY2hlbiIsICJmYW1pbHlfbmFtZSI6ICJaaGFuZyIsICJwaWN0dXJlIjogImh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0xPa2FaTFlFZlAtY2pjN1JTMnVQQU9vYURUc2k5Q0xpNmZLME9fNGJFWnU3bFRCMzQ9czk2LWMiLCAiZW1haWwiOiAieHozODdAbmF1LmVkdSIsICJlbWFpbF92ZXJpZmllZCI6IHRydWUsICJoZCI6ICJuYXUuZWR1IiwgInRva2VuIjogImV5SjFjMlZ5SWpvZ2V5SnpkV0lpIn0sICJfc3RhdGVfZ29vZ2xlXzVtTmRuT0VKWG0ycm1OSmlxcmJ4ZzM2ak1OMWtmNCI6IHsiZGF0YSI6IHsicmVkaXJlY3RfdXJpIjogImh0dHBzOi8vbG9jYWxob3N0OjgwMDAvYXV0aD9leHRlbnNpb25faWQ9Z2JjbWJvcHBiYmZqaGRwbGltam5kbmtoYmplb2xiamkiLCAibm9uY2UiOiAiMTBvMXFtdFZaY1d3YVFqU0hhUVgiLCAidXJsIjogImh0dHBzOi8vYWNjb3VudHMuZ29vZ2xlLmNvbS9vL29hdXRoMi92Mi9hdXRoP3Jlc3BvbnNlX3R5cGU9Y29kZSZjbGllbnRfaWQ9MjIwNDU4OTY2MjQ0LWxvbzdwajdxMmRpYnU0dTBmYmdwczZxbTg0NjZpZG9tLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tJnJlZGlyZWN0X3VyaT1odHRwcyUzQSUyRiUyRmxvY2FsaG9zdCUzQTgwMDAlMkZhdXRoJTNGZXh0ZW5zaW9uX2lkJTNEZ2JjbWJvcHBiYmZqaGRwbGltam5kbmtoYmplb2xiamkmc2NvcGU9b3BlbmlkK2VtYWlsK3Byb2ZpbGUmc3RhdGU9NW1OZG5PRUpYbTJybU5KaXFyYnhnMzZqTU4xa2Y0Jm5vbmNlPTEwbzFxbXRWWmNXd2FRalNIYVFYIn0sICJleHAiOiAxNzMzNDU4NTE2LjQ0NjE4NDl9fQ==.0ad325a3a8a407a804919af7bffe35d3fdb9816f06ee376d110cedde1effb7ad",
)

LOGIN_HEADER = dict(
    **USUAL_HEADERS,
    Cookie="_xsrf=2|e8ec40bb|be67f97ce63626c0817f331d876587e5|1719595733; session=",
)

AUTH_HEADER = dict(
    **USUAL_HEADERS,
    Cookie="_xsrf=2|e8ec40bb|be67f97ce63626c0817f331d876587e5|1719595733; session=eyJ1c2VyIjogeyJzdWIiOiAiMTEyMjA4MjUzNzk3MTM1ODU1NDY4IiwgIm5hbWUiOiAiWGlhb2NoZW4gWmhhbmciLCAiZ2l2ZW5fbmFtZSI6ICJYaWFvY2hlbiIsICJmYW1pbHlfbmFtZSI6ICJaaGFuZyIsICJwaWN0dXJlIjogImh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0xPa2FaTFlFZlAtY2pjN1JTMnVQQU9vYURUc2k5Q0xpNmZLME9fNGJFWnU3bFRCMzQ9czk2LWMiLCAiZW1haWwiOiAieHozODdAbmF1LmVkdSIsICJlbWFpbF92ZXJpZmllZCI6IHRydWUsICJoZCI6ICJuYXUuZWR1In19.101086856aac8d049f71f21941f0f0bb7b78aa5415bde84cb93f3de339cdb378",
)

AUTH_LINK = "/auth?extension_id=gbcmboppbbfjhdplimjndnkhbjeolbji&state=51gZK0gvP8cvhjuO0m2nty3nkSIUy9&code=4%2F0AeanS0bvEfVN5JHHzmCFxCjoW05Msq5TwNRFBoka-tIbxoCa27ebMDw53PZf9YyD8yDaAw&scope=email+profile+openid+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.profile+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email&authuser=0&hd=nau.edu&prompt=consent"

AUTHORIZED_HEADER = dict(
    **USUAL_HEADERS,
    Cookie="_xsrf=2|e8ec40bb|be67f97ce63626c0817f331d876587e5|1719595733; session=eyJ1c2VyIjogeyJzdWIiOiAiMTEyMjA4MjUzNzk3MTM1ODU1NDY4IiwgIm5hbWUiOiAiWGlhb2NoZW4gWmhhbmciLCAiZ2l2ZW5fbmFtZSI6ICJYaWFvY2hlbiIsICJmYW1pbHlfbmFtZSI6ICJaaGFuZyIsICJwaWN0dXJlIjogImh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0xPa2FaTFlFZlAtY2pjN1JTMnVQQU9vYURUc2k5Q0xpNmZLME9fNGJFWnU3bFRCMzQ9czk2LWMiLCAiZW1haWwiOiAieHozODdAbmF1LmVkdSIsICJlbWFpbF92ZXJpZmllZCI6IHRydWUsICJoZCI6ICJuYXUuZWR1In19.101086856aac8d049f71f21941f0f0bb7b78aa5415bde84cb93f3de339cdb378",
)

WRONG_TOKEN_HEADER = dict(
    **USUAL_HEADERS,
    Cookie="_xsrf=2|e8ec40bb|be67f97ce63626c0817f331d876587e5|1719595733; session=lifeIsLikeaBoxOfChocolates",
)

cprint("TESTING ENDPOINTS", "header")
cprint("Unprotected endpoints", "blue")
response = test_endpoint("/naked", "GET")
assert response.status_code == 200
assert len(response.json()) == 1

cprint("Logout", "blue")
response = test_endpoint("/logout", "GET", headers=LOGOUT_HEADER)
assert response.status_code == 302

cprint("Unauthorized endpoints", "blue")
response = test_endpoint("/my_profile", "GET")
assert response.status_code == 401

cprint("Login", "blue")
response = test_endpoint("/login?extension_id=gbcmboppbbfjhdplimjndnkhbjeolbji", "GET", headers=LOGIN_HEADER)
assert response.status_code == 302

cprint("Authorized endpoints, the user information is recovered from the JWT", "blue")
response = test_endpoint("/my_profile", "GET", headers=AUTHORIZED_HEADER)
assert response.status_code == 200

cprint("Correct return body", "blue")
data = response.json()
assert data["email"] == "xz387@nau.edu"
assert data["name"] == "Xiaochen Zhang"

cprint("Wrong token to test if the JWT can deny the unauthorized user", "blue")
response = test_endpoint(
    "/my_profile",
    "GET",
    headers=WRONG_TOKEN_HEADER,
)
assert response.status_code == 401

cprint("Path not found", "blue")
response = test_endpoint("/our_profiles", "GET", headers=AUTHORIZED_HEADER)
assert response.status_code == 404


cprint("Post request, that means correct request body parsing, different method than GET", "blue")
response = test_endpoint("/sentence_measure/", "POST", headers=AUTHORIZED_HEADER, json={"text_id": "readly_2775ecb6"})
assert response.status_code == 200

cprint("Test if the server can handle concurrent connections", "blue")


def in_concurrent_requesting(
    start_time: datetime,  # pass in from concurrent_requesting
    method: str,
    path: str,
    headers: Optional[dict] = None,
    json: Optional[dict] = None,
):
    thread_start = (datetime.now() - start_time).total_seconds()
    response = client_core(method, path, headers, json)
    thread_end = (datetime.now() - start_time).total_seconds()
    return {
        "status_code": response.status_code,
        "text_id": response.json()["text_id"],
        "start": thread_start,
        "end": thread_end,
        "round_trip_time": thread_end - thread_start,
    }


def concurrent_requesting(
    n_requests: int,
    n_threads: int,
    method: str,
    path: str,
    headers: Optional[dict] = None,
    json: Optional[dict] = None,
):
    start_time = datetime.now()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = [
            executor.submit(
                in_concurrent_requesting,
                start_time,
                method,
                path,
                headers,
                json,
            )
            for _ in range(n_requests)
        ]
        df = pd.DataFrame(list(f.result() for f in concurrent.futures.as_completed(futures)))
    return df


df = concurrent_requesting(
    10, 10, "POST", "/sentence_measure/", headers=AUTHORIZED_HEADER, json={"text_id": "readly_2775ecb6"}
)
print(df)
