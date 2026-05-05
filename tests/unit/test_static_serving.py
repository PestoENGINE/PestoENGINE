"""Unit tests for static file serving auto-detection."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.main import _mount_ui


def test_index_served_when_dist_exists(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SPA</html>")

    fresh_app = FastAPI()
    _mount_ui(fresh_app, dist)

    with TestClient(fresh_app) as client:
        res = client.get("/")
    assert res.status_code == 200
    assert "<html>SPA</html>" in res.text


def test_root_404_when_dist_missing(tmp_path):
    fresh_app = FastAPI()
    _mount_ui(fresh_app, tmp_path / "nonexistent")

    with TestClient(fresh_app) as client:
        res = client.get("/")
    assert res.status_code == 404


def test_api_takes_priority_over_static(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SPA</html>")

    fresh_app = FastAPI()

    @fresh_app.get("/v1/test")
    async def _api():
        return JSONResponse({"ok": True})

    _mount_ui(fresh_app, dist)

    with TestClient(fresh_app) as client:
        api_res = client.get("/v1/test")
        root_res = client.get("/")

    assert api_res.status_code == 200
    assert api_res.json() == {"ok": True}
    assert root_res.status_code == 200
    assert "<html>SPA</html>" in root_res.text


def test_static_asset_served(tmp_path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html>SPA</html>")
    (assets / "app.js").write_text("console.log('hi')")

    fresh_app = FastAPI()
    _mount_ui(fresh_app, dist)

    with TestClient(fresh_app) as client:
        res = client.get("/assets/app.js")
    assert res.status_code == 200
    assert "console.log" in res.text


def test_unknown_route_returns_404_when_dist_exists(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SPA</html>")

    fresh_app = FastAPI()
    _mount_ui(fresh_app, dist)

    with TestClient(fresh_app) as client:
        res = client.get("/some-client-side-route")
    assert res.status_code == 404
