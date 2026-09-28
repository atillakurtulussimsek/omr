"""Form şablonu: JSON tanımını kanonik piksel koordinatlı alan/grup/hücre yapısına açar.

Alan hücresi (satır r, sütun c) merkezi: (x + c*stepX, y + r*stepY), kanonik piksel.
Alan tipleri:
  rows    : her satır bir grup, seçenekler sütunlardır (cevaplar, kitapçık)
  columns : her sütun bir grup, seçenekler satırlardır (rakam/harf ızgaraları)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from . import store

DEFAULT_PITCH = 40.0


@dataclass
class Cell:
    x: float
    y: float
    label: str
    index: int = -1  # şablondaki tüm hücreler içindeki sıra


@dataclass
class Group:
    cells: List[Cell]


@dataclass
class Field:
    name: str
    title: str
    kind: str
    blank: str
    category: Optional[str]
    groups: List[Group]

    @property
    def width(self) -> int:
        """Sabit genişlikli dışa aktarmada kapladığı karakter sayısı."""
        longest = max(len(c.label) for g in self.groups for c in g.cells)
        return len(self.groups) * longest


@dataclass
class FormTemplate:
    id: str
    name: str
    width: int
    height: int
    bubbleRadius: float
    anchorSize: float
    pitch: float
    anchors: np.ndarray
    fields: List[Field]
    alignment: str = "anchors"           # anchors | timing
    timingMarks: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    timingSize: Optional[List[float]] = None   # (uzun, kısa) kenar, kanonik px
    cells: List[Cell] = field(default_factory=list)
    export: Optional[dict] = None   # TXT çıktı düzeni (bkz. export.py)

    @property
    def cellPoints(self) -> np.ndarray:
        return np.array([(c.x, c.y) for c in self.cells], dtype=np.float64).reshape(-1, 2)


def buildField(spec: dict) -> Field:
    def cell(r: int, c: int, label: str) -> Cell:
        return Cell(spec["x"] + c * spec["stepX"], spec["y"] + r * spec["stepY"], label)

    labels = spec["labels"]
    if spec["type"] == "rows":
        groups = [Group([cell(r, c, labels[c]) for c in range(spec["cols"])]) for r in range(spec["rows"])]
    else:
        groups = [Group([cell(r, c, labels[r]) for r in range(spec["rows"])]) for c in range(spec["cols"])]
    return Field(spec["name"], spec.get("title") or spec["name"], spec["type"],
                 spec.get("blank", ""), spec.get("category"), groups)


def buildTemplate(spec: dict) -> FormTemplate:
    store.validateSpec(spec)
    fields = [buildField(f) for f in spec.get("fields", [])]
    cells = [c for f in fields for g in f.groups for c in g.cells]
    for i, c in enumerate(cells):
        c.index = i
    steps = [f[k] for f in spec.get("fields", []) for k, n in (("stepX", "cols"), ("stepY", "rows")) if f[n] > 1]
    return FormTemplate(
        id=spec["id"], name=spec["name"], width=int(spec["width"]), height=int(spec["height"]),
        bubbleRadius=spec["bubbleRadius"], anchorSize=spec.get("anchorSize", 33),
        pitch=min(steps) if steps else DEFAULT_PITCH,
        anchors=np.array(spec.get("anchors", []), dtype=np.float64).reshape(-1, 2),
        fields=fields, cells=cells, export=spec.get("export"),
        alignment=spec.get("alignment", "anchors"),
        timingMarks=np.array(spec.get("timingMarks", []), dtype=np.float64).reshape(-1, 2),
        timingSize=spec.get("timingSize"),
    )


def loadTemplate(formId: str = "optik129") -> FormTemplate:
    return buildTemplate(store.loadSpec(formId))


def listTemplates() -> List[dict]:
    return [{"id": s["id"], "name": s["name"], "fieldCount": len(s.get("fields", [])),
             "anchorCount": len(s.get("anchors", [])), "alignment": s.get("alignment", "anchors"),
             "timingCount": len(s.get("timingMarks", [])),
             "hasReference": store.referencePath(s["id"]).is_file()} for s in store.listSpecs()]
