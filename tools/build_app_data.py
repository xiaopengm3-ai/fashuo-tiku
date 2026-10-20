"""生成网页使用的题库数据。"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import taxonomy  # noqa: E402

OUT = os.path.join(ROOT, "app", "data")
os.makedirs(OUT, exist_ok=True)

tax = taxonomy.taxonomy_json()
node_info = {}
for sub in tax:
    for g in sub["groups"]:
        for n in g["nodes"]:
            node_info[n["id"]] = {"name": n["name"], "group": g["name"], "subject": sub["id"],
                                  "subjectName": sub["name"], "color": sub["color"]}

TYPE_LABEL = {
    "single": "单项选择", "multiple": "多项选择", "short": "简答",
    "debate": "辨析", "article": "法条分析", "case": "案例分析",
    "analysis": "分析", "essay": "论述", "objective": "客观题",
}


def tidy(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"[ \t]+", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def tidy_expl(t: str) -> str:
    t = (t or "").replace("\r", "")
    lines = []
    for line in t.splitlines():
        line = re.sub(r"[ \t]+", "", line).strip()
        if not line:
            continue
        if re.fullmatch(r"\d{1,3}\s*/\s*\d{1,3}", line):
            continue
        if any(k in line for k in ("添加秋北", "公众号", "小红书", "领取更多", "备考群", "秋北先生的藏宝阁")):
            continue
        if re.match(r"^\d{4}\s*年全国硕士研究生招生考试", line):
            continue
        if re.fullmatch(r"(法律硕士.*(试题|答案)|.*答案详解|.*参考答案).*", line) and len(line) < 40:
            continue
        lines.append(line)
    out = ""
    for line in lines:
        if not out:
            out = line
        elif re.match(r"^([【（(]|[一二三四五六七八九十]+、|\d{1,2}[.．、]|（\d|[A-D][.．、])", line):
            out += "\n" + line
        else:
            out += line
    return out.strip()


def main():
    qs = json.load(open(os.path.join(ROOT, "work", "classified.json"), encoding="utf-8"))
    out = []
    for q in qs:
        stem = tidy(q["stem"])
        if len(stem) < 6:
            continue
        opts = {k: tidy(v) for k, v in (q.get("options") or {}).items()}
        objective = q["type"] in ("single", "multiple")
        # 客观题选项缺失太多则丢弃
        if objective and sum(1 for v in opts.values() if v) < 3:
            continue
        if objective:
            ans = re.sub(r"[^A-D]", "", q.get("answer") or "")
            # 根据答案数量修正题型
            qtype = "multiple" if len(ans) > 1 else "single"
        else:
            ans = q.get("answer") or ""
            qtype = q["type"] if q["type"] in ("short", "debate", "article", "case", "analysis", "essay") else "short"
        tinfo = node_info.get(q.get("topic"))
        out.append({
            "id": q["id"], "year": q["year"], "degree": q["degree"], "paper": q["paper"],
            "number": q["number"], "type": qtype, "typeLabel": TYPE_LABEL.get(qtype, "主观题"),
            "subject": q["subject"],
            "subjectName": node_info.get(q.get("topic"), {}).get("subjectName") or {
                "xingfa": "刑法", "minfa": "民法", "fali": "法理学", "xianfa": "宪法", "fazhishi": "法制史",
            }.get(q["subject"], q["subject"]),
            "topic": q.get("topic") or "",
            "topicName": tinfo["name"] if tinfo else "未分类",
            "groupName": tinfo["group"] if tinfo else "其他",
            "stem": stem,
            "options": {k: opts.get(k, "") for k in "ABCD"} if objective else {},
            "answer": ans,
            "explanation": tidy_expl(q.get("explanation") or ""),
            "source": q.get("source", ""),
        })

    # 统计
    for sub in tax:
        sub["count"] = sum(1 for q in out if q["subject"] == sub["id"])
        for g in sub["groups"]:
            for n in g["nodes"]:
                n["count"] = sum(1 for q in out if q["topic"] == n["id"])
            g["count"] = sum(n["count"] for n in g["nodes"])

    obj = [q for q in out if q["type"] in ("single", "multiple")]
    subj = [q for q in out if q["type"] not in ("single", "multiple")]

    def dump(name, data):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    dump("taxonomy.json", tax)
    dump("objective.json", obj)
    dump("subjective.json", subj)
    years = sorted({q["year"] for q in out})
    meta = {
        "total": len(out), "objective": len(obj), "subjective": len(subj),
        "years": years,
        "byYear": dict(Counter(q["year"] for q in out)),
        "byDegree": dict(Counter(q["degree"] for q in out)),
        "generatedAt": "2026-10-20",
    }
    dump("meta.json", meta)
    print("total", len(out), "objective", len(obj), "subjective", len(subj))
    print("subject counts", Counter(q["subject"] for q in out))
    print("missing answers", len([q for q in obj if not q["answer"]]))


if __name__ == "__main__":
    main()
