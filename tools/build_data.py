"""合并真题与解析，生成题库基础数据与 QA 报告。"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import parser  # noqa: E402

MANIFEST = os.path.join(ROOT, "work", "text", "manifest.json")
OCR_DIR = os.path.join(ROOT, "work", "ocr", "papers")
OUT = os.path.join(ROOT, "work")


def ocr_pages(key: str):
    path = os.path.join(OCR_DIR, f"{key}.txt")
    if not os.path.exists(path):
        return None
    return parser.load_ocr_pages(path)


def true_pages(rec):
    pages = ocr_pages(rec["key"])
    if pages:
        return pages
    return parser.load_pdf_pages(rec["path"])


def answer_text(rec):
    path = os.path.join(OCR_DIR, f"{rec['key']}.txt")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    return "\n".join(p["raw"] for p in rec["pages"])


def trim_next_answer(expl: str, qnum: int) -> str:
    """截掉解析尾部误粘进来的下一题答案块。"""
    pat = re.compile(
        r"(?m)(?:^|[\n。；])\s*[•·●\-—.．、]?\s*[iIl]?\s*(\d{1,3})\s*[.．、]?\s*(?:\d\s*)?[【\[]?\s*(?:答案|解析|详解)"
    )
    for m in pat.finditer(expl):
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if n > qnum:
            return expl[:m.start()].strip()
    return expl


MANUAL_ANSWER_FIX = {
    "2024-法学-综合课-10": "C",  # 解析明确 C 项正确，题库答案键误作 D
}

MANUAL_EXPL_FIX = {
    "2010-法学-综合课-4": [("权，国民是制宪权的主体。故选A。", "")],
    "2012-非法学-综合课-12": [("故选C。", "故选B。")],
    "2025-法学-综合课-10": [("正确答案是 B", "正确答案是 D"), ("正确答案是B", "正确答案是D")],
    "2025-非法学-综合课-16": [("正确答案是 B", "正确答案是 D"), ("正确答案是B", "正确答案是D")],
}


def clean_text(t: str) -> str:
    t = re.sub(r"历\s*年\s*法\s*硕\s*真\s*题\s*解\s*析.*", "", t)
    t = re.sub(r"[ \t]+", "", t)
    t = re.sub(r"([。！？；：，、])\1+", r"\1", t)
    t = t.replace("((", "（").replace("))", "）")
    t = t.replace("()", "（）")
    t = re.sub(r"一(?=[。！？])", "", t)  # OCR 行尾噪声
    return t.strip()


ANSWER_OVERRIDES = {
    (2026, "法学", "基础课"): dict(zip(range(1, 21), "DCBDBDBBDCDADBDB A ACD".replace(" ", ""))) | {
        21: "ABD", 22: "BCD", 23: "ABC", 24: "AC", 25: "ABCD",
        26: "ABD", 27: "ABC", 28: "ABCD", 29: "CD", 30: "AD",
    },
    (2026, "非法学", "基础课"): dict(zip(range(1, 41), "CBDDDABADADADCBDBDBBDADBDB AACDACACAADBBB".replace(" ", ""))) | {
        41: "ABD", 42: "BCD", 43: "ABC", 44: "AC", 45: "ABCD",
        46: "ABD", 47: "ABC", 48: "ABCD", 49: "CD", 50: "AD",
    },
    (2026, "法学", "综合课"): dict(zip(range(1, 21), "CBCCAACDBBDADD CADABA".replace(" ", ""))) | {
        21: "CD", 22: "BD", 23: "BCD", 24: "CD", 25: "BC",
        26: "ABD", 27: "ACD", 28: "CD", 29: "BC", 30: "ABCD",
    },
    (2026, "非法学", "综合课"): dict(zip(range(1, 41), "ADBDCCBCCAACDBBDADDCCDDCDDCADAB AACBB CBBD".replace(" ", ""))) | {
        41: "CD", 42: "BD", 43: "BCD", 44: "CD", 45: "BC",
        46: "ABD", 47: "ACD", 48: "CD", 49: "BC", 50: "ABCD",
    },
}


def merge(rec_true, rec_ans):
    qs = parser.parse_true_pages(true_pages(rec_true))
    qnums = sorted(q.number for q in qs)
    qtexts = {}
    for q in qs:
        qtexts[q.number] = q.stem + " " + " ".join(q.options.values())
    ans = parser.align_blocks(parser.parse_answers(answer_text(rec_ans)), qnums, qtexts) if rec_ans else {}
    out = []
    for q in qs:
        a = ans.get(q.number, {})
        answer = (a.get("answer") or "").strip()
        expl = trim_next_answer((a.get("explanation") or "").strip(), q.number)
        stem = clean_text(q.stem)
        options = {k: clean_text(v) for k, v in q.options.items()}
        if q.qtype in ("single", "multiple") and sum(1 for v in q.options.values() if v) == 0:
            if "简述" in q.stem:
                q.qtype = "short"
            elif "论述" in q.stem or "试论" in q.stem:
                q.qtype = "essay"
            elif "案例" in q.stem:
                q.qtype = "case"
            elif "分析" in q.stem:
                q.qtype = "analysis"
            else:
                q.qtype = "short"
        if q.qtype in ("single", "multiple"):
            override = ANSWER_OVERRIDES.get((rec_true["year"], rec_true["degree"], rec_true["paper"]), {})
            if q.number in override:
                answer = override[q.number]
            if not answer:
                # 从解析正文里再找一次
                m = re.search(r"(?:答案选|故选|答案为|应选)\s*([A-D]{1,4})", expl)
                if m:
                    answer = m.group(1)
            qid = f"{rec_true['year']}-{rec_true['degree']}-{rec_true['paper']}-{q.number}"
            answer = MANUAL_ANSWER_FIX.get(qid, answer)
            for old, new in MANUAL_EXPL_FIX.get(qid, []):
                expl = expl.replace(old, new)
        out.append({
            "id": f"{rec_true['year']}-{rec_true['degree']}-{rec_true['paper']}-{q.number}",
            "year": rec_true["year"],
            "degree": rec_true["degree"],
            "paper": rec_true["paper"],
            "number": q.number,
            "type": q.qtype,
            "stem": stem,
            "options": options,
            "answer": answer,
            "explanation": clean_text(expl),
            "material": clean_text(q.material),
            "materialTitle": clean_text(q.material_title),
            "source": os.path.basename(rec_true["path"]),
        })
    # 无“根据以下……”标志、但确为共享材料的个别题组
    extra = {
        (2022, "非法学", "基础课"): {
            "material": "甲（15周岁）深夜闯入临街店铺，意图行窃，被留下理货的店主（系聋哑人）发现。",
            "title": "根据以下案情，回答第9、10、11小题。",
            "nums": (9, 10, 11),
        }
    }
    info = extra.get((rec_true["year"], rec_true["degree"], rec_true["paper"]))
    if info:
        for q in out:
            if q["number"] in info["nums"]:
                q["material"] = info["material"]
                q["materialTitle"] = info["title"]
            # 清掉此前被并入上一题选项的材料尾巴
            for k, v in list(q["options"].items()):
                if info["material"] in v:
                    q["options"][k] = v.split(info["material"])[0].strip()

    return out


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    groups = defaultdict(dict)
    for rec in manifest:
        if rec["year"] and 2010 <= rec["year"] <= 2026:
            groups[(rec["year"], rec["degree"], rec["paper"])][rec["kind"]] = rec
            if rec["kind"] == "解析" and "真题" in os.path.basename(rec["path"]):
                groups[(rec["year"], rec["degree"], rec["paper"])].setdefault("真题", rec)
    all_q = []
    report = []
    for (year, degree, paper), g in sorted(groups.items()):
        if "真题" not in g:
            continue
        rec_t = g["真题"]
        rec_a = g.get("解析")
        name = os.path.basename(rec_t["path"])
        if rec_a is None and (rec_t["year"] >= 2025 and ("答案" in name)):
            rec_a = rec_t
        qs = merge(rec_t, rec_a)
        all_q.extend(qs)
        nums = {q["number"] for q in qs}
        expected = set(range(1, max(nums) + 1)) if nums else set()
        missing = sorted(expected - nums)
        missing_ans = [q["number"] for q in qs if q["type"] in ("single", "multiple") and not q["answer"]]
        bad_opts = [q["number"] for q in qs if q["type"] in ("single", "multiple") and sum(1 for v in q["options"].values() if v) < 4]
        report.append({
            "key": f"{year}-{degree}-{paper}",
            "questions": len(qs),
            "max": max(nums) if nums else 0,
            "missing": missing,
            "missing_ans": missing_ans,
            "bad_opts": bad_opts,
            "has_ans": bool(rec_a),
        })
    with open(os.path.join(OUT, "base_questions.json"), "w", encoding="utf-8") as f:
        json.dump(all_q, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "qa_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"total {len(all_q)}")
    for r in report:
        flag = ""
        if r["missing"] or r["missing_ans"] or r["bad_opts"] or not r["has_ans"]:
            flag = "  <-- CHECK"
        print(f"{r['key']:24s} q={r['questions']:3d} max={r['max']:3d} missing={r['missing'][:6]} ans={len(r['missing_ans'])} opts={len(r['bad_opts'])}{flag}")


if __name__ == "__main__":
    main()
