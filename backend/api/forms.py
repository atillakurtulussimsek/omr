"""Form tanımlama uçları: şablon listesi, oluşturma (referans görselden), kaydetme, deneme okuması."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import List

import cv2
import numpy as np
from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from omr import reference, store
from omr.align import AlignmentError
from omr.export import formatLine
from omr.fmt import FmtError, importFmt
from omr.pages import isSupported, iterPages
from omr.reader import readPage
from omr.template import buildTemplate, listTemplates

router = APIRouter(prefix="/api/forms")


def readUpload(file: UploadFile) -> np.ndarray:
    """Yüklenen görselin (PDF ise ilk sayfasının) BGR hali."""
    if not isSupported(file.filename or ""):
        raise HTTPException(400, "Desteklenmeyen dosya türü")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / ("upload" + Path(file.filename).suffix.lower())
        path.write_bytes(file.file.read())
        try:
            _, image = next(iterPages(path))
        except Exception:
            image = None
    if image is None:
        raise HTTPException(400, "Görsel açılamadı")
    return image


def saveReference(formId: str, canonical: np.ndarray, detection: dict) -> None:
    store.formDir(formId).mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(store.referencePath(formId)), canonical, [cv2.IMWRITE_JPEG_QUALITY, 85])
    store.detectionPath(formId).write_text(json.dumps(detection), encoding="utf-8")


def loadSpecOr404(formId: str) -> dict:
    try:
        return store.loadSpec(formId)
    except (FileNotFoundError, store.TemplateError) as e:
        raise HTTPException(404, str(e))


def withMeta(spec: dict) -> dict:
    return {**spec, "hasReference": store.referencePath(spec["id"]).is_file()}


@router.get("")
def listForms() -> List[dict]:
    return listTemplates()


@router.post("")
def createForm(name: str = Form(...), file: UploadFile = File(...)) -> dict:
    if not name.strip():
        raise HTTPException(400, "Form adı boş olamaz")
    canonical, detection, rectified = reference.prepareNew(readUpload(file))
    spec = {
        "id": store.newFormId(name), "name": name.strip(),
        "width": canonical.shape[1], "height": canonical.shape[0],
        "bubbleRadius": detection["bubbleRadius"], "anchorSize": detection["anchorSize"],
        "anchors": detection["anchors"], "fields": [],
        "timingMarks": detection["timingMarks"], "timingSize": detection["timingSize"],
        # kare yoksa (4'ten az) zamanlama işaretleriyle hizalanır
        "alignment": "anchors" if len(detection["anchors"]) >= 4 or not detection["timingMarks"] else "timing",
    }
    store.saveSpec(spec)
    saveReference(spec["id"], canonical, detection)
    return {**withMeta(spec), "rectified": rectified}


@router.get("/{formId}")
def getForm(formId: str) -> dict:
    return withMeta(loadSpecOr404(formId))


@router.put("/{formId}")
def saveForm(formId: str, spec: dict = Body(...)) -> dict:
    current = loadSpecOr404(formId)
    spec = {k: v for k, v in spec.items() if k != "hasReference"}
    spec.update(id=formId, width=current["width"], height=current["height"])
    try:
        store.saveSpec(spec)
    except store.TemplateError as e:
        raise HTTPException(400, str(e))
    return withMeta(spec)


@router.delete("/{formId}")
def deleteForm(formId: str) -> dict:
    loadSpecOr404(formId)
    store.deleteForm(formId)
    return {"deleted": formId}


@router.get("/{formId}/reference.jpg")
def getReference(formId: str) -> FileResponse:
    loadSpecOr404(formId)
    if not store.referencePath(formId).is_file():
        raise HTTPException(404, "Referans görsel yok")
    return FileResponse(store.referencePath(formId), media_type="image/jpeg",
                        headers={"Cache-Control": "no-cache"})


@router.get("/{formId}/detection")
def getDetection(formId: str) -> dict:
    loadSpecOr404(formId)
    if not store.detectionPath(formId).is_file():
        return {"circles": [], "anchors": [], "bubbleRadius": 0, "anchorSize": 0,
                "timingMarks": [], "timingSize": [0, 0]}
    return json.loads(store.detectionPath(formId).read_text(encoding="utf-8"))


@router.post("/{formId}/reference")
def uploadReference(formId: str, file: UploadFile = File(...)) -> dict:
    """Var olan şablona referans görsel: şablonun kanonik uzayına hizalanarak kaydedilir."""
    spec = loadSpecOr404(formId)
    try:
        canonical, detection = reference.prepareExisting(readUpload(file), buildTemplate(spec))
    except AlignmentError as e:
        raise HTTPException(400, f"Görsel şablona hizalanamadı: {e}")
    saveReference(formId, canonical, detection)
    return detection


@router.post("/{formId}/test")
def testRead(formId: str, spec: dict = Body(...)) -> dict:
    """Kaydedilmemiş taslağı referans görsel üzerinde dener."""
    current = loadSpecOr404(formId)
    if not store.referencePath(formId).is_file():
        raise HTTPException(400, "Deneme için referans görsel gerekli")
    spec = {k: v for k, v in spec.items() if k != "hasReference"}
    spec.update(id=formId, width=current["width"], height=current["height"])
    try:
        template = buildTemplate(spec)
    except store.TemplateError as e:
        raise HTTPException(400, str(e))
    result, _ = readPage(cv2.imread(str(store.referencePath(formId))), template)
    data = result.toDict()
    data["exportLine"] = formatLine(data["fields"], template) if result.ok else ""
    return data


@router.post("/{formId}/fmt")
def importFmtFile(formId: str, file: UploadFile = File(...)) -> dict:
    """Sekonic .FMT dosyasından alan + TXT düzeni önerisi; kaydetmez, editördeki taslağa uygulanır."""
    loadSpecOr404(formId)
    if not store.detectionPath(formId).is_file():
        raise HTTPException(400, "FMT içe aktarma için referans görsel gerekli")
    detection = json.loads(store.detectionPath(formId).read_text(encoding="utf-8"))
    try:
        return importFmt(file.file.read(), detection)
    except FmtError as e:
        raise HTTPException(400, str(e))
