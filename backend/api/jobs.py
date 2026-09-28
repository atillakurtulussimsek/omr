"""Okuma işleri: yüklenen dosyalar arka planda işlenir, durum bellekte, görseller diskte tutulur.
Kalıcı kayıt yoktur; işler JOB_TTL_HOURS sonra silinir. Durum bellekte olduğundan tek worker çalıştırın."""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from omr.annotate import drawAnnotated, encodeJpeg
from omr.pages import countPages, iterPages
from omr.reader import readPage
from omr.template import FormTemplate

JOB_DIR = Path(os.environ.get("JOB_DIR", Path(tempfile.gettempdir()) / "omrJobs"))
JOB_TTL_HOURS = float(os.environ.get("JOB_TTL_HOURS", "24"))
WORKER_COUNT = int(os.environ.get("WORKER_COUNT", "2"))


class Job:
    def __init__(self, template: FormTemplate, files: List[Path]):
        self.id = uuid.uuid4().hex
        self.template = template
        self.files = files
        self.dir = JOB_DIR / self.id
        self.createdAt = time.time()
        self.status = "queued"   # queued | running | done | error
        self.error = ""
        self.total = 0
        self.pages: List[dict] = []
        self.lock = threading.Lock()

    def annotatedPath(self, index: int) -> Path:
        return self.dir / "annotated" / f"{index:05d}.jpg"

    def toDict(self) -> dict:
        with self.lock:
            return {"id": self.id, "formId": self.template.id, "status": self.status,
                    "error": self.error, "total": self.total, "processed": len(self.pages),
                    "pages": list(self.pages)}


jobs: Dict[str, Job] = {}
executor = ThreadPoolExecutor(max_workers=WORKER_COUNT)


def newJobDir() -> Path:
    path = JOB_DIR / ("upload-" + uuid.uuid4().hex)
    (path / "input").mkdir(parents=True)
    return path


def submitJob(template: FormTemplate, uploadDir: Path, files: List[Path]) -> Job:
    cleanupJobs()
    job = Job(template, files)
    uploadDir.rename(job.dir)
    job.files = [job.dir / "input" / f.name for f in files]
    (job.dir / "annotated").mkdir()
    jobs[job.id] = job
    executor.submit(runJob, job)
    return job


def getJob(jobId: str) -> Optional[Job]:
    return jobs.get(jobId)


def runJob(job: Job) -> None:
    job.status = "running"
    try:
        job.total = sum(countPages(f) for f in job.files)
        for path in job.files:
            for pageNo, image in iterPages(path):
                index = len(job.pages)
                # yüklenen dosya adının başındaki sıra öneki (0001_) gösterimde atılır
                source = {"file": path.name.split("_", 1)[1], "page": pageNo}
                if image is None:
                    data = {"ok": False, "error": "Görüntü açılamadı", "fields": {}, "flags": []}
                else:
                    result, alignment = readPage(image, job.template)
                    data = result.toDict()
                    if alignment is not None:
                        annotated = drawAnnotated(alignment, job.template, result)
                        job.annotatedPath(index).write_bytes(encodeJpeg(annotated))
                data.update(index=index, source=source, hasAnnotated=job.annotatedPath(index).is_file())
                with job.lock:
                    job.pages.append(data)
        job.status = "done"
    except Exception as e:  # bozuk PDF vb.
        job.error = str(e)
        job.status = "error"
    finally:
        shutil.rmtree(job.dir / "input", ignore_errors=True)


def cleanupJobs() -> None:
    limit = time.time() - JOB_TTL_HOURS * 3600
    for jobId in [i for i, j in jobs.items() if j.createdAt < limit and j.status in ("done", "error")]:
        shutil.rmtree(jobs.pop(jobId).dir, ignore_errors=True)
    if JOB_DIR.is_dir():   # yeniden başlatmadan kalan sahipsiz klasörler
        for p in JOB_DIR.iterdir():
            if p.name not in jobs and p.stat().st_mtime < limit:
                shutil.rmtree(p, ignore_errors=True)
