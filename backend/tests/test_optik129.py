import json
from pathlib import Path

import cv2
import pytest

from omr.export import exportTxt
from omr.reader import readPage
from omr import store
from omr.template import buildTemplate, loadTemplate

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "optik129_ornek01.jpg"
EXPECTED_FILE = SAMPLE.with_suffix(".expected.json")   # gerçek öğrenci verisi: örnekle birlikte git dışında
EXPECTED = json.loads(EXPECTED_FILE.read_text(encoding="utf-8")) if EXPECTED_FILE.is_file() else {}

pytestmark = pytest.mark.skipif(not SAMPLE.is_file() or not EXPECTED, reason="örnek tarama / beklenen sonuç yok")


@pytest.fixture(scope="module")
def template():
    return loadTemplate("optik129")


@pytest.fixture(scope="module")
def image():
    return cv2.imread(str(SAMPLE))


def assertExpected(result):
    assert result.ok, result.error
    for name, value in EXPECTED.items():
        assert result.fields[name].value == value, name


def testSample(template, image):
    result, alignment = readPage(image, template)
    assertExpected(result)
    assert alignment.anchorCount == 10
    assert alignment.circleMatchRatio > 0.95
    assert result.flags == []


@pytest.mark.parametrize("rotation", [cv2.ROTATE_180, cv2.ROTATE_90_CLOCKWISE,
                                      cv2.ROTATE_90_COUNTERCLOCKWISE])
def testRotated(template, image, rotation):
    assertExpected(readPage(cv2.rotate(image, rotation), template)[0])


def testSkewed(template, image):
    h, w = image.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), 2.5, 0.97)
    assertExpected(readPage(cv2.warpAffine(image, m, (w, h), borderValue=(255, 255, 255)), template)[0])


def testTimingAlignment(image):
    """Kare yerine zamanlama işaretleriyle hizalama: aynı sonuç, ters taramada da."""
    spec = store.loadSpec("optik129")
    spec.update(alignment="timing", anchors=[], timingSize=[40, 17],
                timingMarks=[[80, 280 + 40 * i] for i in range(61)])
    template = buildTemplate(spec)
    for page in (image, cv2.rotate(image, cv2.ROTATE_180)):
        result, alignment = readPage(page, template)
        assertExpected(result)
        assert alignment.anchorCount == 61 and alignment.circleMatchRatio > 0.95


def testFallsBackToTimingWithoutSquares(template, image):
    """Aynı formun karesiz baskısı: kareler silinince zamanlama işaretlerine düşer, saçma hizalama üretmez."""
    noSquares = image.copy()
    for x, y in [(1393, 120), (122, 133), (432, 248), (1394, 542), (433, 596), (855, 1360), (126, 1368),
                 (893, 1473), (1810, 2536), (929, 2541)]:
        cv2.rectangle(noSquares, (x - 3, y - 3), (x + 36, y + 36), (255, 255, 255), -1)
    result, alignment = readPage(noSquares, template)
    assertExpected(result)
    assert alignment.method == "timing"


def testWrongFormRejected(template, image):
    """Hizalama işaretleri tutsa bile baloncuklar yerinde değilse sayfa reddedilir."""
    spec = store.loadSpec("optik129")
    for f in spec["fields"]:
        f["x"] += 17
        f["y"] += 19
    result, _ = readPage(image, buildTemplate(spec))
    assert not result.ok and "hizalanamadı" in result.error


def testBlankPageFails(template, image):
    result, alignment = readPage(image * 0 + 255, template)
    assert not result.ok and alignment is None


def testExportTxtDefault(template, image):
    line = exportTxt([readPage(image, template)[0].toDict()], template).decode("utf-8")
    assert line.startswith(f"{EXPECTED['ogrenciNo']} {EXPECTED['adSoyad']:20s} {EXPECTED['sinif']:5s}   {EXPECTED['alan']:3s} {EXPECTED['oturum']} {EXPECTED['kitapcik']} ")
    assert line.endswith("\r\n")
    assert "CDBBEBA D CACBEC  CB " in line          # boş cevap -> boşluk
    assert len(line.rstrip("\r\n")) <= 5 + 20 + 5 + 1 + 3 + 3 + 1 + 8 + 11 + 3 + 40 + 46 + 40 + 40 + 13


def testExportTxtCustom(image):
    spec = store.loadSpec("optik129")
    spec["export"] = {"encoding": "windows-1254", "items": [
        {"kind": "text", "text": "YKS"},
        {"kind": "field", "field": "ogrenciNo", "width": 8, "align": "right", "pad": "0"},
        {"kind": "space", "width": 2},
        {"kind": "field", "field": "alan", "width": 1, "map": {"SAY": "2", "SÖZ": "1"}},
        {"kind": "field", "field": "sube", "width": 1, "blankAs": "?"},
        {"kind": "field", "field": "adSoyad", "width": 12},
        {"kind": "field", "field": "sosyal", "width": 10, "blankAs": ".", "map": {"A": "1"}},
    ]}
    template = buildTemplate(spec)
    data = exportTxt([readPage(image, template)[0].toDict()], template)
    no, ad, sos = EXPECTED["ogrenciNo"], EXPECTED["adSoyad"], EXPECTED["sosyal"][:10]
    alan = {"SAY": "2", "SÖZ": "1"}.get(EXPECTED["alan"], EXPECTED["alan"])
    sosText = "".join("1" if c == "A" else "." if c == "-" else c for c in sos)
    assert data == f"YKS{no:0>8}  {alan}?{ad[:12]}{sosText}\r\n".encode("windows-1254")


def testExportValidation():
    spec = store.loadSpec("optik129")
    spec["export"] = {"encoding": "utf-8", "items": [{"kind": "field", "field": "yok", "width": 3}]}
    with pytest.raises(store.TemplateError):
        buildTemplate(spec)
