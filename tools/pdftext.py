"""PDF 文本提取：优先使用 PDF 自带文本层，按版式还原阅读顺序。

- 双栏排版的真题：按左右栏分别排序，避免左右栏交错。
- 单栏排版（含四列选项）：按 y 再 x 排序。
- 解析 PDF：大多为正常文字流，直接采用 PDF 文本顺序。
- 扫描页（2024 等）返回空文本，交给 OCR 管线。
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass

import pymupdf

WATERMARK_KEYS = (
    "光速考研", "淘宝", "历年法硕真题解析", "享受完美售后", "详细解析请联系",
    "公众号", "小红书", "秋北", "领取更多备考资料", "加微信", "微信",
)

# 允许的字符：CJK、ASCII 可打印、常用中英文标点
PUNCT = set("，。；：？！、（）《》“”‘’—…·,.;:?!()[]<>\"'%&+-/=*#@_～~｜|【】〔〕「」『』")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def readable(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    if CONTROL_RE.search(text):
        return False
    good = 0
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            good += 1
        elif ch.isascii() and ch.isprintable():
            good += 1
        elif ch in PUNCT or ch in " \t\u3000":
            good += 1
    return good / max(1, len(text)) >= 0.9


def normalize_line(t: str) -> str:
    t = t.replace("\u3000", " ").replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t


def drop_line(t: str, y: float, h: float) -> bool:
    if not t:
        return True
    if not readable(t):
        return True
    compact = re.sub(r"\s+", "", t)
    if any(k in compact for k in WATERMARK_KEYS):
        return True
    if y < 52 or y > h - 34:
        return True
    if re.fullmatch(r"[-—\s]*\d{1,3}[-—\s]*", t):
        return True
    return False


@dataclass
class Line:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2


def page_lines(page) -> list[Line]:
    h = page.rect.height
    lines: list[Line] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for ln in block.get("lines", []):
            t = normalize_line("".join(s.get("text", "") for s in ln.get("spans", [])))
            if drop_line(t, ln["bbox"][1], h):
                continue
            lines.append(Line(*ln["bbox"], t))
    return lines


def is_two_column(lines: list[Line], width: float) -> bool:
    if len(lines) < 8:
        return False
    # 有横跨中缝的整行文本，说明是单栏排版（选项可能分成多列）
    cross = sum(1 for l in lines if l.x0 < width * 0.3 and l.x1 > width * 0.7)
    if cross >= 3:
        return False
    wide = sum(1 for l in lines if (l.x1 - l.x0) > width * 0.55)
    if wide / len(lines) > 0.18:
        return False
    left = sum(1 for l in lines if l.x1 < width * 0.55)
    right = sum(1 for l in lines if l.x0 > width * 0.45)
    return left >= 3 and right >= 3


def order_page(page, layout: bool = True) -> str:
    lines = page_lines(page)
    width = page.rect.width
    if not lines:
        return ""
    if not layout:
        return "\n".join(l.text for l in lines)
    if is_two_column(lines, width):
        left = sorted([l for l in lines if l.cx < width / 2], key=lambda l: (round(l.y0 / 3), l.x0))
        right = sorted([l for l in lines if l.cx >= width / 2], key=lambda l: (round(l.y0 / 3), l.x0))
        return "\n".join(l.text for l in left + right)
    ordered = sorted(lines, key=lambda l: (round(l.y0 / 3), l.x0))
    return "\n".join(l.text for l in ordered)


def raw_page(page) -> str:
    h = page.rect.height
    out = []
    for t in page.get_text("text").splitlines():
        t = normalize_line(t)
        if drop_line(t, h / 2, h):  # 对 raw 文本没有坐标，仅按内容过滤
            continue
        out.append(t)
    return "\n".join(out)


def extract(path: str) -> dict:
    doc = pymupdf.open(path)
    pages = []
    for page in doc:
        raw = raw_page(page)
        layout = order_page(page, layout=True)
        pages.append({"raw": raw, "layout": layout})
    return {"path": path, "pages": pages, "page_count": doc.page_count}


if __name__ == "__main__":
    path = sys.argv[1]
    data = extract(path)
    print(f"pages={data['page_count']}", file=sys.stderr)
    for i, p in enumerate(data["pages"]):
        print(f"===== PAGE {i + 1} (LAYOUT) =====")
        print(p["layout"])
