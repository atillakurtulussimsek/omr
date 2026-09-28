"""Hizalama: dolu hizalama karelerinden (veya kare yoksa zamanlama işaretlerinden) kaba dönüşüm ->
kanonik boyuta warp -> baloncuk çemberleriyle ince düzeltme. Sayfanın yönü (0/90/180/270) eşleştirmeden çıkar."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from .template import FormTemplate
from .timing import MIN_MARKS, findTimingMarks, timingHypotheses

COARSE_TOL = 40.0            # benzerlik hipotezinde eşleşme toleransı (kanonik px)
FINE_TOL = 15.0              # homografi sonrası eşleşme toleransı
CIRCLE_MATCH_TOL = 12.0      # çember <-> şablon hücresi eşleşme toleransı
SNAP_TOL = 7.0               # düzeltme sonrası hücreyi bulunan çembere oturtma toleransı
MIN_ANCHORS = 4
GOOD_MATCH_RATIO = 0.8        # bu örtüşmenin üstünde diğer hizalama yöntemi denenmez
MIN_MATCH_RATIO = 0.3         # bunun altında hizalama yanlış kabul edilir


class AlignmentError(Exception):
    pass


@dataclass
class Alignment:
    gray: np.ndarray           # kanonik doluluk görüntüsü (en parlak kanal)
    color: np.ndarray          # kanonik renkli görüntü
    cellPoints: np.ndarray     # hücre merkezleri (yerel düzeltme uygulanmış)
    homography: np.ndarray     # kaynak -> kanonik
    anchorCount: int
    circleMatchRatio: float    # şablon hücrelerinden çemberi bulunanların oranı
    paperWhite: float
    darkLevel: float = 0.0
    method: str = "anchors"


def applyHomography(h: np.ndarray, pts: np.ndarray) -> np.ndarray:
    q = np.c_[pts, np.ones(len(pts))] @ h.T
    return q[:, :2] / q[:, 2:]


def findSquares(gray: np.ndarray, threshold: float, side: float, maxCount: int = 40) -> np.ndarray:
    """Kenarı ~side piksel olan dolu kare adaylarının merkezleri."""
    _, bw = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
    k = max(3, int(round(0.35 * side)))
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))  # çerçeve/yazı/halka temizliği
    n, _, stats, centroids = cv2.connectedComponentsWithStats(bw)
    found = []
    for i in range(1, n):
        _, _, w, h, area = stats[i]
        if not (0.55 * side <= w <= 1.6 * side and 0.55 * side <= h <= 1.6 * side):
            continue
        extent = area / float(w * h)
        aspect = min(w, h) / float(max(w, h))
        if extent > 0.85 and aspect > 0.8:
            found.append((extent * aspect, centroids[i][0], centroids[i][1]))
    found.sort(reverse=True)
    return np.array([(x, y) for _, x, y in found[:maxCount]], dtype=np.float64).reshape(-1, 2)


def matchAnchors(cands: np.ndarray, anchors: np.ndarray, expectedScale: float
                 ) -> Tuple[np.ndarray, np.ndarray]:
    """Aday kareleri şablon çapalarıyla eşleştirir. Dönüş: (adayIndeksleri, çapaIndeksleri).

    Aday çifti x çapa çifti -> benzerlik dönüşümü hipotezi (karmaşık sayılarla z' = a*z + b);
    en çok çapayı tutturan hipotez seçilir. Dönme serbest olduğundan ters/yan tarama da çözülür."""
    if len(cands) < MIN_ANCHORS:
        raise AlignmentError("Yeterli hizalama karesi bulunamadı")
    c = cands[:, 0] + 1j * cands[:, 1]
    a = anchors[:, 0] + 1j * anchors[:, 1]
    ci, cj = np.where(~np.eye(len(c), dtype=bool))
    ai, aj = np.triu_indices(len(a), 1)
    best = (0, np.inf, None)
    for p, q in zip(ai, aj):
        s = (a[q] - a[p]) / (c[cj] - c[ci])
        ok = (np.abs(s) > 0.6 * expectedScale) & (np.abs(s) < 1.6 * expectedScale)
        if not ok.any():
            continue
        s = s[ok]
        t = a[p] - s * c[ci[ok]]
        mapped = s[:, None] * c[None, :] + t[:, None]                 # (hipotez, aday)
        dist = np.abs(mapped[:, :, None] - a[None, None, :])          # (hipotez, aday, çapa)
        nearest = dist.min(axis=1)                                    # (hipotez, çapa)
        hit = nearest < COARSE_TOL
        counts = hit.sum(axis=1)
        top = counts.max()
        if top < best[0]:
            continue
        idx = np.where(counts == top)[0]
        errs = np.where(hit[idx], nearest[idx], 0).sum(axis=1) / top
        k = idx[errs.argmin()]
        if top > best[0] or errs.min() < best[1]:
            best = (int(top), float(errs.min()), (s[k], t[k]))
    if best[2] is None or best[0] < MIN_ANCHORS:
        raise AlignmentError("Hizalama kareleri şablonla eşleşmedi")
    s, t = best[2]
    dist = np.abs((s * c + t)[:, None] - a[None, :])
    anchorIdx = np.where(dist.min(axis=0) < COARSE_TOL)[0]
    candIdx = dist[:, anchorIdx].argmin(axis=0)
    return candIdx, anchorIdx


def coarseHomography(cands: np.ndarray, template: FormTemplate, expectedScale: float
                     ) -> Tuple[np.ndarray, int]:
    candIdx, anchorIdx = matchAnchors(cands, template.anchors, expectedScale)
    h, _ = cv2.findHomography(cands[candIdx], template.anchors[anchorIdx], 0)
    if h is None:
        raise AlignmentError("Homografi hesaplanamadı")
    # homografiyle yeniden eşleştir: benzerliğin kaçırdığı çapaları kazan, sapanları at
    dist = np.linalg.norm(applyHomography(h, cands)[:, None] - template.anchors[None], axis=2)
    anchorIdx = np.where(dist.min(axis=0) < FINE_TOL)[0]
    if len(anchorIdx) >= MIN_ANCHORS:
        candIdx = dist[:, anchorIdx].argmin(axis=0)
        h2, _ = cv2.findHomography(cands[candIdx], template.anchors[anchorIdx], 0)
        if h2 is not None:
            h = h2
    return h, len(anchorIdx)


def detectCircles(gray: np.ndarray, template: FormTemplate) -> np.ndarray:
    r = template.bubbleRadius
    circles = cv2.HoughCircles(cv2.GaussianBlur(gray, (5, 5), 0), cv2.HOUGH_GRADIENT, dp=1,
                               minDist=0.72 * template.pitch, param1=120, param2=22,
                               minRadius=int(r - 4), maxRadius=int(r + 4))
    if circles is None:
        return np.zeros((0, 2))
    return circles[0, :, :2].astype(np.float64)


def matchCircles(circles: np.ndarray, cellPoints: np.ndarray, tol: float
                 ) -> Tuple[np.ndarray, np.ndarray]:
    """Her hücre için tol içindeki en yakın çember. Dönüş: (hücreIndeksleri, çemberIndeksleri)."""
    if len(circles) == 0:
        return np.zeros(0, int), np.zeros(0, int)
    dist = np.linalg.norm(cellPoints[:, None] - circles[None], axis=2)
    nearest = dist.argmin(axis=1)
    cellIdx = np.where(dist[np.arange(len(cellPoints)), nearest] < tol)[0]
    return cellIdx, nearest[cellIdx]


def localCellPoints(circles: np.ndarray, template: FormTemplate) -> Tuple[np.ndarray, float]:
    """Hücre merkezlerini bulunan çemberlere oturtur; çemberi olmayan hücreye yakın
    komşularının ortalama sapmasını uygular (kâğıt eğriliği gibi düzlem dışı bozulmalar için)."""
    pts = template.cellPoints.copy()
    if len(pts) == 0:
        return pts, 1.0
    cellIdx, circIdx = matchCircles(circles, pts, SNAP_TOL)
    if len(cellIdx) == 0:
        return pts, 0.0
    residual = circles[circIdx] - pts[cellIdx]
    matched = np.zeros(len(pts), bool)
    matched[cellIdx] = True
    radius = 5 * template.pitch
    for i in np.where(~matched)[0]:
        near = np.linalg.norm(pts[cellIdx] - pts[i], axis=1) < radius
        if near.any():
            pts[i] += residual[near].mean(axis=0)
    pts[cellIdx] = circles[circIdx]
    return pts, len(cellIdx) / float(len(pts))


def pageLevels(value: np.ndarray) -> Tuple[float, float]:
    """(kâğıt beyazı, en koyu düzey). Soluk/sıkıştırılmış taramalarda siyah ~100'e çıkabildiği için
    eşikler sabit değil, bu iki düzeye göre kurulur."""
    sample = value[::4, ::4]
    return float(np.median(sample)), float(np.percentile(sample, 0.5))


def countMatches(h: np.ndarray, circles: np.ndarray, template: FormTemplate) -> int:
    if len(circles) == 0 or len(template.cells) == 0:
        return 0
    return len(matchCircles(applyHomography(h, circles), template.cellPoints, CIRCLE_MATCH_TOL)[0])


def coarseFromTiming(gray: np.ndarray, value: np.ndarray, markThreshold: float,
                     template: FormTemplate, expectedScale: float) -> Tuple[np.ndarray, int]:
    size = tuple(v / expectedScale for v in template.timingSize) if template.timingSize else None
    marks, _ = findTimingMarks(value, markThreshold, size)
    if len(marks) < MIN_MARKS:
        raise AlignmentError("Zamanlama işaretleri bulunamadı")
    hypotheses = timingHypotheses(marks, template.timingMarks)
    if not hypotheses:
        raise AlignmentError("Zamanlama işaretleri şablonla eşleşmedi")
    # kafes periyodik olduğundan yanlış kayma da çoğu baloncuğu tutturur; en çok tutturan doğrudur
    work = cv2.resize(gray, None, fx=expectedScale, fy=expectedScale, interpolation=cv2.INTER_AREA
                      if expectedScale < 1 else cv2.INTER_LINEAR)
    circles = detectCircles(work, template) / expectedScale
    counts = [countMatches(h, circles, template) for h in hypotheses]
    return hypotheses[int(np.argmax(counts))], len(marks)


def fineAlign(gray: np.ndarray, h: np.ndarray, template: FormTemplate) -> Tuple[np.ndarray, np.ndarray]:
    """İnce düzeltme: kanonik görüntüdeki çemberleri şablon hücrelerine oturtan düzeltme homografisi.
    Dönüş: (düzeltilmiş homografi, kanonik çember merkezleri)."""
    size = (template.width, template.height)
    warped = cv2.warpPerspective(gray, h, size, flags=cv2.INTER_LINEAR, borderValue=255)
    circles = detectCircles(warped, template)
    cellIdx, circIdx = matchCircles(circles, template.cellPoints, CIRCLE_MATCH_TOL)
    if len(cellIdx) >= 50:
        fix, _ = cv2.findHomography(circles[circIdx], template.cellPoints[cellIdx], cv2.RANSAC, 3.0)
        if fix is not None:
            h = fix @ h
            circles = applyHomography(fix, circles)
    return h, circles


def alignPage(image: np.ndarray, template: FormTemplate) -> Alignment:
    color = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    value = color.max(axis=2)   # en parlak kanal: renkli form baskısı silikleşir, kurşun kalem koyu kalır
    paperWhite, darkLevel = pageLevels(value)
    markThreshold = darkLevel + 0.3 * (paperWhite - darkLevel)
    size = (template.width, template.height)
    # sayfanın görüntüyü doldurduğu varsayımıyla beklenen ölçek; eşleştirme 0.6-1.6 katını kabul eder
    expectedScale = min(template.width, template.height) / float(min(gray.shape))

    def coarse(method: str) -> Tuple[np.ndarray, int]:
        if method == "timing":
            return coarseFromTiming(gray, value, markThreshold, template, expectedScale)
        cands = findSquares(value, markThreshold, template.anchorSize / expectedScale)
        return coarseHomography(cands, template, expectedScale)

    # Şablonun yöntemi önce denenir. Aynı formun karesiz baskıları olabildiğinden (dolu baloncuklar
    # kare sanılıp saçma bir dönüşüm çıkabilir) sonuç baloncuk örtüşmesiyle doğrulanır; tutmazsa
    # şablonda verisi olan diğer yöntem denenir.
    available = {"anchors": len(template.anchors) >= MIN_ANCHORS, "timing": len(template.timingMarks) >= MIN_MARKS}
    other = "anchors" if template.alignment == "timing" else "timing"
    methods = [m for m in (template.alignment, other) if available[m]]
    if not methods:
        raise AlignmentError("Şablonda hizalama işareti yok (en az 4 kare veya 10 zamanlama işareti gerekli)")
    canVerify = len(template.cells) >= 50
    best, errors = None, []
    for method in methods:
        try:
            h, markCount = coarse(method)
        except AlignmentError as e:
            errors.append(str(e))
            continue
        h, circles = fineAlign(gray, h, template)
        cellPoints, ratio = localCellPoints(circles, template)
        if best is None or ratio > best[3]:
            best = (h, markCount, cellPoints, ratio, method)
        if not canVerify or ratio >= GOOD_MATCH_RATIO:
            break
    if best is None:
        raise AlignmentError("; ".join(errors))
    h, markCount, cellPoints, ratio, method = best
    if canVerify and ratio < MIN_MATCH_RATIO:
        raise AlignmentError("Sayfa şablonla hizalanamadı: hizalama işaretleri eşleşti ama baloncuklar "
                             f"yerinde değil (örtüşme %{round(ratio * 100)}). Form bu şablona ait olmayabilir")

    valueOut = cv2.warpPerspective(value, h, size, flags=cv2.INTER_LINEAR, borderValue=255)
    colorOut = cv2.warpPerspective(color, h, size, flags=cv2.INTER_LINEAR,
                                   borderValue=(255, 255, 255))
    return Alignment(valueOut, colorOut, cellPoints, h, markCount, ratio, paperWhite, darkLevel, method)
