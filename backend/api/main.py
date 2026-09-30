from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

from typing import Dict, List

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from omr.export import exportTxt
from omr.pages import isSupported
from omr.template import loadTemplate

from . import auth, jobs
from .forms import router as formsRouter

app = FastAPI(title="Optik Form Okuyucu", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(auth.router)
app.include_router(formsRouter)
app.middleware("http")(auth.requireSession)


def requireJob(jobId: str) -> jobs.Job:
    job = jobs.getJob(jobId)
    if job is None:
        raise HTTPException(404, "İş bulunamadı")
    return job


def pageStem(page: dict) -> str:
    source = page["source"]
    return f"{page['index'] + 1:04d}_{Path(source['file']).stem}_s{source['page']}"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/jobs")
def createJob(files: List[UploadFile] = File(...), formId: str = Form("optik129")) -> dict:
    try:
        template = loadTemplate(formId)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    unsupported = [f.filename for f in files if not isSupported(f.filename or "")]
    if unsupported:
        raise HTTPException(400, "Desteklenmeyen dosya: " + ", ".join(map(str, unsupported)))
    uploadDir = jobs.newJobDir()
    saved = []
    for i, f in enumerate(files):
        path = uploadDir / "input" / f"{i:04d}_{Path(f.filename).name}"
        with path.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(path)
    return jobs.submitJob(template, uploadDir, saved).toDict()


@app.get("/api/jobs/{jobId}")
def jobStatus(jobId: str) -> dict:
    return requireJob(jobId).toDict()


@app.put("/api/jobs/{jobId}/pages/{index}")
def editPage(jobId: str, index: int, edits: Dict[str, Dict[str, str]] = Body(...)) -> dict:
    """Elle düzeltme: {alan: {grupIndeksi: değer}}."""
    try:
        return jobs.applyEdits(requireJob(jobId), index, edits)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/jobs/{jobId}/export.txt")
def jobExport(jobId: str) -> Response:
    job = requireJob(jobId)
    return Response(exportTxt(job.toDict()["pages"], job.template), media_type="text/plain",
                    headers={"Content-Disposition": 'attachment; filename="sonuclar.txt"'})


@app.get("/api/jobs/{jobId}/pages/{index}/annotated.jpg")
def pageAnnotated(jobId: str, index: int, download: bool = False) -> FileResponse:
    job = requireJob(jobId)
    pages = job.toDict()["pages"]
    path = job.annotatedPath(index)
    if not (0 <= index < len(pages)) or not path.is_file():
        raise HTTPException(404, "Görsel bulunamadı")
    return FileResponse(path, media_type="image/jpeg",
                        filename=pageStem(pages[index]) + ".jpg" if download else None)


@app.get("/api/jobs/{jobId}/annotated.zip")
def jobAnnotatedZip(jobId: str) -> StreamingResponse:
    job = requireJob(jobId)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for page in job.toDict()["pages"]:
            if page["hasAnnotated"]:
                z.write(job.annotatedPath(page["index"]), pageStem(page) + ".jpg")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": 'attachment; filename="isaretleme_sonuclari.zip"'})
