"""İşaretleme sonucu görseli: okunan baloncukları kanonik görüntü üzerinde çizer."""
from __future__ import annotations

import cv2
import numpy as np

from .align import Alignment
from .reader import FILLED_THRESHOLD, MULTI, SUSPECT_THRESHOLD, PageResult
from .template import FormTemplate

GREEN, ORANGE, RED = (0, 200, 0), (0, 140, 255), (0, 0, 230)


def drawAnnotated(alignment: Alignment, template: FormTemplate, result: PageResult) -> np.ndarray:
    im = alignment.color.copy()
    r = int(template.bubbleRadius + 2)
    for f in template.fields:
        for g, gr in zip(f.groups, result.fields[f.name].groups):
            for c, v in zip(g.cells, gr.fills):
                if v < SUSPECT_THRESHOLD:
                    continue
                color = RED if gr.status == MULTI else GREEN if v >= FILLED_THRESHOLD else ORANGE
                x, y = alignment.cellPoints[c.index]
                cv2.circle(im, (int(round(x)), int(round(y))), r, color, 3)
    return im


def encodeJpeg(image: np.ndarray, quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG kodlanamadı")
    return buf.tobytes()
