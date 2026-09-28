"""Referans görsel: yeni form tanımlarken boş form taramasını kanonik uzaya çevirir ve
editör için baloncukları + hizalama karelerini algılar.

Yeni şablonda kanonik uzay, referans görselin düzeltilmiş halidir: baloncuklar düzenli bir
kafese oturtulup (homografi) eğim ve perspektif giderilir; kafes bulunamazsa görsel olduğu gibi kalır.
Var olan şablona referans yüklenirse görsel şablonun kanonik uzayına hizalanır."""
from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

from .align import AlignmentError, alignPage, applyHomography, pageLevels
from .timing import findTimingMarks
from .template import FormTemplate

CANONICAL_WIDTH = 2000
MIN_LATTICE_RATIO = 0.7      # kafese oturan baloncuk oranı bunun altındaysa düzeltme uygulanmaz
LATTICE_TOL = 0.2            # kafes birimi


def houghCircles(gray: np.ndarray, minDist: float, minRadius: int, maxRadius: int) -> np.ndarray:
    circles = cv2.HoughCircles(cv2.GaussianBlur(gray, (5, 5), 0), cv2.HOUGH_GRADIENT, dp=1,
                               minDist=minDist, param1=120, param2=22,
                               minRadius=minRadius, maxRadius=maxRadius)
    return np.zeros((0, 3)) if circles is None else circles[0].astype(np.float64)


def detectBubbles(gray: np.ndarray) -> np.ndarray:
    """(x, y, r) dizisi. Yarıçap bilinmediği için önce geniş aralıkta aranır, sonra daraltılır."""
    rough = houghCircles(gray, 20, 8, 26)
    if len(rough) < 20:
        return rough
    radius = float(np.median(rough[:, 2]))
    return houghCircles(gray, 1.8 * radius, int(radius - 4), int(radius + 4))


def neighborPitch(points: np.ndarray, axis: int, radius: float) -> Optional[float]:
    """Aynı satırdaki (axis=0) / sütundaki (axis=1) en yakın komşu mesafelerinin ortancası."""
    other = 1 - axis
    steps = []
    for p in points:
        d = points - p
        ok = (np.abs(d[:, other]) < radius) & (d[:, axis] > radius)
        if ok.any():
            steps.append(d[ok, axis].min())
    return float(np.median(steps)) if len(steps) >= 10 else None


def fitLattice(points: np.ndarray, pitchX: float, pitchY: float) -> Optional[np.ndarray]:
    """Noktaları tam sayı kafes düğümlerine taşıyan homografi (görüntü -> kafes birimi).
    Yoğun bölgeden başlayıp çevreye doğru büyüyerek indeks ataması yapar."""
    center = np.median(points, axis=0)
    seed = points[np.linalg.norm(points - center, axis=1).argmin()]
    h = np.array([[1 / pitchX, 0, -seed[0] / pitchX], [0, 1 / pitchY, -seed[1] / pitchY], [0, 0, 1]])
    dist = np.linalg.norm((points - seed) / (pitchX, pitchY), axis=1)
    for radius in (4, 8, 13, 20, 30, 45, 1e9, 1e9):
        q = applyHomography(h, points)
        err = np.linalg.norm(q - np.rint(q), axis=1)
        ok = (dist < radius) & (err < LATTICE_TOL)
        if ok.sum() < 8:
            return None
        h2, _ = cv2.findHomography(points[ok], np.rint(q[ok]), cv2.RANSAC, 0.15)
        if h2 is None:
            return None
        h = h2
    q = applyHomography(h, points)
    ratio = (np.linalg.norm(q - np.rint(q), axis=1) < LATTICE_TOL).mean()
    return h if ratio >= MIN_LATTICE_RATIO else None


def rectify(image: np.ndarray) -> Tuple[np.ndarray, bool]:
    """Görseli CANONICAL_WIDTH genişliğe getirir; kafes bulunursa eğim/perspektifi giderir."""
    scale = CANONICAL_WIDTH / float(image.shape[1])
    image = cv2.resize(image, None, fx=scale, fy=scale,
                       interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bubbles = detectBubbles(gray)
    if len(bubbles) < 30:
        return image, False
    points, radius = bubbles[:, :2], float(np.median(bubbles[:, 2]))
    pitchX, pitchY = neighborPitch(points, 0, radius), neighborPitch(points, 1, radius)
    if not pitchX or not pitchY:
        return image, False
    lattice = fitLattice(points, pitchX, pitchY)
    if lattice is None:
        return image, False
    # kafes birimi -> piksel; görüntü merkezi yerinde kalsın
    h, w = gray.shape
    center = np.array([[w / 2.0, h / 2.0]])
    u = applyHomography(lattice, center)[0]
    toPixels = np.array([[pitchX, 0, center[0, 0] - pitchX * u[0]],
                         [0, pitchY, center[0, 1] - pitchY * u[1]], [0, 0, 1]])
    warp = toPixels @ lattice
    return cv2.warpPerspective(image, warp, (w, h), flags=cv2.INTER_LINEAR,
                               borderValue=(255, 255, 255)), True


def findAnchors(value: np.ndarray, threshold: float) -> Tuple[List[List[float]], float]:
    """Dolu hizalama kareleri (merkezler) ve ortanca kenar uzunluğu."""
    width = value.shape[1]
    minSide, maxSide = 0.008 * width, 0.035 * width
    _, bw = cv2.threshold(value, threshold, 255, cv2.THRESH_BINARY_INV)
    k = max(3, int(round(0.5 * minSide)))
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    n, _, stats, centroids = cv2.connectedComponentsWithStats(bw)
    found = []
    for i in range(1, n):
        _, _, w, h, area = stats[i]
        if minSide <= w <= maxSide and minSide <= h <= maxSide \
                and area / float(w * h) > 0.85 and min(w, h) / float(max(w, h)) > 0.8:
            found.append((float(centroids[i][0]), float(centroids[i][1]), (w + h) / 2.0))
    if not found:
        return [], 0.0
    side = float(np.median([f[2] for f in found]))
    anchors = [[round(x, 1), round(y, 1)] for x, y, s in found if 0.75 * side <= s <= 1.25 * side]
    return anchors, side


def detect(canonical: np.ndarray) -> dict:
    gray = cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY)
    bubbles = detectBubbles(gray)
    value = canonical.max(axis=2)
    paperWhite, darkLevel = pageLevels(value)
    threshold = darkLevel + 0.3 * (paperWhite - darkLevel)
    anchors, anchorSize = findAnchors(value, threshold)
    marks, markSize = findTimingMarks(value, threshold)
    if len(bubbles):  # taşırılarak doldurulmuş baloncuklar kare sanılmasın
        anchors = [a for a in anchors
                   if np.linalg.norm(bubbles[:, :2] - a, axis=1).min() > 0.6 * np.median(bubbles[:, 2])]
    return {
        "circles": [[round(x, 1), round(y, 1), round(r, 1)] for x, y, r in bubbles],
        "bubbleRadius": round(float(np.median(bubbles[:, 2])), 1) if len(bubbles) else 16,
        "anchors": anchors,
        "anchorSize": round(anchorSize, 1),
        "timingMarks": [[round(x, 1), round(y, 1)] for x, y in marks],
        "timingSize": [round(v, 1) for v in markSize],
    }


def prepareNew(image: np.ndarray) -> Tuple[np.ndarray, dict, bool]:
    """Yeni şablon için: (kanonik görsel, algılama, düzeltme uygulandı mı)."""
    canonical, rectified = rectify(image)
    return canonical, detect(canonical), rectified


def prepareExisting(image: np.ndarray, template: FormTemplate) -> Tuple[np.ndarray, dict]:
    """Var olan şablonun kanonik uzayına hizalanmış görsel + algılama. AlignmentError fırlatabilir."""
    canonical = alignPage(image, template).color
    return canonical, detect(canonical)
