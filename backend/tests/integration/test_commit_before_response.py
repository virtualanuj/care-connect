"""A client must be able to read what it just wrote.

If the request's transaction is committed *after* the response is sent, a fast follow-up request
(the UI opens the new appointment straight away) can run before the commit and see nothing. This
probes the database at the exact moment the response starts.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import get_engine
from tests.api_harness import ApiHarness
from tests.integration.test_appointments_api import Ctx, z

pytestmark = pytest.mark.integration


class ResponseStartProbe:
    """ASGI wrapper: when a POST /appointments response starts, count committed appointments."""

    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        self.app = app
        self.committed_when_response_started: list[int] = []

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        async def wrapped(message):  # type: ignore[no-untyped-def]
            is_booking = (
                scope["type"] == "http"
                and scope["method"] == "POST"
                and scope["path"].endswith("/appointments")
            )
            if message["type"] == "http.response.start" and is_booking:
                with get_engine().connect() as connection:
                    count = connection.execute(
                        text("SELECT count(*) FROM appointments")
                    ).scalar_one()
                self.committed_when_response_started.append(int(count))
            await send(message)

        await self.app(scope, receive, wrapped)


def test_a_booking_is_committed_before_its_response_starts(booking_harness: ApiHarness) -> None:
    ctx = Ctx(booking_harness)
    probe = ResponseStartProbe(booking_harness.app)
    ctx.c = TestClient(probe, raise_server_exceptions=False)  # same app, now observed

    response = ctx.book(ctx.asha, z(9, 0))

    assert response.status_code == 201
    assert probe.committed_when_response_started == [1]  # visible to other connections already
