import pytest

from omr.fmt import FmtError, importFmt, mergeStacked, parseFmt

FMT = """05=04=04=D=*= =
01=02=01=03=K=Y=A B=X=[KITAPCIK]
03=04=01=01=K=Y= =X=[BOS]
03=05=01=02=S=D=012=X=[NO]
03=05=04=04=S=D=011=X=[SINIF-1]
03=05=04=04=S=D=901=X=[SINIF-2]
""".encode("windows-1254")


def grid(cells, x0=100.0, y0=200.0, pitch=40.0):
    return {"circles": [[x0 + c * pitch, y0 + r * pitch, 16.0] for r, c in cells]}


def formCells():
    cells = [(0, 0), (0, 2), (1, 0), (1, 2)]                      # kitapçık A/B x 2 satır
    cells += [(r, c) for r in (2, 3, 4) for c in (0, 1)]          # no: 3 satır x 2 hane
    cells += [(r, 3) for r in (2, 3, 4)]                          # sınıf
    cells += [(r, c) for r in range(8, 14) for c in range(6)]     # kafes adımı bulunabilsin diye dolgu
    return cells


def testParseAndMerge():
    header, entries = parseFmt(FMT)
    assert header == {"rows": 5, "cols": 4, "multi": "*", "blank": " "}
    merged = mergeStacked(entries)
    assert [e.name for e in merged] == ["KITAPCIK", "BOS", "NO", "SINIF"]
    assert merged[3].labels == ["09", "10", "11"]


def testImport():
    out = importFmt(FMT, grid(formCells()))
    fields = {f["name"]: f for f in out["fields"]}
    assert list(fields) == ["kitapcik", "no", "sinif"]
    k = fields["kitapcik"]
    assert (k["type"], k["rows"], k["cols"], k["labels"], k["stepX"]) == ("rows", 2, 2, ["A", "B"], 80.0)
    assert (k["x"], k["y"]) == (100.0, 200.0)
    assert (fields["no"]["x"], fields["no"]["y"], fields["no"]["rows"], fields["no"]["cols"]) == (100.0, 280.0, 3, 2)
    assert fields["sinif"]["x"] == 220.0
    items = out["export"]["items"]
    assert [(i["kind"], i.get("field"), i["width"]) for i in items] == [
        ("field", "kitapcik", 2), ("space", None, 2), ("field", "no", 2), ("field", "sinif", 2)]
    assert out["report"]["matchRatio"] == 1.0 and out["report"]["warnings"] == []


def testRejectsGarbage():
    with pytest.raises(FmtError):
        parseFmt(b"bu bir fmt degil")
