"""题目学科与考点分类。"""
from __future__ import annotations

import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import taxonomy  # noqa: E402

NODE_KW = taxonomy.node_keywords()

EXTRA_KW = {
    "xf-xx": ["刑法的机能", "规制机能", "保障机能", "保护机能", "刑法的任务", "刑法的形式", "但书", "广义刑法", "狭义刑法", "单行刑法", "附属刑法"],
    "xf-xfzl": ["特殊预防", "一般预防", "刑罚的目的", "刑罚的功能"],
    "xf-lx": ["认罪认罚", "量刑情节", "法定情节", "酌定情节"],
    "xf-fz3": ["组织领导传销", "传销活动", "伪造货币", "出售购买运输假币", "生产销售有毒有害食品", "生产销售不符合安全标准的食品", "生产销售伪劣产品"],
    "xf-fz6": ["拒不执行判决", "裁定罪", "考试作弊", "组织考试作弊", "传授犯罪方法"],
    "mf-7": ["主物", "从物", "孳息", "拾得遗失物"],
    "mf-21": ["机动车交通事故", "好意同乘", "机动车", "交通事故"],
    "mf-18": ["婚约", "彩礼", "同居"],
    "mf-19": ["遗嘱见证人", "见证人"],
    "mf-15": ["快递", "网购", "网络购物", "格式条款"],
    "fl-4": ["社会规范", "区别于其他社会规范", "国家强制性", "规范性", "法律形式", "规范作用"],
    "fl-8": ["非规范性法律文件", "规范性法律文件", "法的形式"],
    "fl-18": ["法律解释主体", "解释主体", "立法解释", "司法解释", "行政解释"],
    "fl-22": ["法律责任的竞合", "归责原则", "免责条件"],
    "xa-2": ["比例原则", "权力清单", "责任清单"],
    "xa-10": ["监督法", "备案审查", "合宪性"],
    "xa-26": ["人大代表执行职务", "代表保障", "言论免责"],
    "xa-31": ["互联网法院", "在线诉讼"],
    "xa-12": ["法律与道德", "权利和义务所指向的对象", "集会", "游行", "示威", "结社", "言论自由", "出版自由"],
    "fz-1": ["律博士", "篇目", "法规汇编", "元朝", "中华法系", "盗贼重法", "铸刑书", "铸刑鼎", "竹刑", "春秋", "中国土地法大纲", "立法思想", "吕刑", "甫刑", "九刑", "禹刑", "汤刑", "明德慎罚", "天罚", "礼法合一"],
    "fz-2": ["非公室告", "公室告", "三风十愆", "圜土", "受财", "六赃", "刺配", "耻辱刑", "象刑", "义绝", "七出", "三不去", "存留养亲", "保辜", "眚", "非眚", "惟终", "惟眚", "刑制改革", "斩左趾", "宫刑", "发遣", "顾山", "女徒顾山", "测立", "刑讯", "五听", "三宥", "三赦"],
    "fz-3": ["官制", "官吏", "监察", "考课", "三风十愆", "理藩院", "蒙古律例", "回疆则例", "苗例", "少数民族"],
    "fz-4": ["诸色人", "出典", "典卖", "婚姻", "继承", "契约", "义绝", "和离", "七出", "三不去", "民事主体", "人身依附"],
    "fz-6": ["复核", "录囚", "非公室告", "诉讼", "监狱", "圜土", "廷尉", "中渭桥", "张释之", "大理寺", "刑部", "御史台", "都察院", "测立", "刑讯", "告诉", "直诉", "越诉", "登闻鼓", "法院编制法"],
    "fz-7": ["中国土地法大纲", "土地法大纲"],
    "fz-8": ["中华苏维埃共和国宪法大纲", "陕甘宁边区施政纲领"],
    "fz-9": ["盗贼重法", "重法地"],
}
for nid, extra in EXTRA_KW.items():
    if nid in NODE_KW:
        NODE_KW[nid]["keywords"] = list(dict.fromkeys(NODE_KW[nid]["keywords"] + extra))
SUBJECTS = {s["id"]: s for s in taxonomy.SUBJECTS}

SUBJECT_HINTS = {
    "xingfa": [
        ("犯罪构成", 6), ("犯罪故意", 6), ("犯罪过失", 6), ("正当防卫", 6), ("紧急避险", 6),
        ("共同犯罪", 6), ("犯罪未遂", 6), ("犯罪中止", 6), ("犯罪预备", 6), ("罪数", 6),
        ("法条竞合", 5), ("想象竞合", 5), ("牵连犯", 5), ("吸收犯", 5),
        ("刑罚", 4), ("量刑", 4), ("缓刑", 5), ("假释", 5), ("减刑", 5), ("追诉时效", 5),
        ("自首", 5), ("立功", 5), ("累犯", 5), ("数罪并罚", 5), ("刑事责任", 4),
        ("法定刑", 5), ("罪名", 5), ("单位犯罪", 5), ("不作为", 5), ("因果关系", 3),
        ("贪污", 5), ("受贿", 5), ("行贿", 5), ("盗窃", 4), ("抢劫", 4), ("诈骗罪", 5),
        ("故意杀人", 5), ("故意伤害", 5), ("绑架", 5), ("拐卖", 5), ("毒品", 5),
        ("国家工作人员", 3), ("主犯", 4), ("从犯", 4), ("教唆犯", 5), ("既遂", 3),
        ("罪", 1), ("刑", 1),
    ],
    "minfa": [
        ("民事法律行为", 6), ("民事法律关系", 6), ("民事主体", 6), ("诉讼时效", 6),
        ("物权", 6), ("债权", 5), ("合同", 4), ("侵权", 6), ("婚姻", 5), ("继承", 5),
        ("人格权", 6), ("代理", 5), ("抵押", 5), ("质押", 5), ("留置", 5), ("担保", 5),
        ("所有权", 5), ("用益物权", 6), ("占有", 5), ("著作权", 5), ("专利权", 5),
        ("商标", 5), ("知识产权", 5), ("不当得利", 6), ("无因管理", 6), ("违约责任", 6),
        ("要约", 5), ("承诺", 3), ("法人", 5), ("自然人", 4), ("监护", 5), ("收养", 5),
        ("离婚", 5), ("抚养", 3), ("遗产", 5), ("遗嘱", 5), ("损害赔偿", 4),
        ("相邻关系", 5), ("业主", 4), ("居住权", 5), ("地役权", 5),
        ("民事", 2), ("赔偿", 1),
    ],
    "fali": [
        ("法的本质", 8), ("法的特征", 8), ("法的作用", 8), ("法的价值", 8),
        ("法律规则", 8), ("法律原则", 8), ("法律渊源", 8), ("法的效力", 8),
        ("法律部门", 8), ("法律体系", 8), ("法律监督", 8), ("法律解释", 8),
        ("法律推理", 8), ("法律论证", 8), ("法律关系", 7), ("法律责任", 8),
        ("法律制裁", 8), ("法律职业", 6), ("法律文化", 6), ("法律意识", 6),
        ("法律移植", 6), ("法律继承", 6), ("法的起源", 6), ("法理学", 8),
        ("法系", 6), ("法治", 5), ("依法治国", 5), ("立法", 4), ("执法", 5),
        ("司法", 5), ("守法", 5), ("权利能力", 4), ("法律事实", 6), ("法学", 4),
        ("法律", 2),
    ],
    "xianfa": [
        ("宪法", 6), ("全国人民代表大会", 8), ("全国人大常委会", 8), ("国务院", 7),
        ("国家主席", 7), ("中央军事委员会", 7), ("监察委员会", 7), ("人民法院", 6),
        ("人民检察院", 6), ("公民基本权利", 8), ("基本权利", 7), ("选举", 6),
        ("民族区域自治", 8), ("特别行政区", 8), ("一国两制", 8), ("基层群众自治", 8),
        ("村民委员会", 6), ("居民委员会", 6), ("合宪性审查", 8), ("违宪", 7),
        ("宪法解释", 8), ("宪法修改", 8), ("人民代表大会制度", 8), ("民主集中制", 6),
        ("国家机构", 7), ("国家性质", 7), ("行政区划", 7), ("立法法", 7),
        ("法律保留", 7), ("备案审查", 7), ("基本义务", 7), ("宗教信仰自由", 7),
        ("人大代表", 6), ("人民代表大会代表", 7), ("罢免", 6), ("质询", 6),
        ("预算", 6), ("税收", 5), ("国旗", 6), ("国歌", 6), ("国徽", 6),
        ("自然资源", 6), ("水流", 5), ("土地所有", 6), ("国家所有", 5),
        ("民族自治机关", 8), ("自治区", 6), ("自治州", 6), ("自治县", 6),
        ("澳门", 5), ("香港", 5), ("基本法", 6), ("行政长官", 6), ("立法会", 6),
    ],
    "fazhishi": [
        ("唐律", 10), ("宋刑统", 10), ("大明律", 10), ("大清律例", 10), ("法经", 10),
        ("九章律", 10), ("北齐律", 10), ("开皇律", 10), ("十恶", 9), ("八议", 9),
        ("官当", 9), ("五刑", 7), ("秋审", 9), ("会审", 8), ("领事裁判权", 10),
        ("会审公廨", 10), ("马锡五", 10), ("临时约法", 9), ("钦定宪法大纲", 10),
        ("天坛宪草", 9), ("贿选宪法", 9), ("训政时期约法", 9), ("陕甘宁", 9),
        ("中华苏维埃", 9), ("西周", 7), ("汉代", 7), ("唐朝", 7), ("宋代", 7),
        ("明朝", 7), ("清朝", 7), ("清末", 7), ("北洋政府", 9), ("南京国民政府", 9),
        ("南京临时政府", 9), ("革命根据地", 7), ("御史台", 7), ("大理寺", 7),
        ("刑部", 7), ("都察院", 7), ("科举", 7), ("三省六部", 7), ("郡县", 7),
        ("均田", 7), ("两税法", 7), ("一条鞭法", 7), ("摊丁入亩", 7), ("六礼", 7),
        ("七出", 7), ("三不去", 7), ("春秋决狱", 7), ("登闻鼓", 7), ("直诉", 7),
        ("会典", 6), ("编敕", 7), ("律疏", 7), ("刑律", 5), ("律博士", 8),
        ("宣政院", 8), ("理藩院", 7), ("九卿", 6), ("律", 2), ("秦朝", 6),
        ("汉朝", 6), ("魏晋", 6), ("南北朝", 6), ("隋朝", 6), ("元朝", 6),
    ],
}

GENERIC_TERMS = {"法律", "罪", "刑", "民事", "赔偿", "律", "法学", "权利", "义务"}

STRICT_HINTS = {
    sid: [(t, w) for t, w in terms if t not in GENERIC_TERMS]
    for sid, terms in SUBJECT_HINTS.items()
}
STRICT_HINTS["fazhishi"] += [
    ("西周", 10), ("秦朝", 10), ("汉朝", 10), ("唐朝", 10), ("宋朝", 10), ("元朝", 10),
    ("明朝", 10), ("清朝", 10), ("魏晋", 9), ("南北朝", 9), ("隋朝", 9), ("唐律", 10),
    ("宋刑统", 10), ("大明律", 10), ("大清律例", 10), ("法经", 10), ("九章律", 10),
    ("北齐律", 10), ("开皇律", 10), ("临时约法", 10), ("钦定宪法大纲", 10),
    ("天坛宪草", 10), ("贿选宪法", 10), ("训政时期约法", 10), ("中华民国民法", 10),
    ("六法全书", 10), ("律博士", 10), ("宣政院", 10), ("理藩院", 10), ("编敕", 9),
    ("秋审", 10), ("朝审", 10), ("会审", 9), ("御史台", 9), ("大理寺", 9),
    ("刑部", 9), ("都察院", 9), ("领事裁判权", 10), ("会审公廨", 10), ("马锡五", 10),
    ("八议", 10), ("十恶", 10), ("官当", 10), ("五刑", 8), ("六礼", 8), ("七出", 8),
    ("三不去", 8), ("春秋决狱", 9), ("登闻鼓", 9), ("直诉", 9), ("科举", 8),
    ("三省六部", 9), ("郡县", 9), ("均田", 9), ("两税法", 9), ("一条鞭法", 9),
    ("摊丁入亩", 9), ("沈家本", 10), ("大清现行刑律", 10), ("大清新刑律", 10),
    ("暂行新刑律", 10), ("陕甘宁", 9), ("中华苏维埃", 9), ("革命根据地", 9),
    ("北洋政府", 9), ("南京国民政府", 9), ("南京临时政府", 9),
]
STRICT_HINTS["fali"] += [("法的实施", 7), ("法的制定", 7), ("法的适用", 7), ("法律规范", 7), ("法律条文", 7)]
STRICT_HINTS["xianfa"] += [
    ("宪法", 8), ("全国人民代表大会", 10), ("全国人大常委会", 10), ("国务院", 9),
    ("国家主席", 9), ("中央军事委员会", 9), ("监察委员会", 9), ("人民法院", 8),
    ("人民检察院", 8), ("公民基本权利", 10), ("基本权利", 9), ("选举", 8),
    ("民族区域自治", 10), ("特别行政区", 10), ("一国两制", 10), ("基层群众自治", 10),
    ("村民委员会", 9), ("居民委员会", 9), ("合宪性审查", 10), ("违宪", 9),
    ("宪法解释", 10), ("宪法修改", 10), ("人民代表大会制度", 10), ("国家机构", 9),
    ("国家性质", 9), ("行政区划", 9), ("立法法", 9), ("备案审查", 9), ("基本义务", 9),
    ("宗教信仰自由", 9), ("人大代表", 9), ("罢免", 9), ("质询", 9), ("预算", 8),
    ("国旗", 9), ("国歌", 9), ("国徽", 9), ("民族自治机关", 10), ("基本法", 9),
    ("行政长官", 9), ("立法会", 9),
]


def strict_subject_scores(text: str) -> dict:
    return {sid: score_terms(text, hints) for sid, hints in STRICT_HINTS.items()}

SUBJECT_ORDER = {
    "基础课": ["xingfa", "minfa"],
    "综合课": ["fali", "xianfa", "fazhishi"],
}


def clean(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def score_terms(text: str, terms: list[tuple[str, int]]) -> int:
    s = 0
    for term, w in terms:
        c = text.count(term)
        if c:
            s += w * min(c, 3)
    return s


def subject_scores(text: str) -> dict:
    return {sid: score_terms(text, hints) for sid, hints in SUBJECT_HINTS.items()}


def segment_run(items, scores, subs):
    """在题目连续段内按给定学科顺序切分，返回 {题号: 学科}。"""
    n = len(items)
    nums = [q["number"] for q in items]
    k = len(subs)
    neg = -10**9
    dp = [[neg] * (k + 1) for _ in range(n + 1)]
    back = [[0] * (k + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    pref = [[0] * (n + 1) for _ in range(k)]
    for si, sid in enumerate(subs):
        for i in range(1, n + 1):
            pref[si][i] = pref[si][i - 1] + scores[nums[i - 1]][sid]
    for i in range(1, n + 1):
        for j in range(1, k + 1):
            si = j - 1
            for p in range(i):
                if dp[p][j - 1] == neg:
                    continue
                val = dp[p][j - 1] + pref[si][i] - pref[si][p]
                if val > dp[i][j]:
                    dp[i][j] = val
                    back[i][j] = p
    best_j, best_v = 0, neg
    for j in range(1, k + 1):
        if dp[n][j] - 3 * j > best_v:
            best_v, best_j = dp[n][j] - 3 * j, j
    cuts = []
    i, j = n, best_j
    while j > 0:
        p = back[i][j]
        cuts.append((p, i, subs[j - 1]))
        i, j = p, j - 1
    cuts.reverse()
    assign = {}
    for p, qn, sid in cuts:
        for t in range(p, qn):
            assign[nums[t]] = sid
    for num in nums:
        assign.setdefault(num, subs[0])
    return assign


def segment_paper(items, scores, paper):
    """按题型连续段切分；每段允许使用学科顺序中的任意连续子序列。"""
    order = SUBJECT_ORDER[paper]
    assign = {}
    run = []
    last_type = None
    for q in items + [None]:
        if q is None or (last_type is not None and q["type"] != last_type):
            if run:
                best, best_v = None, -10**9
                for s in range(len(order)):
                    for j in range(1, len(order) - s + 1):
                        subs = order[s:s + j]
                        cand = segment_run(run, scores, subs)
                        # 以逐题最高分之和作为该切分的评价（等价于 DP 值）
                        v = sum(scores[r["number"]][sid] for r in run for sid in [cand[r["number"]]])
                        v -= 2 * j
                        if v > best_v:
                            best, best_v = cand, v
                assign.update(best or {r["number"]: order[0] for r in run})
            run = []
        if q is None:
            break
        run.append(q)
        last_type = q["type"]
    return assign


def fixed_subject(year, degree, paper, number):
    """依据官方试卷结构确定学科；无法确定时返回 None。"""
    if paper == "基础课":
        if degree == "非法学":
            if year == 2010:
                return "xingfa" if number <= 30 else "minfa"
            if number <= 40:
                return "xingfa" if number <= 20 else "minfa"
            if number <= 50:
                return "xingfa" if number <= 45 else "minfa"
            if year <= 2017:
                if number in (51, 52, 55, 57, 59):
                    return "xingfa"
                if number in (53, 54, 56, 58, 60):
                    return "minfa"
            else:
                if number in (51, 52, 55, 57):
                    return "xingfa"
                if number in (53, 54, 56, 58):
                    return "minfa"
        else:
            if year == 2010:
                return "xingfa" if number <= 19 else "minfa"
            if number <= 20:
                return "xingfa" if number <= 10 else "minfa"
            if number <= 30:
                return "xingfa" if number <= 25 else "minfa"
            if number <= 34:
                return "xingfa" if number <= 32 else "minfa"
            if number <= 36:
                return "xingfa" if number == 35 else "minfa"
            if number <= 38:
                return "xingfa" if number == 37 else "minfa"
        return None

    # 综合课
    if degree == "非法学":
        if year <= 2017:
            if number <= 45:
                return "fali" if number <= 15 else ("xianfa" if number <= 30 else "fazhishi")
            if number <= 63:
                return "fali" if number <= 51 else ("xianfa" if number <= 57 else "fazhishi")
            if number <= 66:
                return ["fali", "xianfa", "fazhishi"][number - 64]
            if number <= 69:
                return ["fali", "xianfa", "fazhishi"][number - 67]
            if number == 70:
                return "fali"
        else:
            if number <= 40:
                return "fali" if number <= 12 else ("xianfa" if number <= 27 else "fazhishi")
            if number <= 50:
                return "fali" if number <= 43 else ("xianfa" if number <= 47 else "fazhishi")
            if number <= 53:
                return ["fali", "xianfa", "fazhishi"][number - 51]
            if number <= 56:
                return ["fali", "xianfa", "fazhishi"][number - 54]
            if number == 57:
                return "fali"
            if number == 58:
                return "fazhishi" if year == 2018 else "xianfa"
        return None

    # 法学 综合课
    if number <= 20:
        return "fali" if number <= 7 else ("xianfa" if number <= 14 else "fazhishi")
    if 31 <= number <= 33:
        return ["fali", "xianfa", "fazhishi"][number - 31]
    return None

def topic_score(text: str, node_id: str) -> float:
    info = NODE_KW[node_id]
    s = 0.0
    name = info["name"]
    if name and name in text:
        s += 8
    for kw in info["keywords"]:
        if not kw:
            continue
        c = text.count(kw)
        if not c:
            continue
        w = 3.0 if len(kw) >= 4 else (2.0 if len(kw) == 3 else 1.2)
        s += w * min(c, 3)
    return s


def classify_topic(text: str, subject: str) -> tuple[str | None, float]:
    candidates = [(nid, info) for nid, info in NODE_KW.items() if info["subject"] == subject]
    best, best_s = None, 0.0
    for nid, info in candidates:
        s = topic_score(text, nid)
        if s > best_s:
            best, best_s = nid, s
    return best, best_s


def main():
    src = os.path.join(ROOT, "work", "base_questions.json")
    qs = json.load(open(src, encoding="utf-8"))
    by_paper = {}
    for q in qs:
        by_paper.setdefault((q["year"], q["degree"], q["paper"]), []).append(q)
    for key, items in by_paper.items():
        # 去重后按题号
        items.sort(key=lambda x: x["number"])
        scores = {}
        for q in items:
            text = clean(q["stem"] + q.get("material", "") + "".join(q["options"].values()) + q["explanation"])
            scores[q["number"]] = strict_subject_scores(text)
        assign = segment_paper(items, scores, key[2])
        for q in items:
            text = clean(q["stem"] + q.get("material", "") + "".join(q["options"].values()) + q["explanation"])
            fixed = fixed_subject(q["year"], q["degree"], q["paper"], q["number"])
            sid = fixed or assign[q["number"]]
            if fixed:
                sc = strict_subject_scores(text)
                alt = max(sc, key=sc.get)
                if alt != fixed and sc[alt] >= 20 and sc[alt] > sc[fixed] * 2 + 16:
                    sid = alt
            q["subject"] = sid
            tid, sc = classify_topic(text, sid)
            q["topic"] = tid
            q["topicScore"] = round(sc, 1)
    with open(os.path.join(ROOT, "work", "classified.json"), "w", encoding="utf-8") as f:
        json.dump(qs, f, ensure_ascii=False, indent=1)
    # 统计
    from collections import Counter
    c = Counter((q["subject"], q.get("topic")) for q in qs)
    print("subjects:", Counter(q["subject"] for q in qs))
    none = [q for q in qs if not q["topic"]]
    print("unclassified", len(none))
    for q in none[:10]:
        print(q["id"], q["stem"][:60])
    print("top topics:")
    for (s, t), n in c.most_common(15):
        print(s, t, n)


if __name__ == "__main__":
    main()
