from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_reader_routes_are_registered() -> None:
    routes = {route.path for route in app.routes}

    assert "/reader/materials" in routes
    assert "/reader/materials/import" in routes
    assert "/reader/api-config" in routes
    assert "/reader/api-config/test" in routes
    assert "/reader/materials/{course_id}" in routes
    assert "/reader/materials/{course_id}/index-status" in routes
    assert "/reader/pdf/{course_id}" in routes
    assert "/reader/markdown/{course_id}" in routes
    assert "/reader/markdown/{course_id}/index" in routes
    assert "/reader/markdown/{course_id}/pages/{page_number}" in routes
    assert "/reader/pages/{course_id}" in routes
    assert "/reader/pages/{course_id}/index" in routes
    assert "/reader/pages/{course_id}/pages/{page_number}" in routes
    assert "/reader/current-page/ask" in routes
    assert "/reader/selection/ask" in routes
    assert "/reader/selection/explain-code" in routes
    delete_routes = {(route.path, tuple(sorted(route.methods or []))) for route in app.routes}
    assert any(path == "/reader/materials/{course_id}" and "DELETE" in methods for path, methods in delete_routes)
    assert any(path == "/reader/markdown/{course_id}/pages/{page_number}" and "PUT" in methods for path, methods in delete_routes)


def test_reader_materials_returns_list() -> None:
    client = TestClient(app)

    response = client.get("/reader/materials")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_reader_pdf_unknown_course_returns_404() -> None:
    client = TestClient(app)

    response = client.get("/reader/pdf/unknown_course")

    assert response.status_code == 404
