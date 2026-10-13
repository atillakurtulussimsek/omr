"""Girdi: görüntü veya çok sayfalı PDF -> BGR sayfa görüntüleri."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Tuple

import cv2
import numpy as np

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
PDF_DPI = 240
# PDF sayfası gömülü taramadan küçük olabilir (A4 tarama A5 sayfaya yerleştirilmiş gibi); sabit dpi ile
# render edince görüntü yarıya iner ve baloncuklar algılanamaz. Bu yüzden dpi, gömülü görselin yerel
# çözünürlüğüne göre seçilir; çıktı uzun kenarı bu aralıkta tutulur.
MIN_LONG_SIDE = 2200
MAX_LONG_SIDE = 3600


def pageDpi(page) -> int:
    """Sayfadaki en büyük gömülü görselin yerel çözünürlüğünü verecek dpi (sınırlar içinde)."""
    longPt = max(page.rect.width, page.rect.height)
    native = 0
    for img in page.get_images(full=True):
        native = max(native, img[2], img[3])
    if native == 0:
        native = PDF_DPI * longPt / 72
    target = min(max(native, MIN_LONG_SIDE), MAX_LONG_SIDE)
    return int(round(target / (longPt / 72)))


def isSupported(name: str) -> bool:
    ext = Path(name).suffix.lower()
    return ext in IMAGE_EXTS or ext == ".pdf"


def countPages(path: Path) -> int:
    if path.suffix.lower() != ".pdf":
        return 1
    import fitz
    with fitz.open(path) as doc:
        return doc.page_count


def iterPages(path: Path) -> Iterator[Tuple[int, np.ndarray]]:
    """(sayfaNo, görüntü) üretir; sayfaNo 1'den başlar. Açılamayan görüntü için None döner."""
    if path.suffix.lower() == ".pdf":
        import fitz
        with fitz.open(path) as doc:
            for i, page in enumerate(doc, 1):
                pix = page.get_pixmap(dpi=pageDpi(page), colorspace=fitz.csRGB, alpha=False)
                rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
                yield i, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    else:
        yield 1, cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
