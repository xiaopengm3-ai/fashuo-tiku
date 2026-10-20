"""从真题/解析文本中解析题目与答案。"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field

import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import pdftext  # noqa: E402

TEXT_DIR = os.path.join(ROOT, "work", "text")
OCR_DIR = os.path.join(ROOT, "work", "ocr", "papers")

SECTION_TYPES = {
    "单项选择题": "single", "单选题": "single",
    "多项选择题": "multiple", "多选题": "multiple",
    "简答题": "short", "辨析题": "debate",
    "法条分析题": "article", "案例分析题": "case",
    "分析题": "analysis", "材料分析题": "analysis",
    "论述题": "essay", "分析论述题": "essay",
}
SECTION_RE = re.compile(
    r"^\s*([一二三四五六七八九十]+)\s*[、.．:：]\s*"
    r"(单项选择题|单选题|多项选择题|多选题|简答题|辨析题|法条分析题|案例分析题|材料分析题|分析论述题|论述题|分析题)"
)
Q_RE = re.compile(r"^\s*(\d{1,3})\s*[.．、,，]\s*")
Q_SPACE_RE = re.compile(r"^\s*(\d{1,3})\s+(?=[\u4e00-\u9fff\u201c\u2018《])")


def match_q(text: str):
    m = Q_RE.match(text) or Q_SPACE_RE.match(text)
    return int(m.group(1)) if m else None
OPT_RE = re.compile(r"^\s*([ABCD])\s*(?:[.．、:：]\s*|\s+)")
OPT_SPLIT_RE = re.compile(r"(?=(?:^|\s)([ABCD])(?:[.．、:：]|\s))")

HEADER_RE = re.compile(
    r"^(第\s*\d+\s*页|专业基础课|专业综合课|.*真题试卷$|.*联考真题$|.*答案详解$|.*答案$|—+\s*专业|\d{4}\s*年全国.*(真题|考试|试卷))"
)
PAGE_NO_RE = re.compile(r"^\s*[-—]?\s*\d{1,3}\s*[-—]?\s*$")


def map_section(title: str) -> str:
    for k, v in SECTION_TYPES.items():
        if k in title:
            return v
    return "objective"


@dataclass
class TextLine:
    text: str
    x0: float | None = None
    y0: float | None = None


@dataclass
class Question:
    number: int
    qtype: str
    stem: str
    options: dict = field(default_factory=dict)
    raw: str = ""
    page: int = 0


NUM_LINE_FIX = [
    (re.compile(r"^([lI])\s*[.．、]"), r"1."),
    (re.compile(r"^([lI])(?=\d)"), "1"),
    (re.compile(r"^([gG])\s*[.．、]"), r"9."),
    (re.compile(r"^([Zz])\s*[.．、]"), r"2."),
    (re.compile(r"^([Ss])\s*[.．、]"), r"5."),
]


def normalize_ocr_line(t: str) -> str:
    # OCR 把题号拆成 "1 1." / "1 6."
    t = re.sub(r"^(\d)\s+(\d{1,2})\s*([.．、,，])", r"\1\2\3", t)
    for pat, rep in NUM_LINE_FIX:
        if pat.match(t):
            t = pat.sub(rep, t, count=1)
            break
    # 选项字母小写 -> 大写（仅当后面紧跟选项分隔符）
    m = re.match(r"^([a-d])\s*([.．、:：])", t)
    if m:
        t = m.group(1).upper() + m.group(2) + t[m.end():]
    return t


def clean_text(t: str) -> str:
    t = t.replace("\u3000", " ").replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t


def load_ocr_pages(path: str) -> list[list[TextLine]]:
    pages: list[list[TextLine]] = []
    cur = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("===== PAGE"):
                if cur:
                    pages.append(cur)
                cur = []
            elif line.strip():
                cur.append(TextLine(normalize_ocr_line(clean_text(line))))
    if cur:
        pages.append(cur)
    return pages


def load_pdf_pages(path: str) -> list[list[TextLine]]:
    doc = pymupdf.open(path)
    raw_pages = []
    single_mode = False
    cross_total = 0
    wide_total = 0
    line_total = 0
    for page in doc:
        lines = pdftext.page_lines(page)
        width = page.rect.width
        cross_total += sum(1 for l in lines if l.x0 < width * 0.3 and l.x1 > width * 0.7)
        wide_total += sum(1 for l in lines if (l.x1 - l.x0) > width * 0.55)
        line_total += len(lines)
        raw_pages.append((lines, width))
    if cross_total >= 3 or (line_total and wide_total / line_total > 0.18):
        single_mode = True
    pages = []
    for lines, width in raw_pages:
        two = (not single_mode) and pdftext.is_two_column(lines, width)
        if two:
            left = sorted([l for l in lines if l.cx < width / 2], key=lambda l: (round(l.y0 / 3), l.x0))
            right = sorted([l for l in lines if l.cx >= width / 2], key=lambda l: (round(l.y0 / 3), l.x0))
            ordered = left + right
        else:
            ordered = sorted(lines, key=lambda l: (round(l.y0 / 3), l.x0))
        pages.append([TextLine(normalize_ocr_line(l.text), l.x0, l.y0) for l in ordered])
    return pages


def is_header(t: str) -> bool:
    if PAGE_NO_RE.match(t):
        return True
    if HEADER_RE.match(t):
        return True
    if re.search(r"第\s*\d+\s*页\s*[（(]?共\s*\d+\s*页", t):
        return True
    return False


def split_inline_options(text: str) -> tuple[str, list[tuple[str, str]]]:
    """把同一行中的 A. ... B. ... 拆开。"""
    matches = list(re.finditer(r"([ABCD])\s*[.．、]\s*", text))
    if not matches:
        return text, []
    stem = text[: matches[0].start()].strip()
    opts = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        opts.append((m.group(1), text[m.end():end].strip()))
    return stem, opts


def finalize_options(opts: dict[str, str]) -> dict[str, str]:
    out = {}
    for k in "ABCD":
        v = opts.get(k, "").strip()
        v = re.sub(r"\s+", " ", v)
        v = re.sub(r"(?<=[\u4e00-\u9fff])[一C]$", "", v)  # OCR 行尾噪声
        out[k] = v.strip(" ：:，,;；")
    return out


def parse_true_pages(pages: list[list[TextLine]]) -> list[Question]:
    # 先整理为 (page, line) 序列
    seq = []
    for pno, lines in enumerate(pages):
        for ln in lines:
            if is_header(ln.text):
                continue
            seq.append((pno, ln))

    # 找到题号链
    starts = []
    last = 0
    seen = set()
    for idx, (pno, ln) in enumerate(seq):
        n = match_q(ln.text)
        if n is None or n in seen or n > 90:
            continue
        if n > last + 6 and n <= 99 and n // 11 == last + 1 and n % 11 == 0:
            n = last + 1
        if n == last + 1 or (last == 0 and n == 1):
            starts.append((idx, n)); seen.add(n); last = n
        elif n > last and n <= last + 6:
            # 可能漏了少数题，仍然接受以保持后续连续
            starts.append((idx, n)); seen.add(n); last = n
        elif n < last and n >= 1:
            # 版式错位导致小题排到后面（如整段案例题）
            starts.append((idx, n)); seen.add(n)
    questions: list[Question] = []
    section_at = {}
    range_rules = []
    for idx, (pno, ln) in enumerate(seq):
        m = SECTION_RE.match(ln.text)
        if m:
            section = map_section(m.group(2))
            section_at[idx] = section
            rng = re.search(r"(\d{1,3})\s*[~～\-—至]\s*(\d{1,3})", ln.text)
            if not rng and idx + 1 < len(seq):
                rng = re.search(r"(\d{1,3})\s*[~～\-—至]\s*(\d{1,3})", seq[idx + 1][1].text)
            if rng:
                range_rules.append((int(rng.group(1)), int(rng.group(2)), section))
    starts.sort(key=lambda x: x[0])
    for si, (start, qn) in enumerate(starts):
        end = starts[si + 1][0] if si + 1 < len(starts) else len(seq)
        pno, first = seq[start]
        num = qn
        m = re.match(r"^\s*\d{1,3}\s*[.．、,，]?\s*", first.text)
        # 当前题目所属 section：优先按题号范围，其次最近 heading
        sec = "single"
        for a, b, st in range_rules:
            if a <= num <= b:
                sec = st
                break
        else:
            for idx in range(start, -1, -1):
                if idx in section_at:
                    sec = section_at[idx]
                    break
        body = [first.text[m.end():].strip()]
        body_lines = [(first, body[0])]
        for j in range(start + 1, end):
            t = seq[j][1].text
            if SECTION_RE.match(t):
                break
            body_lines.append((seq[j][1], t))
            body.append(t)

        # 拆分选项
        opts: dict[str, str] = {}
        stem_parts = []
        cur = None
        for ln, t in body_lines:
            if not t:
                continue
            om = OPT_RE.match(t)
            if om:
                cur = om.group(1)
                rest = t[om.end():].strip()
                # 行内还有后续选项
                stem0, inline = split_inline_options(rest)
                if inline:
                    if stem0:
                        opts[cur] = (opts.get(cur, "") + " " + stem0).strip()
                    else:
                        opts[cur] = ""
                    for k, v in inline:
                        cur = k
                        opts[k] = v
                else:
                    opts[cur] = rest
                continue
            if cur is not None:
                # 选项续行 vs 题干续行
                if ln.x0 is not None and ln.x0 < 45:
                    stem_parts.append(t)
                    cur = None
                elif re.search(r"[（(]\s*[）)]\s*$", t) or t.startswith(("下列", "关于", "甲", "乙", "丙", "丁")):
                    # 可能是题干被 OCR 置后
                    if not opts.get(cur):
                        opts[cur] = t
                    else:
                        opts[cur] += " " + t
                else:
                    opts[cur] = (opts.get(cur, "") + " " + t).strip()
            else:
                stem_parts.append(t)

        stem = "".join(stem_parts).strip()
        stem = re.sub(r"^[()（）\s]+", "", stem)
        stem = re.sub(r"([。？！])\1+", r"\1", stem)
        if not stem.endswith(("？", "?", "。", "）", ")")):
            stem = stem.rstrip("，,、;；") + "。"
        questions.append(Question(
            number=num, qtype=sec, stem=stem,
            options=finalize_options(opts) if sec in ("single", "multiple") else {},
            page=pno,
        ))
    questions.sort(key=lambda q: q.number)
    return questions


# ---------------- 解析 ----------------

DIGIT_FIX = {"O": "0", "o": "0", "I": "1", "l": "1", "S": "5", "s": "5", "B": "8", "Z": "2", "g": "9"}


def fix_num(s: str):
    s = (s or "").strip()
    if not s:
        return None
    if s in ("l", "I"):
        return 1
    if s.isdigit():
        return int(s)
    return None

ANS_RE = re.compile(
    r"(?m)^\s*(?:(\d{1,3})\s*[.．、]\s*)?"
    r"[【\[［(（]?\s*(答案要点|答案)\s*[】\]］)）]?\s*[:：]?\s*"
)
DETAIL_RE = re.compile(r"(?m)^\s*(?:(\d{1,3})\s*[.．、]\s*)?[【\[［(（]?\s*(详解)\s*[】\]］)）]?\s*[:：]?\s*")


def repair_answer_numbers(text: str) -> str:
    text = text.replace("参考答案", "答案")
    pat = re.compile(
        r"(?m)^(\s*)([0-9lIoSsBZg]{1,3})(\s*[.．、]\s*(?:[（(]\s*\d\s*[）)]\s*)?"
        r"[【\[［(（]?\s*(?:答案|答案要点|详解|解析))"
    )

    def repl(m):
        tok = m.group(2)
        mapped = "".join(DIGIT_FIX.get(c, c) for c in tok)
        if mapped.isdigit():
            return m.group(1) + mapped + m.group(3)
        return m.group(0)

    return pat.sub(repl, text)


def _blocks_from(text: str, pattern) -> list[dict]:
    matches = list(pattern.finditer(text))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append({"num": fix_num(m.group(1)) if m.group(1) else None,
                    "kind": m.group(2), "raw": text[m.end():end],
                    "start": m.start()})
    return out


def extract_answer_blocks(text: str) -> list[dict]:
    text = text.replace("\r", "")
    text = repair_answer_numbers(text)
    blocks = _blocks_from(text, ANS_RE)
    detail = _blocks_from(text, DETAIL_RE)
    seen = {b["num"] for b in blocks if b["num"] is not None}
    for d in detail:
        if d["num"] is not None and d["num"] not in seen:
            blocks.append(d)
    blocks.sort(key=lambda b: b["start"])
    if not blocks:
        blocks = detail
    return blocks


def align_blocks(blocks: list[dict], qnums: list[int]) -> dict[int, dict]:
    qset = set(qnums)
    used = set()
    out = {}
    ptr = 0
    for b in blocks:
        n = b.get("num")
        target = None
        if n in qset and n not in used and n >= (qnums[ptr] if ptr < len(qnums) else 0):
            target = n
        else:
            while ptr < len(qnums) and qnums[ptr] in used:
                ptr += 1
            if ptr < len(qnums):
                target = qnums[ptr]
        if target is None:
            continue
        ans, expl = split_answer(b["raw"])
        if target in out:
            # 合并同题的多个答案块
            if ans and not out[target]["answer"]:
                out[target]["answer"] = ans
            out[target]["explanation"] = (out[target]["explanation"] + "\n" + clean_explanation(expl)).strip()
        else:
            out[target] = {"answer": ans, "explanation": clean_explanation(expl)}
        used.add(target)
        while ptr < len(qnums) and qnums[ptr] in used:
            ptr += 1
    return out


def parse_answers(text: str) -> list[dict]:
    return extract_answer_blocks(text)


def split_answer(raw: str) -> tuple[str, str]:
    s = raw.strip()
    s = re.sub(r"^[\s:：]+", "", s)
    m = re.match(r"^([A-D]{1,4})(?![A-Za-z\u4e00-\u9fff])", s)
    if m:
        return m.group(1), s[m.end():].strip()
    lines = [x.strip() for x in s.splitlines() if x.strip()]
    if lines and re.fullmatch(r"[A-D]{1,4}", lines[0]):
        return lines[0], "\n".join(lines[1:]).strip()
    m = re.search(r"(?:答案选|故选|答案为|正确答案是|应选)\s*([A-D]{1,4})", s[:300])
    if m:
        return m.group(1), s
    return "", s


def clean_explanation(t: str) -> str:
    t = re.sub(r"(?m)^\s*[【\[]?\s*(解析|点评|详解|特别说明|答案要点)\s*[】\]]?\s*[:：]?\s*", "", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()
