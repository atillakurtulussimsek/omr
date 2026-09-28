"""Sonuçları sabit genişlikli TXT satırlarına çevirir (her sayfa bir satır).

Düzen şablonun `export` tanımından gelir:
  {"encoding": "utf-8" | "windows-1254",
   "items": [{"kind": "field", "field": ad, "width": n, "align": "left"|"right", "pad": " ",
              "blankAs": " ", "multiAs": "*", "map": {"SAY": "2"}},
             {"kind": "text", "text": "..."}, {"kind": "space", "width": n}]}
Dönüşümler grup (soru / hane) bazında uygulanır. Tanım yoksa alanlar şablon sırasıyla,
aralarında birer boşlukla yazılır."""
from __future__ import annotations

from typing import Iterable

from .template import FormTemplate

ENCODINGS = ("utf-8", "windows-1254")
LINE_END = "\r\n"


def defaultExport(template: FormTemplate) -> dict:
    items = []
    for f in template.fields:
        if items:
            items.append({"kind": "space", "width": 1})
        items.append({"kind": "field", "field": f.name, "width": f.width, "align": "left", "pad": " ",
                      "blankAs": " ", "multiAs": "*", "map": {}})
    return {"encoding": "utf-8", "items": items}


def exportOf(template: FormTemplate) -> dict:
    return template.export or defaultExport(template)


def fieldText(item: dict, result: dict, template: FormTemplate) -> str:
    spec = next(f for f in template.fields if f.name == item["field"])
    labels = {c.label for c in spec.groups[0].cells}
    mapping = item.get("map") or {}
    out = []
    for g in (result or {}).get("groups", []):
        value = g["value"]
        if g["status"] == "multi":
            value = item.get("multiAs", "*")
        elif value not in labels:
            value = item.get("blankAs", " ")
        else:
            value = mapping.get(value, value)
        out.append(value)
    text, width = "".join(out), item["width"]
    pad = item.get("pad") or " "
    text = text.rjust(width, pad) if item.get("align") == "right" else text.ljust(width, pad)
    return text[:width]


def formatLine(fields: dict, template: FormTemplate) -> str:
    parts = []
    for item in exportOf(template)["items"]:
        if item["kind"] == "text":
            parts.append(item["text"])
        elif item["kind"] == "space":
            parts.append(" " * item["width"])
        else:
            parts.append(fieldText(item, fields.get(item["field"]), template))
    return "".join(parts)


def exportTxt(pages: Iterable[dict], template: FormTemplate) -> bytes:
    """pages: PageResult.toDict() çıktıları; okunamayan sayfalar atlanır."""
    text = "".join(formatLine(p["fields"], template) + LINE_END for p in pages if p.get("ok"))
    return text.encode(exportOf(template).get("encoding", "utf-8"), errors="replace")
