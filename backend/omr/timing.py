"""Zamanlama işaretleri: sayfa kenarındaki dolu dikdörtgen dizisi. Hizalama karesi olmayan
formlarda kaba hizalama bunlardan çıkarılır (dönme + ölçek + kayma); kalan hata baloncuklarla düzeltilir."""
from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

MIN_MARKS = 10
MAX_INDEX_SHIFT = 3        # eksik/fazla algılanan uç işaretler için denenen kayma


def darkComponents(value: np.ndarray, threshold: float):
    _, bw = cv2.threshold(value, threshold, 255, cv2.THRESH_BINARY_INV)
    n, _, stats, centroids = cv2.connectedComponentsWithStats(bw)
    return stats[1:], centroids[1:]


def bestLine(points: np.ndarray, tol: float, rounds: int = 400) -> np.ndarray:
    """En çok noktayı tol içinde toplayan doğrunun üzerindeki noktaların indeksleri (RANSAC)."""
    rng = np.random.default_rng(0)
    best = np.zeros(0, int)
    n = len(points)
    for _ in range(rounds):
        i, j = rng.choice(n, 2, replace=False)
        d = points[j] - points[i]
        length = np.hypot(*d)
        if length < 10 * tol:
            continue
        dist = np.abs(d[0] * (points[:, 1] - points[i, 1]) - d[1] * (points[:, 0] - points[i, 0])) / length
        inliers = np.where(dist < tol)[0]
        if len(inliers) > len(best):
            best = inliers
    return best


def findTimingMarks(value: np.ndarray, threshold: float, size: Optional[Tuple[float, float]] = None
                    ) -> Tuple[np.ndarray, Tuple[float, float]]:
    """Doğrusal dizilmiş dolu dikdörtgenlerin merkezleri (dizi boyunca sıralı) ve (uzun, kısa) kenarı.
    size verilirse yalnız o boyuta yakın adaylar alınır (piksel; yön bağımsız)."""
    stats, centroids = darkComponents(value, threshold)
    page = min(value.shape)
    w, h, area = stats[:, 2].astype(float), stats[:, 3].astype(float), stats[:, 4].astype(float)
    longSide, shortSide = np.maximum(w, h), np.minimum(w, h)
    ok = (area / (w * h) > 0.75) & (shortSide >= 4)
    if size:
        ok &= (longSide > 0.6 * size[0]) & (longSide < 1.5 * size[0]) \
            & (shortSide > 0.5 * size[1]) & (shortSide < 1.7 * size[1])
    else:
        ratio = longSide / np.maximum(shortSide, 1)
        ok &= (ratio > 1.5) & (ratio < 7) & (longSide > 0.008 * page) & (longSide < 0.04 * page)
    idx = np.where(ok)[0]
    if len(idx) < MIN_MARKS:
        return np.zeros((0, 2)), (0.0, 0.0)
    points = centroids[idx]
    line = bestLine(points, 0.004 * page)
    if len(line) >= MIN_MARKS:    # aynı doğrudaki farklı boyutlu lekeleri at
        med = np.median(longSide[idx][line])
        line = line[np.abs(longSide[idx][line] - med) < 0.25 * med]
    if len(line) < MIN_MARKS:
        return np.zeros((0, 2)), (0.0, 0.0)
    points = points[line]
    axis = int(np.ptp(points[:, 1]) > np.ptp(points[:, 0]))   # dikey dizi -> y'ye göre sırala
    order = points[:, axis].argsort()
    chosen = idx[line][order]
    return points[order], (float(np.median(longSide[chosen])), float(np.median(shortSide[chosen])))


def markIndices(points: np.ndarray) -> np.ndarray:
    """Sıralı işaretlerin adım cinsinden tam sayı konumları (aradaki eksik işaretler boşluk bırakır)."""
    along = np.linalg.norm(points - points[0], axis=1)
    pitch = np.median(np.diff(along))
    return np.rint(along / pitch).astype(int)


def similarity(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """src -> dst en küçük kareler benzerlik dönüşümü (3x3). Doğrusal noktalarla da tanımlıdır."""
    z, w = src[:, 0] + 1j * src[:, 1], dst[:, 0] + 1j * dst[:, 1]
    zc, wc = z - z.mean(), w - w.mean()
    a = (np.conj(zc) * wc).sum() / (np.abs(zc) ** 2).sum()
    b = w.mean() - a * z.mean()
    return np.array([[a.real, -a.imag, b.real], [a.imag, a.real, b.imag], [0, 0, 1]])


def timingHypotheses(detected: np.ndarray, templateMarks: np.ndarray) -> List[np.ndarray]:
    """Algılanan işaretleri şablondakilerle eşleyen aday dönüşümler: iki yön (düz / 180° dönük)
    x birkaç indeks kayması. En olası olan (düz, kaymasız) başta."""
    tIdx = markIndices(templateMarks)
    out = []
    for shift in sorted(range(-MAX_INDEX_SHIFT, MAX_INDEX_SHIFT + 1), key=abs):
        for points in (detected, detected[::-1]):
            lookup = {int(i) + shift: p for i, p in zip(markIndices(points), points)}
            pairs = [(lookup[int(i)], t) for i, t in zip(tIdx, templateMarks) if int(i) in lookup]
            if len(pairs) >= max(MIN_MARKS, 0.7 * len(templateMarks)):
                src, dst = (np.array(v) for v in zip(*pairs))
                out.append(similarity(src, dst))
    return out
