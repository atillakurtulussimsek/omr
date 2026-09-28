"""Okuma: hizalanmış sayfadaki her baloncuk için doluluk oranı -> grup/alan değerleri."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .align import Alignment, AlignmentError, alignPage
from .template import FormTemplate

FILL_RADIUS = 10          # doluluk ölçülen dairenin yarıçapı (kanonik px)
# Doluluk = dairedeki ortalama koyuluk, kâğıt beyazı (0) - sayfanın en koyu düzeyi (1) arasında.
# Ölçümler: boş baloncuk <= 0.30 (içindeki harf baskısı), silik işaret >= 0.40, koyu işaret ~0.9.
FILLED_THRESHOLD = 0.45
SUSPECT_THRESHOLD = 0.32
MULTI_MARK = "*"
MIN_CIRCLE_MATCH_RATIO = 0.6

EMPTY, FILLED, MULTI, SUSPECT = "empty", "filled", "multi", "suspect"


@dataclass
class GroupResult:
    value: str
    status: str
    fills: List[float]


@dataclass
class FieldResult:
    name: str
    title: str
    category: str
    value: str
    groups: List[GroupResult]


@dataclass
class PageResult:
    ok: bool
    error: str = ""
    fields: Dict[str, FieldResult] = field(default_factory=dict)
    flags: List[dict] = field(default_factory=list)
    alignment: dict = field(default_factory=dict)

    def toDict(self) -> dict:
        return {
            "ok": self.ok,
            "error": self.error,
            "fields": {
                n: {"title": f.title, "category": f.category, "value": f.value,
                    "groups": [{"value": g.value, "status": g.status,
                                "fills": [round(v, 3) for v in g.fills]} for g in f.groups]}
                for n, f in self.fields.items()
            },
            "flags": self.flags,
            "alignment": self.alignment,
        }


def fillRatios(gray: np.ndarray, points: np.ndarray, paperWhite: float, darkLevel: float) -> np.ndarray:
    r = FILL_RADIUS
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    disk = xx * xx + yy * yy <= r * r
    padded = np.pad(gray, r, constant_values=255)
    span = max(paperWhite - darkLevel, 1.0)
    out = np.zeros(len(points))
    for i, (x, y) in enumerate(np.rint(points).astype(int)):
        if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
            roi = padded[y:y + 2 * r + 1, x:x + 2 * r + 1]
            out[i] = (paperWhite - float(roi[disk].mean())) / span
    return np.clip(out, 0.0, 1.0)


def readGroup(labels: List[str], fills: np.ndarray, blank: str) -> GroupResult:
    filled = [l for l, v in zip(labels, fills) if v >= FILLED_THRESHOLD]
    suspect = bool(((fills >= SUSPECT_THRESHOLD) & (fills < FILLED_THRESHOLD)).any())
    if len(filled) > 1:
        value, status = MULTI_MARK, MULTI
    elif len(filled) == 1:
        value, status = filled[0], SUSPECT if suspect else FILLED
    else:
        value, status = blank, SUSPECT if suspect else EMPTY
    return GroupResult(value, status, [float(v) for v in fills])


def readAligned(alignment: Alignment, template: FormTemplate) -> PageResult:
    fills = fillRatios(alignment.gray, alignment.cellPoints, alignment.paperWhite, alignment.darkLevel)
    result = PageResult(ok=True, alignment={
        "method": alignment.method,
        "anchorCount": alignment.anchorCount,
        "circleMatchRatio": round(alignment.circleMatchRatio, 3),
    })
    if alignment.circleMatchRatio < MIN_CIRCLE_MATCH_RATIO:
        result.flags.append({"field": "", "group": -1, "status": "alignment",
                             "message": "Hizalama zayıf; sonuçları kontrol edin"})
    for f in template.fields:
        groups = []
        for gi, g in enumerate(f.groups):
            gr = readGroup([c.label for c in g.cells],
                           fills[[c.index for c in g.cells]], f.blank)
            groups.append(gr)
            if gr.status in (MULTI, SUSPECT):
                result.flags.append({"field": f.name, "group": gi, "status": gr.status,
                                     "message": f"{f.title} {gi + 1}: " +
                                     ("çift işaret" if gr.status == MULTI else "şüpheli işaret")})
        value = "".join(g.value for g in groups)
        if f.category != "answers":
            value = value.strip()
        result.fields[f.name] = FieldResult(f.name, f.title, f.category or "info", value, groups)
    return result


def readPage(image: np.ndarray, template: FormTemplate):
    """Dönüş: (PageResult, Alignment | None)."""
    try:
        alignment = alignPage(image, template)
    except AlignmentError as e:
        return PageResult(ok=False, error=str(e)), None
    return readAligned(alignment, template), alignment
