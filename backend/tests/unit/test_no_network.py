import socket

import pytest
from pytest_socket import SocketBlockedError


def test_unit_tests_cannot_open_tcp_connections() -> None:
    with pytest.raises(SocketBlockedError), socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("127.0.0.1", 5432))
