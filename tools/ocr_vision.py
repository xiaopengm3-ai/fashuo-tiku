"""使用 macOS Vision 框架 OCR 扫描页（中文）。

用法:
  python3 tools/ocr_vision.py <pdf> <start> <end> <out.txt> [zoom]

页码从 0 开始，end 不含。输出每页标记及按阅读顺序排列的文本行。
"""
from __future__ import annotations

import os
import sys
import tempfile

import pymupdf
import Quartz
import Vision


def ocr_image(path: str, languages=("zh-Hans", "en-US"), correction: bool = True) -> list[tuple[float, float, float, float, str]]:
    url = Quartz.CFURLCreateFromFileSystemRepresentation(None, path.encode(), len(path.encode()), False)
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setRecognitionLanguages_(list(languages))
    req.setUsesLanguageCorrection_(correction)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision OCR failed: {err}")
    out = []
    for obs in req.results() or []:
        cand = obs.topCandidates_(1)
        if not cand:
            continue
        text = cand[0].string()
        bb = obs.boundingBox()
        # 归一化坐标，转成左上原点
        x0 = bb.origin.x
        y0 = 1 - (bb.origin.y + bb.size.height)
        x1 = x0 + bb.size.width
        y1 = y0 + bb.size.height
        out.append((x0, y0, x1, y1, text))
    return out


def order_items(items):
    """按版式还原阅读顺序：双栏页先左栏后右栏，单栏页按行。"""
    if not items:
        return []
    left, right = [], []
    for it in items:
        x0, y0, x1, y1, _ = it
        cx = (x0 + x1) / 2
        (left if cx < 0.5 else right).append(it)
    # 双栏：两侧都有足够的行，且没有大量横跨两栏的行
    if len(left) >= 6 and len(right) >= 6:
        cross = sum(1 for it in items if it[0] < 0.25 and it[2] > 0.75)
        if cross < max(3, len(items) * 0.12):
            key = lambda it: (round(it[1] / 0.012), it[0])
            return sorted(left, key=key) + sorted(right, key=key)
    return sorted(items, key=lambda it: (round(it[1] / 0.012), it[0]))


def ocr_pdf(pdf: str, start: int, end: int, out_path: str, zoom: float = 2.0, correction: bool = True):
    doc = pymupdf.open(pdf)
    end = min(end, doc.page_count)
    chunks = []
    for i in range(start, end):
        page = doc[i]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            pix.save(tmp)
            items = ocr_image(tmp, correction=correction)
        finally:
            os.unlink(tmp)
        chunks.append(f"===== PAGE {i + 1} =====")
        for it in order_items(items):
            chunks.append(it[4])
        chunks.append("")
        print(f"ocr page {i + 1}/{end}", file=sys.stderr, flush=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(chunks))


if __name__ == "__main__":
    pdf = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    out = sys.argv[4]
    zoom = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
    correction = not (len(sys.argv) > 6 and sys.argv[6] == "nocorr")
    ocr_pdf(pdf, start, end, out, zoom, correction)
