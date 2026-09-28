"""Sekonic .FMT içe aktarma: optik okuyucu form tanımından alanları ve TXT düzenini üretir.

Dosya (Windows-1254):
  başlık : satırSayısı=sütunSayısı=?=?=çiftİşaretKarakteri=boşKarakteri=
  alan   : satırBaş=satırSon=sütunBaş=sütunSon=S|K=D|Y=etiketler=X=[ad]
           D (dikey): her sütun bir hane, etiketler satırlara karşılık gelir
           Y (yatay): her satır bir soru, etiketler sütunlara karşılık gelir
           etiketi tek boşluk olan satır okuma yapmaz, çıktıya hane sayısı kadar boşluk koyar
Alan satırlarının sırası TXT çıktısındaki sıradır. Satır/sütun numaraları baloncuk kafesindeki
konumlardır; kafesin görseldeki yeri, FMT hücrelerini algılanan baloncuklarla en çok örtüştüren
kaydırma aranarak bulunur."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .reference import neighborPitch
from .store import TR_MAP

ENCODING = "windows-1254"
LINE = re.compile(r"^(\d+)=(\d+)=(\d+)=(\d+)=([SK])=([DY])=(.*)=X=\[(.*)\]\s*$")


class FmtError(ValueError):
    pass


@dataclass
class FmtEntry:
    row0: int
    row1: int
    col0: int
    col1: int
    direction: str      # D | Y
    labels: List[str]
    name: str

    @property
    def rows(self) -> int:
        return self.row1 - self.row0 + 1

    @property
    def cols(self) -> int:
        return self.col1 - self.col0 + 1

    @property
    def groupCount(self) -> int:
        return self.cols if self.direction == "D" else self.rows

    @property
    def isSpacer(self) -> bool:
        return all(l.strip() == "" for l in self.labels)


def parseFmt(data: bytes) -> Tuple[dict, List[FmtEntry]]:
    lines = [l for l in data.decode(ENCODING, errors="replace").splitlines() if l.strip()]
    if not lines:
        raise FmtError("FMT dosyası boş")
    head = lines[0].split("=")
    if len(head) < 6 or not head[0].isdigit() or not head[1].isdigit():
        raise FmtError("FMT başlık satırı tanınmadı")
    header = {"rows": int(head[0]), "cols": int(head[1]), "multi": head[4] or "*", "blank": head[5] or " "}
    entries = []
    for n, line in enumerate(lines[1:], 2):
        m = LINE.match(line)
        if not m:
            raise FmtError(f"FMT {n}. satır tanınmadı: {line}")
        row0, row1, col0, col1 = (int(v) for v in m.groups()[:4])
        entry = FmtEntry(row0, row1, col0, col1, m.group(6), list(m.group(7)), m.group(8).strip())
        options = entry.rows if entry.direction == "D" else entry.cols
        if not entry.isSpacer and len(entry.labels) != options:
            raise FmtError(f"FMT {n}. satır ({entry.name}): {options} seçenek için {len(entry.labels)} etiket var")
        entries.append(entry)
    return header, entries


def mergeStacked(entries: List[FmtEntry]) -> List[FmtEntry]:
    """Aynı hücreleri art arda okuyan satırları (SINIF-1 '0111' + SINIF-2 '9012') çok karakterli
    etiketli tek alana birleştirir ('09', '10', '11', '12')."""
    out: List[FmtEntry] = []
    for e in entries:
        p = out[-1] if out else None
        if p and not e.isSpacer and not p.isSpacer and (p.row0, p.row1, p.col0, p.col1, p.direction) == \
                (e.row0, e.row1, e.col0, e.col1, e.direction):
            p.labels = [a + b for a, b in zip(p.labels, e.labels)]
            p.name = re.sub(r"[-_ ]*\d+$", "", p.name) or p.name
        else:
            out.append(FmtEntry(e.row0, e.row1, e.col0, e.col1, e.direction, list(e.labels), e.name))
    return out


def lattice(circles: np.ndarray) -> Tuple[float, float, float, float]:
    """(adımX, adımY, fazX, fazY): baloncuk merkezleri ~ faz + k * adım."""
    radius = float(np.median(circles[:, 2]))
    pitchX, pitchY = neighborPitch(circles[:, :2], 0, radius), neighborPitch(circles[:, :2], 1, radius)
    if not pitchX or not pitchY:
        raise FmtError("Referans görselde baloncuk kafesi bulunamadı")

    def phase(values: np.ndarray, pitch: float) -> float:
        angle = np.angle(np.exp(2j * np.pi * values / pitch).sum())
        return float(angle / (2 * np.pi) * pitch % pitch)

    return pitchX, pitchY, phase(circles[:, 0], pitchX), phase(circles[:, 1], pitchY)


def findShift(entries: List[FmtEntry], circles: np.ndarray, grid: Tuple[float, float, float, float]
              ) -> Tuple[int, int, float]:
    """FMT (sütun, satır) -> kafes indeksi kaydırması ve örtüşme oranı."""
    pitchX, pitchY, phaseX, phaseY = grid
    gx = (circles[:, 0] - phaseX) / pitchX
    gy = (circles[:, 1] - phaseY) / pitchY
    ok = (np.abs(gx - np.rint(gx)) < 0.2) & (np.abs(gy - np.rint(gy)) < 0.2)
    gx, gy = np.rint(gx[ok]).astype(int), np.rint(gy[ok]).astype(int)
    pad = 80
    occupied = np.zeros((gy.max() + 2 * pad, gx.max() + 2 * pad), bool)
    occupied[gy + pad, gx + pad] = True
    cells = np.array([(r, c) for e in entries if not e.isSpacer
                      for r in range(e.row0, e.row1 + 1) for c in range(e.col0, e.col1 + 1)
                      if (e.labels[r - e.row0] if e.direction == "D" else e.labels[c - e.col0]).strip()])
    if len(cells) == 0:
        raise FmtError("FMT dosyasında okunacak alan yok")
    best = (-1, 0, 0)
    for ky in range(-cells[:, 0].max(), gy.max() + 1):
        for kx in range(-cells[:, 1].max(), gx.max() + 1):
            r, c = cells[:, 0] + ky + pad, cells[:, 1] + kx + pad
            inside = (r >= 0) & (r < occupied.shape[0]) & (c >= 0) & (c < occupied.shape[1])
            score = int(occupied[r[inside], c[inside]].sum())
            if score > best[0]:
                best = (score, kx, ky)
    return best[1], best[2], best[0] / float(len(cells))


def fitAxis(index: np.ndarray, position: np.ndarray, start: float, step: float) -> Tuple[float, float]:
    """konum ~ başlangıç + indeks * adım doğrusu; tek indeks varsa yalnız başlangıç düzeltilir."""
    if len(index) == 0:
        return start, step
    if len(np.unique(index)) < 2:
        return float(np.mean(position - index * step)), step
    slope, intercept = np.polyfit(index, position, 1)
    return float(intercept), float(slope)


def fieldKey(name: str, used: set) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name.translate(TR_MAP)) or ["alan"]
    key = words[0].lower() + "".join(w.capitalize() for w in words[1:])
    if not key[0].isalpha():
        key = "alan" + key
    base, n = key, 2
    while key in used:
        key, n = f"{base}{n}", n + 1
    used.add(key)
    return key


def importFmt(data: bytes, detection: dict) -> dict:
    """Dönüş: {"fields": [...], "export": {...}, "report": {...}} (şablona uygulanmaya hazır öneri)."""
    circles = np.array(detection.get("circles", []), dtype=np.float64).reshape(-1, 3)
    if len(circles) < 30:
        raise FmtError("FMT içe aktarma için baloncukları algılanmış bir referans görsel gerekli")
    header, rawEntries = parseFmt(data)
    entries = mergeStacked(rawEntries)
    grid = lattice(circles)
    pitchX, pitchY, phaseX, phaseY = grid
    shiftX, shiftY, ratio = findShift(entries, circles, grid)
    tol = 0.35 * min(pitchX, pitchY)

    fields, items, warnings, used = [], [], [], set()
    for e in entries:
        if e.isSpacer:
            items.append({"kind": "space", "width": e.groupCount})
            continue
        labels, cols, rows, strideX, strideY = list(e.labels), e.cols, e.rows, 1, 1
        # "A B" gibi aralıklı etiketler: boş hücreleri at, adımı büyüt
        marked = [i for i, l in enumerate(labels) if l.strip()]
        if len(marked) < len(labels) and len(marked) >= 1:
            gaps = set(np.diff(marked)) if len(marked) > 1 else {1}
            if marked[0] == 0 and len(gaps) == 1:
                stride = int(gaps.pop())
                labels = [labels[i] for i in marked]
                if e.direction == "D":
                    rows, strideY = len(labels), stride
                else:
                    cols, strideX = len(labels), stride
        x0 = phaseX + (e.col0 + shiftX) * pitchX
        y0 = phaseY + (e.row0 + shiftY) * pitchY
        stepX, stepY = pitchX * strideX, pitchY * strideY
        # hücreleri algılanan baloncuklarla eşle; baloncuğu hiç olmayan sondaki haneleri at
        ci, ri = np.meshgrid(np.arange(cols), np.arange(rows))
        pts = np.c_[x0 + ci.ravel() * stepX, y0 + ri.ravel() * stepY]
        dist = np.linalg.norm(pts[:, None] - circles[None, :, :2], axis=2)
        near, hit = dist.argmin(axis=1), dist.min(axis=1) < tol
        groupAxis = ci.ravel() if e.direction == "D" else ri.ravel()
        groupHits = [bool(hit[groupAxis == g].any()) for g in range(e.groupCount if e.direction == "D" and strideX == 1
                                                                  or e.direction == "Y" and strideY == 1 else 0)]
        trimmed = 0
        while groupHits and not groupHits[-1] and len(groupHits) > 1:
            groupHits.pop()
            trimmed += 1
        if trimmed:
            if e.direction == "D":
                cols -= trimmed
            else:
                rows -= trimmed
            keep = (ci.ravel() < cols) & (ri.ravel() < rows)
            ci, ri, near, hit = ci.ravel()[keep], ri.ravel()[keep], near[keep], hit[keep]
            warnings.append(f"{e.name}: baloncuğu olmayan son {trimmed} hane okunmayacak (çıktı genişliği korunur)")
        else:
            ci, ri = ci.ravel(), ri.ravel()
        if not hit.any():
            # FMT ile basılı form arasında bir hücrelik kayma olabiliyor: komşu konumu dene
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                moved = pts[:len(ci)] + (dx * pitchX, dy * pitchY)
                d2 = np.linalg.norm(moved[:, None] - circles[None, :, :2], axis=2)
                if (d2.min(axis=1) < tol).all():
                    near, hit = d2.argmin(axis=1), np.ones(len(ci), bool)
                    x0, y0 = x0 + dx * pitchX, y0 + dy * pitchY
                    warnings.append(f"{e.name}: FMT konumunda baloncuk yok; bir hücre "
                                    f"{'sola' if dx < 0 else 'sağa' if dx > 0 else 'yukarı' if dy < 0 else 'aşağı'} "
                                    "kaydırılarak oturtuldu, kontrol edin")
                    break
            else:
                warnings.append(f"{e.name}: bu konumda baloncuk algılanmadı")
        x0, stepX = fitAxis(ci[hit], circles[near[hit], 0], x0, stepX)
        y0, stepY = fitAxis(ri[hit], circles[near[hit], 1], y0, stepY)

        isAnswers = e.direction == "Y" and rows > 1 and "".join(labels) in "ABCDEFGH"
        key = fieldKey(e.name, used)
        fields.append({
            "name": key, "title": e.name, "category": "answers" if isAnswers else "info",
            "type": "columns" if e.direction == "D" else "rows",
            "x": round(x0, 1), "y": round(y0, 1), "stepX": round(stepX, 2), "stepY": round(stepY, 2),
            "rows": rows, "cols": cols, "labels": labels,
            "blank": "-" if isAnswers else "_" if "".join(labels).isdigit() and len(labels) == 10 else " ",
        })
        items.append({"kind": "field", "field": key, "width": e.groupCount * max(len(l) for l in labels),
                      "align": "left", "pad": " ", "blankAs": header["blank"], "multiAs": header["multi"], "map": {}})
    if ratio < 0.8:
        warnings.append(f"FMT hücrelerinin yalnız %{round(ratio * 100)}'i algılanan baloncuklarla örtüştü; "
                        "FMT bu forma ait olmayabilir")
    return {
        "fields": fields,
        "export": {"encoding": ENCODING, "items": items},
        "report": {"matchRatio": round(ratio, 3), "fieldCount": len(fields),
                   "lineWidth": sum(i["width"] for i in items), "warnings": warnings},
    }
