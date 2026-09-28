from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "optik129_ornek01.jpg"
from tests.test_optik129 import EXPECTED

pytestmark = pytest.mark.skipif(not SAMPLE.is_file() or not EXPECTED, reason="örnek tarama / beklenen sonuç yok")
client = TestClient(app)


def upload(url, **data):
    with SAMPLE.open("rb") as f:
        return client.post(url, data=data, files={"file": (SAMPLE.name, f, "image/jpeg")})


def testBuiltinListed():
    forms = client.get("/api/forms").json()
    assert "optik129" in [f["id"] for f in forms]
    assert next(f for f in forms if f["id"] == "optik129")["fieldCount"] == 14


def testCreateEditAndTestRead():
    r = upload("/api/forms", name="Deneme Formu Ö1")
    assert r.status_code == 200, r.text
    spec = r.json()
    assert spec["id"] == "deneme-formu-o1" and spec["rectified"] and spec["hasReference"]
    assert spec["width"] == 2000 and len(spec["anchors"]) == 10
    detection = client.get(f"/api/forms/{spec['id']}/detection").json()
    assert len(detection["circles"]) > 1700
    assert client.get(f"/api/forms/{spec['id']}/reference.jpg").content[:2] == b"\xff\xd8"

    # düzeltilmiş uzayda öğrenci no ızgarası: sol üst baloncuğu algılananlardan bul
    xs = sorted({round(c[0] / 40) for c in detection["circles"]})
    field = {"name": "ogrenciNo", "title": "Öğrenci No", "category": "info", "type": "columns",
             "stepX": 40, "stepY": 40, "rows": 10, "cols": 5, "labels": list("0123456789"), "blank": "_"}
    first = min((c for c in detection["circles"] if 480 < c[0] < 560 and 240 < c[1] < 320),
                key=lambda c: c[0] + c[1])
    field.update(x=first[0], y=first[1])
    draft = {**spec, "fields": [field]}
    result = client.post(f"/api/forms/{spec['id']}/test", json=draft).json()
    assert result["ok"] and result["fields"]["ogrenciNo"]["value"] == EXPECTED["ogrenciNo"]

    assert client.put(f"/api/forms/{spec['id']}", json=draft).json()["fields"][0]["name"] == "ogrenciNo"
    bad = {**draft, "fields": [{**field, "labels": ["0"]}]}
    assert client.put(f"/api/forms/{spec['id']}", json=bad).status_code == 400
    assert client.delete(f"/api/forms/{spec['id']}").status_code == 200
    assert client.get(f"/api/forms/{spec['id']}").status_code == 404


def testReferenceForExistingTemplate():
    r = upload("/api/forms/optik129/reference")
    assert r.status_code == 200, r.text
    assert client.get("/api/forms/optik129").json()["hasReference"]
    result = client.post("/api/forms/optik129/test", json=client.get("/api/forms/optik129").json()).json()
    assert result["fields"]["adSoyad"]["value"] == EXPECTED["adSoyad"]
