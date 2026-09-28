"""Kullanım: python -m omr.cli tarama.jpg [tarama2.pdf ...] [--out out] [--annotated] [--form optik129]"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from .annotate import drawAnnotated
from .export import exportTxt
from .pages import iterPages
from .reader import readPage
from .template import loadTemplate


def main() -> None:
    ap = argparse.ArgumentParser(description="Optik form okuyucu")
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--form", default="optik129")
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--annotated", action="store_true", help="işaretleme sonucu görsellerini de yaz")
    args = ap.parse_args()

    template = loadTemplate(args.form)
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for path in args.inputs:
        for pageNo, image in iterPages(path):
            if image is None:
                print(f"{path.name}: açılamadı")
                continue
            result, alignment = readPage(image, template)
            data = result.toDict()
            data["source"] = {"file": path.name, "page": pageNo}
            results.append(data)
            if not result.ok:
                print(f"{path.name} s.{pageNo}: HATA {result.error}")
                continue
            print(f"{path.name} s.{pageNo}")
            for f in result.fields.values():
                print(f"  {f.title:11s} {f.value}")
            for flag in result.flags:
                print(f"  ! {flag['message']}")
            if args.annotated:
                cv2.imwrite(str(args.out / f"{path.stem}_{pageNo}.jpg"),
                            drawAnnotated(alignment, template, result),
                            [cv2.IMWRITE_JPEG_QUALITY, 80])
    (args.out / "sonuclar.json").write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    (args.out / "sonuclar.txt").write_bytes(exportTxt(results, template))


if __name__ == "__main__":
    main()
