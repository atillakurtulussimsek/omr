import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "optik129_ornek01.jpg"
from tests.test_optik129 import EXPECTED

pytestmark = pytest.mark.skipif(not SAMPLE.is_file() or not EXPECTED, reason="örnek tarama / beklenen sonuç yok")


def testJobFlow(tmp_path, monkeypatch):
    monkeypatch.setattr("api.jobs.JOB_DIR", tmp_path)
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok"}
    with SAMPLE.open("rb") as f:
        job = client.post("/api/jobs", files=[("files", (SAMPLE.name, f, "image/jpeg"))]).json()
    for _ in range(100):
        job = client.get(f"/api/jobs/{job['id']}").json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert job["status"] == "done" and job["total"] == 1
    page = job["pages"][0]
    assert page["source"] == {"file": SAMPLE.name, "page": 1}
    assert page["fields"]["ogrenciNo"]["value"] == EXPECTED["ogrenciNo"]
    assert client.get(f"/api/jobs/{job['id']}/export.txt").text.startswith(f"{EXPECTED['ogrenciNo']} {EXPECTED['adSoyad']}")
    img = client.get(f"/api/jobs/{job['id']}/pages/0/annotated.jpg")
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8"
    assert client.get(f"/api/jobs/{job['id']}/annotated.zip").content[:2] == b"PK"
    assert client.get(f"/api/jobs/{job['id']}/pages/5/annotated.jpg").status_code == 404


def testRejectsUnsupported():
    r = TestClient(app).post("/api/jobs", files=[("files", ("a.exe", b"x", "application/octet-stream"))])
    assert r.status_code == 400
