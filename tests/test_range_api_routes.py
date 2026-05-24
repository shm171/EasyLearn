from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_range_routes_are_registered() -> None:
    routes = {route.path for route in app.routes}

    assert "/range/ask" in routes
    assert "/range/summary" in routes
    assert "/range/quiz" in routes
    assert "/range/key-points" in routes


def test_range_ask_validates_reversed_page_range_before_service_call() -> None:
    client = TestClient(app)

    response = client.post(
        "/range/ask",
        json={
            "course_id": "python_001",
            "question": "这一部分讲了什么？",
            "page_start": 5,
            "page_end": 1,
        },
    )

    assert response.status_code == 400
    assert "page_start cannot be greater" in response.text
