"""Form şablonu deposu: FORMS_DIR/{id}/template.json (+ reference.jpg, detection.json).
Paketle gelen şablonlar (omr/forms/*.json) depoda yoksa ilk kullanımda kopyalanır."""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import List

BUILTIN_DIR = Path(__file__).parent / "forms"
FORMS_DIR = Path(os.environ.get("FORMS_DIR", Path(__file__).resolve().parents[1] / "data" / "forms"))

FIELD_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


class TemplateError(ValueError):
    pass


def formDir(formId: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", formId):
        raise TemplateError(f"Geçersiz form kimliği: {formId}")
    return FORMS_DIR / formId


def templatePath(formId: str) -> Path:
    return formDir(formId) / "template.json"


def referencePath(formId: str) -> Path:
    return formDir(formId) / "reference.jpg"


def detectionPath(formId: str) -> Path:
    return formDir(formId) / "detection.json"


def seedBuiltins() -> None:
    for src in BUILTIN_DIR.glob("*.json"):
        dst = templatePath(src.stem)
        if not dst.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)


def withBuiltinDefaults(spec: dict) -> dict:
    """Depodaki eski bir kopyada olmayan hizalama verisini (zamanlama işaretleri) paketteki
    aynı kimlikli şablondan tamamlar; kanonik boyut aynıysa geçerlidir."""
    builtin = BUILTIN_DIR / f"{spec.get('id')}.json"
    if builtin.is_file() and not spec.get("timingMarks"):
        base = json.loads(builtin.read_text(encoding="utf-8"))
        if (base.get("width"), base.get("height")) == (spec.get("width"), spec.get("height")):
            for key in ("timingMarks", "timingSize"):
                if base.get(key):
                    spec[key] = base[key]
    return spec


def listSpecs() -> List[dict]:
    seedBuiltins()
    specs = [withBuiltinDefaults(json.loads(p.read_text(encoding="utf-8"))) for p in FORMS_DIR.glob("*/template.json")]
    return sorted(specs, key=lambda s: s["name"].lower())


def loadSpec(formId: str) -> dict:
    seedBuiltins()
    path = templatePath(formId)
    if not path.is_file():
        raise FileNotFoundError(f"Şablon bulunamadı: {formId}")
    return withBuiltinDefaults(json.loads(path.read_text(encoding="utf-8")))


def saveSpec(spec: dict) -> None:
    validateSpec(spec)
    path = templatePath(spec["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def deleteForm(formId: str) -> None:
    shutil.rmtree(formDir(formId), ignore_errors=True)


def newFormId(name: str) -> str:
    seedBuiltins()
    base = re.sub(r"[^a-z0-9]+", "-", name.translate(TR_MAP).lower()).strip("-") or "form"
    formId, n = base, 2
    while formDir(formId).exists():
        formId, n = f"{base}-{n}", n + 1
    return formId


def validateExport(export: dict, fieldNames: set) -> None:
    if export.get("encoding") not in ("utf-8", "windows-1254"):
        raise TemplateError("TXT çıktısı: kodlama utf-8 veya windows-1254 olmalı")
    if not isinstance(export.get("items"), list):
        raise TemplateError("TXT çıktısı: öğe listesi eksik")
    for n, item in enumerate(export["items"], 1):
        kind = item.get("kind")
        if kind == "text":
            if not isinstance(item.get("text"), str) or "\n" in item["text"] or "\r" in item["text"]:
                raise TemplateError(f"TXT çıktısı {n}. öğe: geçersiz sabit metin")
            continue
        if kind not in ("field", "space"):
            raise TemplateError(f"TXT çıktısı {n}. öğe: bilinmeyen tür")
        if not isinstance(item.get("width"), int) or not 1 <= item["width"] <= 1000:
            raise TemplateError(f"TXT çıktısı {n}. öğe: genişlik 1-1000 arası tam sayı olmalı")
        if kind == "space":
            continue
        if item.get("field") not in fieldNames:
            raise TemplateError(f"TXT çıktısı {n}. öğe: alan bulunamadı ({item.get('field')})")
        if item.get("align", "left") not in ("left", "right"):
            raise TemplateError(f"TXT çıktısı {n}. öğe: hizalama left veya right olmalı")
        if len(item.get("pad", " ")) != 1:
            raise TemplateError(f"TXT çıktısı {n}. öğe: dolgu tek karakter olmalı")
        texts = [item.get("blankAs", " "), item.get("multiAs", "*"), *(item.get("map") or {}).values()]
        if not isinstance(item.get("map") or {}, dict) or not all(isinstance(t, str) for t in texts):
            raise TemplateError(f"TXT çıktısı {n}. öğe: geçersiz dönüşüm")


def validateSpec(spec: dict) -> None:
    if not str(spec.get("name", "")).strip():
        raise TemplateError("Form adı boş olamaz")
    for key in ("width", "height", "bubbleRadius"):
        if not isinstance(spec.get(key), (int, float)) or spec[key] <= 0:
            raise TemplateError(f"Geçersiz değer: {key}")
    if spec.get("alignment", "anchors") not in ("anchors", "timing"):
        raise TemplateError("Hizalama türü anchors veya timing olmalı")
    names = set()
    for f in spec.get("fields", []):
        title = f.get("title") or f.get("name") or "?"
        if not FIELD_NAME.match(str(f.get("name", ""))):
            raise TemplateError(f"{title}: alan anahtarı harfle başlamalı, yalnız harf/rakam içermeli")
        if f["name"] in names:
            raise TemplateError(f"{title}: alan anahtarı tekrar ediyor ({f['name']})")
        names.add(f["name"])
        if f.get("type") not in ("rows", "columns"):
            raise TemplateError(f"{title}: tip rows veya columns olmalı")
        for key in ("rows", "cols"):
            if not isinstance(f.get(key), int) or f[key] < 1:
                raise TemplateError(f"{title}: {key} en az 1 olmalı")
        for key in ("x", "y", "stepX", "stepY"):
            if not isinstance(f.get(key), (int, float)):
                raise TemplateError(f"{title}: {key} sayı olmalı")
        if f["stepX"] <= 0 or f["stepY"] <= 0:
            raise TemplateError(f"{title}: adım sıfırdan büyük olmalı")
        options = f["cols"] if f["type"] == "rows" else f["rows"]
        labels = f.get("labels")
        if not isinstance(labels, list) or len(labels) != options or not all(isinstance(l, str) and l for l in labels):
            raise TemplateError(f"{title}: {options} seçenek için {options} etiket gerekli")
    if spec.get("export") is not None:
        validateExport(spec["export"], names)
