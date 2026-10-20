"""为所有真题/解析 PDF 生成文本缓存（layout/raw），扫描件标记待 OCR。"""
from __future__ import annotations

import json
import os
import re
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import pdftext  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "work", "text")
os.makedirs(OUT, exist_ok=True)


def classify(path: str) -> dict | None:
    name = os.path.basename(path)
    if not name.lower().endswith(".pdf"):
        return None
    if "背诵宝典" in name or "徐涛" in name:
        return None
    m = re.search(r"(20\d{2})", name)
    year = int(m.group(1)) if m else None
    if year is None and "2005-2009" in name:
        year = 2005
    rel = os.path.relpath(path, ROOT)
    if "非法学" in name:
        degree = "非法学"
    elif "法学" in name:
        degree = "法学"
    elif "09.法硕非法学" in rel:
        degree = "非法学"
    else:
        degree = "法学"
    if year is None and not any(k in name for k in ("法硕", "法律硕士")):
        return None
    paper = "基础课" if "基础" in path else "综合课"
    kind = "解析" if "解析" in path else "真题"
    key = f"{year}-{degree}-{paper}-{kind}"
    return {"key": key, "year": year, "degree": degree, "paper": paper, "kind": kind, "path": path}


def main():
    records = []
    for dirpath, _, files in os.walk(ROOT):
        if "/work/" in dirpath or "/app/" in dirpath or "/.venv" in dirpath:
            continue
        for f in sorted(files):
            if not f.endswith(".pdf"):
                continue
            p = os.path.join(dirpath, f)
            meta = classify(p)
            if not meta:
                continue
            data = pdftext.extract(p)
            total_layout = sum(len(x["layout"]) for x in data["pages"])
            total_raw = sum(len(x["raw"]) for x in data["pages"])
            low_pages = sum(1 for x in data["pages"] if len(x["layout"]) < 60)
            meta.update({
                "pages": data["pages"],
                "page_count": data["page_count"],
                "chars_layout": total_layout,
                "chars_raw": total_raw,
                "low_pages": low_pages,
            })
            records.append(meta)
            print(f"{meta['key']:32s} p={data['page_count']:3d} layout={total_layout:6d} raw={total_raw:6d} low={low_pages}", flush=True)
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    print(f"written {len(records)} records")


if __name__ == "__main__":
    main()
