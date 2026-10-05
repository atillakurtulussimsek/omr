"""Form tanımlama uçları: şablon listesi, oluşturma (referans görselden), kaydetme, deneme okuması."""
from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import List

import cv2
import numpy as np
from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

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


EXPORT_KEYS = ("template.json", "reference.jpg", "detection.json")


@router.get("/{formId}/export")
def exportForm(formId: str, withReference: bool = False):
    """Form tanımını indirir: yalnız tanım (JSON) ya da referans görsel + algılama ile birlikte (ZIP)."""
    spec = loadSpecOr404(formId)
    name = f"{formId}.omrform"
    if not withReference:
        return Response(json.dumps(spec, ensure_ascii=False, indent=1).encode("utf-8"),
                        media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{name}.json"'})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("template.json", json.dumps(spec, ensure_ascii=False, indent=1))
        for path in (store.referencePath(formId), store.detectionPath(formId)):
            if path.is_file():
                z.write(path, path.name)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})


@router.post("/import")
def importForm(file: UploadFile = File(...)) -> dict:
    """Dışa aktarılmış form tanımını (JSON veya ZIP) yeni bir form olarak ekler; var olanın üzerine yazmaz."""
    data = file.file.read()
    extras = {}
    try:
        if data[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = set(z.namelist())
                if "template.json" not in names:
                    raise ValueError("ZIP içinde template.json yok")
                spec = json.loads(z.read("template.json").decode("utf-8"))
                extras = {n: z.read(n) for n in ("reference.jpg", "detection.json") if n in names}
        else:
            spec = json.loads(data.decode("utf-8"))
        if not isinstance(spec, dict) or "fields" not in spec:
            raise ValueError("Dosya bir form tanımı değil")
        spec = {k: v for k, v in spec.items() if k not in ("hasReference", "rectified")}
        spec["id"] = store.newFormId(str(spec.get("name", "")))
        store.saveSpec(spec)
    except store.TemplateError as e:
        raise HTTPException(400, f"Form tanımı geçersiz: {e}")
    except (ValueError, KeyError, UnicodeDecodeError, zipfile.BadZipFile) as e:
        raise HTTPException(400, f"Dosya okunamadı: {e}")
    if "reference.jpg" in extras:
        if cv2.imdecode(np.frombuffer(extras["reference.jpg"], np.uint8), cv2.IMREAD_COLOR) is None:
            extras.pop("reference.jpg")
        else:
            store.referencePath(spec["id"]).write_bytes(extras["reference.jpg"])
    if "detection.json" in extras:
        try:
            json.loads(extras["detection.json"].decode("utf-8"))
            store.detectionPath(spec["id"]).write_bytes(extras["detection.json"])
        except ValueError:
            pass
    return withMeta(spec)


@router.delete("/{formId}/reference")
def deleteReference(formId: str) -> dict:
    """Referans (demo) görseli kaldırır. Okuma bundan etkilenmez; baloncuk algılaması editör için kalır,
    yalnız deneme okuması ve TXT önizlemesi görsel gerektirir."""
    loadSpecOr404(formId)
    if store.referencePath(formId).is_file():
        store.referencePath(formId).unlink()
    return {"hasReference": False}
