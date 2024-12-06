from tcp_server import Request, Response
import socket

PROTOCAL = "https"
PORT = 8000
HOST = "localhost"

test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def raw_to_raw(
    input_data: str,
) -> str:
    test_socket.sendall(input_data.encode())
    return test_socket.recv(1024).decode()


def test_naked_endpoint():
    raw_to_raw(f"GET /naked HTTP/1.1\r\nHost: {HOST}:{PORT}\r\n\r\n")
