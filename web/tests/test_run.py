import socket
from contextlib import closing


def test_find_available_port_skips_busy_port():
    from web.run import find_available_port

    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        busy_port = int(sock.getsockname()[1])

        selected = find_available_port("127.0.0.1", busy_port, max_tries=5)

    assert selected != busy_port
    assert selected > busy_port


def test_display_host_uses_loopback_for_wildcard_bind():
    from web.run import display_host

    assert display_host("0.0.0.0") == "127.0.0.1"
    assert display_host("127.0.0.1") == "127.0.0.1"

