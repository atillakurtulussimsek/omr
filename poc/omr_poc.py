"""OMR kavram kanıtı - Testofis OPTİK-129 (YKS) formu
Kullanım: python3 omr_poc.py tarama.jpg
Not: Bölge koordinatları bu örnek taramaya göre sabit girildi. Üretimde köşe kareleri +
zamanlama işaretleriyle hizalanıp sabit bir şablon (JSON) kullanılmalı."""
import sys, cv2, numpy as np

im = cv2.imread(sys.argv[1]); g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
circ = cv2.HoughCircles(cv2.GaussianBlur(g, (5, 5), 0), cv2.HOUGH_GRADIENT, dp=1, minDist=28,
                        param1=120, param2=22, minRadius=12, maxRadius=19)[0]

def cluster(v, gap=12):
    v = np.sort(v); cl = [[v[0]]]
    for x in v[1:]:
        (cl[-1].append(x) if x - cl[-1][-1] < gap else cl.append([x]))
    return [float(np.mean(k)) for k in cl if len(k) >= 3]

def fill(x, y, r=10):
    x, y = int(round(x)), int(round(y))
    roi = g[y-r:y+r+1, x-r:x+r+1]
    yy, xx = np.ogrid[-r:r+1, -r:r+1]
    return float((roi[xx*xx + yy*yy <= r*r] < 120).mean())

def grid(x0, x1, y0, y1):
    a = circ[(circ[:,0]>x0)&(circ[:,0]<x1)&(circ[:,1]>y0)&(circ[:,1]<y1)]
    X, Y = cluster(a[:,0]), cluster(a[:,1])
    F = np.zeros((len(Y), len(X))); P = np.zeros((len(Y), len(X), 2))
    for i, y in enumerate(Y):
        for j, x in enumerate(X):
            d = np.hypot(a[:,0]-x, a[:,1]-y); k = d.argmin()
            P[i,j] = (a[k,0], a[k,1]) if d[k] < 8 else (x, y)
            F[i,j] = fill(*P[i,j])
    return F, P

def mark(P, F, thr=0.5):
    for i in range(F.shape[0]):
        for j in range(F.shape[1]):
            if F[i,j] > thr:
                cv2.circle(im, tuple(int(v) for v in P[i,j]), 17, (0, 200, 0), 3)

for name, (x0, x1) in {'TÜRKÇE':(960,1160), 'SOSYAL':(1190,1390), 'MATEMATİK':(1420,1620), 'FEN':(1650,1850)}.items():
    F, P = grid(x0, x1, 800, 2600); mark(P, F)
    ans = []
    for row in F:
        m = ['ABCDE'[j] for j, v in enumerate(row) if v > 0.5]
        ans.append(m[0] if len(m) == 1 else ('-' if not m else '*'))   # * = çift işaret
    print(f"{name:10s}", ''.join(ans))

F, P = grid(440, 650, 240, 640); mark(P, F)
print('Öğrenci no:', ''.join(str(int(F[:,j].argmax())) if F[:,j].max() > 0.5 else '_' for j in range(F.shape[1])))
L = 'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ'
F, P = grid(100, 880, 1400, 2600); mark(P, F)
print('Ad Soyad  :', ''.join(L[int(F[:,j].argmax())] if F[:,j].max() > 0.5 else ' ' for j in range(F.shape[1])).strip())
cv2.imwrite('okuma_sonucu.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, 80])
