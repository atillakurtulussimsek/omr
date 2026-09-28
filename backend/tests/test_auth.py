import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app


def testOpenWithoutPassword(monkeypatch):
    monkeypatch.setattr(auth, "ADMIN_PASSWORD", "")
    client = TestClient(app)
    assert client.get("/api/auth").json() == {"required": False, "authenticated": True}
    assert client.get("/api/forms").status_code == 200


def testProtectedWithPassword(monkeypatch):
    monkeypatch.setattr(auth, "ADMIN_PASSWORD", "gizli123")
    monkeypatch.setattr(auth, "failures", {})
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/forms").status_code == 401
    assert client.get("/api/auth").json() == {"required": True, "authenticated": False}
    assert client.post("/api/auth/login", json={"password": "yanlis"}).status_code == 401
    r = client.post("/api/auth/login", json={"password": "gizli123"})
    assert r.status_code == 200 and auth.COOKIE in r.cookies
    assert client.get("/api/forms").status_code == 200
    assert client.get("/api/auth").json()["authenticated"]
    client.post("/api/auth/logout")
    assert client.get("/api/forms").status_code == 401


def testLockout(monkeypatch):
    monkeypatch.setattr(auth, "ADMIN_PASSWORD", "gizli123")
    monkeypatch.setattr(auth, "failures", {})
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    client = TestClient(app)
    for _ in range(auth.MAX_FAILURES):
        assert client.post("/api/auth/login", json={"password": "x"}).status_code == 401
    assert client.post("/api/auth/login", json={"password": "gizli123"}).status_code == 429
