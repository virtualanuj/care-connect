from collections.abc import Iterator

import pytest
from pytest_socket import disable_socket, enable_socket


@pytest.fixture(autouse=True)
def block_network() -> Iterator[None]:
    """Unit and contract tests may not open network sockets.

    Unix sockets stay allowed because asyncio uses socketpair().
    """
    disable_socket(allow_unix_socket=True)
    yield
    enable_socket()
