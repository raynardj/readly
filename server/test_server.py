from glow.colors import cprint
from tcp_server import Request, Response, JSONResponse, HTMLResponse, TCPServer
from datetime import datetime
import json


def run_test(test_name: str, test_func):
    """Helper function to run a test and print results"""
    try:
        test_func()
        cprint(f"✓ {test_name}", "green")
        return True
    except AssertionError as e:
        cprint(f"✗ {test_name}", "red")
        cprint(f"  → {str(e)}", "red")
        return False


def assert_equal(actual, expected, message=""):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected}, but got {actual}")


def assert_in(item, container, message=""):
    if item not in container:
        raise AssertionError(f"{message} Expected {item} to be in {container}")


def test_request():
    print("\n📋 Testing Request Parsing:")

    def test_basic_request():
        raw_request = "GET /path HTTP/1.1\r\n" "Host: localhost:8000\r\n" "User-Agent: Mozilla/5.0\r\n" "\r\n"
        request = Request(raw_request)
        assert_equal(request.method, "GET", "Method parsing failed")
        assert_equal(request.path, "/path", "Path parsing failed")
        assert_equal(request.headers["host"], "localhost:8000", "Header parsing failed")

    def test_query_params():
        raw_request = "GET /path?name=test&age=25 HTTP/1.1\r\n\r\n"
        request = Request(raw_request)
        assert_equal(request.query_params["name"], "test", "Query param parsing failed")
        assert_equal(request.query_params["age"], "25", "Query param parsing failed")

    def test_cookies():
        raw_request = "GET /path HTTP/1.1\r\n" "Cookie: session=abc123; user=john\r\n" "\r\n"
        request = Request(raw_request)
        assert_equal(request.cookies["session"], "abc123", "Cookie parsing failed")
        assert_equal(request.cookies["user"], "john", "Cookie parsing failed")

    run_test("Basic request parsing", test_basic_request)
    run_test("Query parameters parsing", test_query_params)
    run_test("Cookie parsing", test_cookies)


def test_response():
    print("\n📨 Testing Response Generation:")

    def test_basic_response():
        response = Response("Hello, World!")
        response_str = response.to_bytes().decode()
        assert_in("HTTP/1.1 200 OK", response_str, "Status line missing")
        assert_in("Content-Type: text/html", response_str, "Content-Type header missing")
        assert_in("Hello, World!", response_str, "Content missing")

    def test_json_response():
        data = {"message": "Hello"}
        response = JSONResponse(data)
        response_str = response.to_bytes().decode()
        assert_in("application/json", response_str, "JSON content type missing")
        assert_in(json.dumps(data), response_str, "JSON content missing")

    run_test("Basic response", test_basic_response)
    run_test("JSON response", test_json_response)


def test_server():
    print("\n🖥️  Testing TCP Server:")

    def test_route_registration():
        app = TCPServer(host="localhost", port=8000)

        @app.get("/test")
        def test_handler(request):
            return Response("Test")

        assert_in("/test", app.routes["GET"], "Route registration failed")
        assert_equal(app.routes["GET"]["/test"].__name__, "test_handler", "Handler registration failed")

    def test_multiple_routes():
        app = TCPServer()

        @app.get("/get-test")
        def get_handler(request):
            return Response("GET")

        @app.post("/post-test")
        def post_handler(request):
            return Response("POST")

        assert_in("/get-test", app.routes["GET"], "GET route registration failed")
        assert_in("/post-test", app.routes["POST"], "POST route registration failed")

    run_test("Route registration", test_route_registration)
    run_test("Multiple routes", test_multiple_routes)


def run_all_tests():
    cprint("\n🚀 Starting TCP Server Tests\n", "blue")

    test_request()
    test_response()
    test_server()

    cprint("\n✨ Tests completed!\n", "blue")


if __name__ == "__main__":
    run_all_tests()
