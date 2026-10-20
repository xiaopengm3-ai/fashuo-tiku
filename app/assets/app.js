/* ============================================================
   法硕真题刷题台
   ============================================================ */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  const LS = {
    ui: "fashuo.ui.v1",
    progress: "fashuo.progress.v1",
    fav: "fashuo.fav.v1",
    draft: "fashuo.draft.v1",
  };

  function readJSON(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch { return fallback; }
  }
  function writeJSON(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* ignore */ }
  }

  const progress = readJSON(LS.progress, {});
  const favorites = new Set(readJSON(LS.fav, []));
  let drafts = readJSON(LS.draft, {});

  const savedUI = readJSON(LS.ui, {});
  const state = {
    mode: savedUI.mode === "subjective" ? "subjective" : "objective",
    groupBy: savedUI.groupBy === "topic" ? "topic" : "subject",
    sort: ["new", "old", "random"].includes(savedUI.sort) ? savedUI.sort : "new",
    filter: Object.assign({
      subject: "", group: "", topic: "", uncat: "", year: "", degree: "", paper: "", status: "", q: "",
    }, savedUI.filter || {}),
    practiceStarted: !!savedUI.practiceStarted,
    index: 0,
    limit: 0,
    seed: Math.random(),
    revealed: false,
    selected: new Set(),
    openSubjects: new Set(savedUI.openSubjects || []),
  };

  let DATA = null;
  let tax = null;
  let nodeMap = new Map();
  let subjectMap = new Map();
  let qmap = new Map();
  let qIndex = { objective: [], subjective: [] };
  let currentList = [];
  let currentQ = null;
  let toastTimer = null;
  let searchTimer = null;

  const SUBJECT_FALLBACK = { xingfa: "刑法", minfa: "民法", fali: "法理学", xianfa: "宪法", fazhishi: "法制史" };

  function saveUI() {
    writeJSON(LS.ui, {
      mode: state.mode, groupBy: state.groupBy, sort: state.sort,
      filter: state.filter, practiceStarted: state.practiceStarted,
      openSubjects: [...state.openSubjects],
    });
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.style.colorScheme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#0d1216" : "#f2ede4");
  }

  function initTheme() {
    let theme = localStorage.getItem("fashuo.theme");
    if (theme !== "light" && theme !== "dark") {
      theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    applyTheme(theme);
  }

  function toggleTheme() {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    localStorage.setItem("fashuo.theme", next);
    applyTheme(next);
    toast(next === "dark" ? "已切换到黑夜模式" : "已切换到白天模式");
  }

  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 1800);
  }

  // ---------- 数据加载 ----------
  async function boot() {
    initTheme();
    try {
      const [meta, taxonomy, objective, subjective] = await Promise.all([
        fetch("data/meta.json", { cache: "no-cache" }).then((r) => r.json()),
        fetch("data/taxonomy.json", { cache: "no-cache" }).then((r) => r.json()),
        fetch("data/objective.json", { cache: "no-cache" }).then((r) => r.json()),
        fetch("data/subjective.json", { cache: "no-cache" }).then((r) => r.json()),
      ]);
      DATA = { meta, objective, subjective };
      tax = taxonomy;
      indexData();
      const params = new URLSearchParams(location.search);
      if (params.get("start") === "1") {
        state.practiceStarted = true;
        if (params.get("subject")) state.filter.subject = params.get("subject");
        if (params.get("topic")) state.filter.topic = params.get("topic");
        if (params.get("year")) state.filter.year = params.get("year");
      }
      bindStatic();
      $("#objCount").textContent = meta.objective.toLocaleString();
      $("#subjCount").textContent = meta.subjective.toLocaleString();
      $("#totalNum").textContent = meta.total.toLocaleString();
      syncControls();
      refreshAll();
    } catch (err) {
      console.error(err);
      $("#view").innerHTML = `
        <div class="empty">
          <h3>题库未能载入</h3>
          <p>请从本地服务器打开本页面，而不是直接双击 HTML 文件。</p>
          <p style="font-size:12px">在项目目录运行 <code>./start.command</code> 或 <code>python3 -m http.server 8765</code></p>
        </div>`;
    }
  }

  function indexData() {
    qmap = new Map();
    qIndex = { objective: DATA.objective, subjective: DATA.subjective };
    for (const list of [DATA.objective, DATA.subjective]) {
      for (const q of list) qmap.set(q.id, q);
    }
    nodeMap = new Map();
    subjectMap = new Map();
    for (const sub of tax) {
      subjectMap.set(sub.id, sub);
      for (const g of sub.groups) {
        for (const n of g.nodes) {
          nodeMap.set(n.id, { ...n, group: g.name, subject: sub.id, subjectName: sub.name, color: sub.color });
        }
      }
    }
  }

  function modeList() { return state.mode === "objective" ? DATA.objective : DATA.subjective; }

  function isDone(q) { return !!progress[q.id]; }

  function subjectName(id) {
    return (subjectMap.get(id) || {}).name || SUBJECT_FALLBACK[id] || id;
  }

  function statusOf(q) {
    const p = progress[q.id];
    if (!p) return "";
    return p.r || "";
  }

  // ---------- 过滤 ----------
  function filteredList() {
    let list = modeList();
    const f = state.filter;
    if (f.subject) list = list.filter((q) => q.subject === f.subject);
    if (f.group) list = list.filter((q) => q.groupName === f.group);
    if (f.topic) list = list.filter((q) => q.topic === f.topic);
    if (f.uncat) list = list.filter((q) => !q.topic);
    if (f.year) list = list.filter((q) => String(q.year) === String(f.year));
    if (f.degree) list = list.filter((q) => q.degree === f.degree);
    if (f.paper) list = list.filter((q) => q.paper === f.paper);
    if (f.status === "todo") list = list.filter((q) => !isDone(q));
    else if (f.status === "done") list = list.filter(isDone);
    else if (f.status === "wrong") list = list.filter((q) => ["wrong", "unknown", "fuzzy"].includes(statusOf(q)));
    else if (f.status === "fav") list = list.filter((q) => favorites.has(q.id));
    if (f.q) {
      const needle = f.q.toLowerCase();
      list = list.filter((q) => {
        const hay = q.stem + " " + (q.material || "") + " " + Object.values(q.options || {}).join(" ") + " " + (q.topicName || "");
        return hay.toLowerCase().includes(needle);
      });
    }
    const arr = list.slice();
    if (state.sort === "new") arr.sort((a, b) => b.year - a.year || a.number - b.number);
    else if (state.sort === "old") arr.sort((a, b) => a.year - b.year || a.number - b.number);
    else {
      const seed = state.seed;
      arr.sort((a, b) => hash(a.id + seed) - hash(b.id + seed));
    }
    if (state.limit > 0) return arr.slice(0, state.limit);
    return arr;
  }

  function hash(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function hasRootFilter() {
    const f = state.filter;
    return !!(f.subject || f.group || f.topic || f.uncat || f.year || f.degree || f.paper || f.status || f.q);
  }

  function shouldShowDashboard() {
    return !state.practiceStarted && !hasRootFilter();
  }

  // ---------- 渲染 ----------
  function refreshAll() {
    updateHeaderStats();
    renderSidebar();
    renderView();
    updatePager();
    saveUI();
  }

  function updateHeaderStats() {
    const list = modeList();
    const done = list.filter(isDone).length;
    $("#doneNum").textContent = done.toLocaleString();
    $("#totalNum").textContent = list.length.toLocaleString();
    const pct = list.length ? Math.round((done / list.length) * 100) : 0;
    $("#miniPct").textContent = pct + "%";
    $("#miniBar").style.width = pct + "%";
    const objDone = DATA.objective.filter(isDone);
    const right = objDone.filter((q) => statusOf(q) === "right").length;
    const wrong = objDone.filter((q) => statusOf(q) === "wrong").length;
    const rate = right + wrong ? Math.round((right / (right + wrong)) * 100) : 0;
    const subjDone = DATA.subjective.filter(isDone);
    const mastered = subjDone.filter((q) => statusOf(q) === "mastered").length;
    $("#miniStats").textContent = state.mode === "objective"
      ? `正确率 ${rate}% · 收藏 ${favorites.size}`
      : `掌握 ${mastered} · 收藏 ${favorites.size}`;
  }

  function subjectProgress(subjectId) {
    const list = modeList().filter((q) => q.subject === subjectId);
    const done = list.filter(isDone).length;
    return { total: list.length, done, pct: list.length ? Math.round((done / list.length) * 100) : 0 };
  }

  function renderSidebar() {
    $("#treeTitle").textContent = state.groupBy === "subject" ? "学科" : "考点";
    const tree = $("#tree");
    if (!DATA) return;
    if (state.groupBy === "subject") {
      const all = modeList();
      const allDone = all.filter(isDone).length;
      let html = treeItemHtml({
        active: !state.filter.subject && !state.filter.topic,
        name: "全部题目",
        dot: "var(--accent)",
        count: all.length,
        pct: all.length ? (allDone / all.length) * 100 : 0,
        attrs: 'data-subject=""',
      });
      for (const sub of tax) {
        const p = subjectProgress(sub.id);
        if (!p.total) continue;
        html += treeItemHtml({
          active: state.filter.subject === sub.id && !state.filter.topic && !state.filter.group,
          name: sub.name,
          dot: `var(--${sub.id === "xingfa" ? "xf" : sub.id === "minfa" ? "mf" : sub.id === "fali" ? "fl" : sub.id === "xianfa" ? "xa" : "fz"})`,
          count: p.total,
          pct: p.pct,
          attrs: `data-subject="${sub.id}"`,
        });
      }
      tree.innerHTML = html;
    } else {
      if (!state._autoOpened && state.openSubjects.size === 0 && !state.filter.subject) {
        const first = tax.find((x) => modeList().some((q) => q.subject === x.id));
        if (first) state.openSubjects.add(first.id);
        state._autoOpened = true;
      }
      let html = "";
      for (const sub of tax) {
        const subCount = modeList().filter((q) => q.subject === sub.id).length;
        if (!subCount) continue;
        const colorVar = `var(--${sub.id === "xingfa" ? "xf" : sub.id === "minfa" ? "mf" : sub.id === "fali" ? "fl" : sub.id === "xianfa" ? "xa" : "fz"})`;
        const open = state.openSubjects.has(sub.id) || state.filter.subject === sub.id;
        let inner = "";
        for (const g of sub.groups) {
          const nodes = g.nodes.filter((n) => n.count > 0);
          if (!nodes.length) continue;
          inner += `<div class="group-label">${esc(g.name)}</div>`;
          for (const n of nodes) {
            inner += `<button class="topic-btn ${state.filter.topic === n.id ? "is-active" : ""}" data-topic="${n.id}">
              <span>${esc(n.name)}</span><span class="num">${n.count}</span></button>`;
          }
        }
        const uncat = modeList().filter((q) => q.subject === sub.id && !q.topic).length;
        if (uncat) {
          inner += `<button class="topic-btn ${state.filter.uncat === sub.id ? "is-active" : ""}" data-uncat="${sub.id}">
            <span>未分类</span><span class="num">${uncat}</span></button>`;
        }
        html += `<details class="acc" data-acc="${sub.id}" ${open ? "open" : ""}>
          <summary style="--subj:${colorVar}"><span class="dot"></span>${esc(sub.name)}<span class="num">${subCount}</span></summary>
          <div class="acc-body">${inner}</div>
        </details>`;
      }
      tree.innerHTML = html;
      $$("details.acc", tree).forEach((d) => {
        d.addEventListener("toggle", () => {
          if (d.open) state.openSubjects.add(d.dataset.acc);
          else state.openSubjects.delete(d.dataset.acc);
          saveUI();
        });
      });
    }
    // 筛选控件状态
    $("#yearSelect").value = state.filter.year || "";
    setPillActive("#degreeRow", state.filter.degree, "degree");
    setPillActive("#paperRow", state.filter.paper, "paper");
    setPillActive("#statusRow", state.filter.status, "status");
    $$("#groupBySeg .seg-btn").forEach((b) => {
      const on = b.dataset.groupby === state.groupBy;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-selected", String(on));
    });
    $$(".mode-btn").forEach((b) => {
      const on = b.dataset.mode === state.mode;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-pressed", String(on));
    });
  }

  function treeItemHtml({ active, name, dot, count, pct, attrs }) {
    return `<button class="tree-item ${active ? "is-active" : ""}" ${attrs}>
      <span class="dot" style="background:${dot}"></span>
      <span class="name">${esc(name)}</span>
      <span class="num">${count}</span>
      <i class="mini-bar" style="width:${Math.max(0, Math.min(100, pct))}%"></i>
    </button>`;
  }

  function setPillActive(rowSel, value, key) {
    $$(rowSel + " .pill").forEach((b) => {
      b.classList.toggle("is-active", (b.dataset[key] || "") === (value || ""));
    });
  }

  function renderView() {
    if (!DATA) return;
    currentList = filteredList();
    if (shouldShowDashboard()) {
      renderDashboard();
      return;
    }
    if (!currentList.length) {
      renderEmpty();
      return;
    }
    if (state.index >= currentList.length) state.index = Math.max(0, currentList.length - 1);
    renderPractice();
  }

  function crumbsHtml() {
    const f = state.filter;
    const bits = [`<button data-clear="all">${state.mode === "objective" ? "客观题" : "主观题"}</button>`];
    if (f.subject) bits.push(`<span class="sep">/</span><button data-clear="subject">${esc(subjectName(f.subject))}</button>`);
    if (f.group) bits.push(`<span class="sep">/</span><button data-clear="group">${esc(f.group)}</button>`);
    if (f.topic) bits.push(`<span class="sep">/</span><span class="here">${esc((nodeMap.get(f.topic) || {}).name || "考点")}</span>`);
    if (f.uncat) bits.push(`<span class="sep">/</span><span class="here">未分类</span>`);
    if (f.status) {
      const label = { todo: "未做", wrong: "做错", done: "已做", fav: "收藏" }[f.status] || "";
      bits.push(`<span class="sep">/</span><span class="here">${label}</span>`);
    }
    if (f.q) bits.push(`<span class="sep">/</span><span class="here">搜索“${esc(f.q)}”</span>`);
    return bits.join("");
  }

  function renderDashboard() {
    $("#crumbs").innerHTML = crumbsHtml();
    bindCrumbClicks();
    const tpl = $("#tpl-dashboard").content.cloneNode(true);
    const modeLabel = state.mode === "objective" ? "客观题" : "主观题";
    $("#heroEyebrow", tpl).textContent = `法律硕士 · 历年真题 · ${modeLabel}`;
    $("#heroTitle", tpl).innerHTML = state.mode === "objective"
      ? "把真题，<br><em>练成手感。</em>"
      : "把答案，<br><em>写成本能。</em>";
    $("#heroSub", tpl).textContent = state.mode === "objective"
      ? "单项选择 · 多项选择 · 按学科与考点双向检索"
      : "简答 · 法条分析 · 案例分析 · 论述 · 对照参考答案自评";

    const list = modeList();
    const done = list.filter(isDone);
    const objDone = DATA.objective.filter(isDone);
    const right = objDone.filter((q) => statusOf(q) === "right").length;
    const wrong = objDone.filter((q) => statusOf(q) === "wrong").length;
    const rate = right + wrong ? Math.round((right / (right + wrong)) * 100) : 0;
    const mastered = DATA.subjective.filter((q) => statusOf(q) === "mastered").length;
    const stats = [
      { n: list.length, label: "本题库题量", sub: `${modeLabel} · 已收录`, color: "var(--accent)" },
      { n: done.length, label: "已完成", sub: `进度 ${list.length ? Math.round(done.length / list.length * 100) : 0}%`, color: "var(--gold)" },
      { n: state.mode === "objective" ? (right + wrong ? rate + "%" : "—") : mastered, label: state.mode === "objective" ? "正确率" : "已掌握", sub: state.mode === "objective" ? `答对 ${right} · 答错 ${wrong}` : "主观题自评", color: "var(--correct)" },
      { n: favorites.size, label: "收藏", sub: "随时回看", color: "var(--xa)" },
    ];
    $("#heroStats", tpl).innerHTML = stats.map((s) => `
      <div class="stat-card" style="--stat-color:${s.color}">
        <div class="stat-num">${s.n}</div>
        <div class="stat-label">${s.label}</div>
        <div class="stat-sub">${s.sub}</div>
      </div>`).join("");

    const grid = $("#dashboardGrid", tpl);
    grid.innerHTML = tax.map((sub) => {
      const p = subjectProgress(sub.id);
      if (!p.total) return "";
      return `<button class="subject-card" data-subject="${sub.id}" style="--subj:var(--${sub.id === "xingfa" ? "xf" : sub.id === "minfa" ? "mf" : sub.id === "fali" ? "fl" : sub.id === "xianfa" ? "xa" : "fz"})">
        <div class="subj-top">
          <span class="subj-seal">${esc(sub.short)}</span>
          <span class="subj-name">${esc(sub.name)}</span>
        </div>
        <div class="subj-count">${p.total}<small>题</small></div>
        <div class="subj-bar"><i style="width:${p.pct}%"></i></div>
        <div class="subj-foot"><span>已练 ${p.done}</span><span>${p.pct}%</span></div>
      </button>`;
    }).join("") + `<button class="subject-card all" data-subject="">
        <div class="subj-count">${list.length}<small>题</small></div>
        <div class="subj-name">全部题目</div>
        <div class="subj-foot"><span>不设筛选</span><span>开始 →</span></div>
      </button>`;

    $("#view").innerHTML = "";
    $("#view").appendChild(tpl);

    $("#startAllBtn").addEventListener("click", () => {
      state.practiceStarted = true;
      state.limit = 0;
      state.index = firstTodoIndex(filteredList());
      refreshAll();
    });
    $("#randomBtn").addEventListener("click", () => {
      state.practiceStarted = true;
      state.sort = "random";
      state.seed = Math.random();
      state.limit = 20;
      state.index = 0;
      $("#sortSelect").value = "random";
      refreshAll();
      toast("随机抽取 20 题");
    });
    $("#wrongBookBtn").addEventListener("click", () => {
      state.filter.status = "wrong";
      state.practiceStarted = true;
      state.limit = 0;
      state.index = 0;
      refreshAll();
    });
    grid.addEventListener("click", (e) => {
      const card = e.target.closest("[data-subject]");
      if (!card) return;
      state.filter = { ...state.filter, subject: card.dataset.subject, group: "", topic: "", status: "", q: "", year: "", degree: "", paper: "" };
      if (!card.dataset.subject) state.filter = defaultFilter();
      state.practiceStarted = true;
      state.limit = 0;
      state.index = 0;
      refreshAll();
      if (window.innerWidth < 900) closeSidebar();
    });
  }

  function defaultFilter() {
    return { subject: "", group: "", topic: "", uncat: "", year: "", degree: "", paper: "", status: "", q: "" };
  }

  function firstTodoIndex(list) {
    const i = list.findIndex((q) => !isDone(q));
    return i < 0 ? 0 : i;
  }

  function renderEmpty() {
    $("#view").innerHTML = `<div class="empty">
      <h3>这里还没有题目</h3>
      <p>试试更换筛选条件，或清除全部筛选回到总览。</p>
      <button class="btn primary" data-clear="all">清除筛选</button>
    </div>`;
    $("#crumbs").innerHTML = crumbsHtml();
    bindCrumbClicks();
    const clearBtn = $("#view [data-clear]");
    if (clearBtn) clearBtn.addEventListener("click", () => {
      state.filter = defaultFilter();
      state.practiceStarted = false;
      state.limit = 0;
      state.index = 0;
      refreshAll();
    });
  }

  function renderPractice() {
    const tpl = $("#tpl-practice").content.cloneNode(true);
    $("#view").innerHTML = "";
    $("#view").appendChild(tpl);
    $("#crumbs").innerHTML = crumbsHtml();
    bindCrumbClicks();

    const list = currentList;
    const q = list[state.index];
    currentQ = q;
    $("#pKicker").textContent = `${q.year} · ${q.degree} · ${q.paper}`;
    $("#pTitle").textContent = `${subjectName(q.subject)} · ${q.topicName || "未分类"}`;
    $("#pCounter").textContent = `${state.index + 1} / ${list.length}`;
    const pbar = $("#pBar");
    if (pbar) pbar.style.width = `${list.length ? ((state.index + 1) / list.length) * 100 : 0}%`;

    renderQuestionCard(q);

    $("#prevBtn").disabled = state.index <= 0;
    $("#nextBtn").disabled = state.index >= list.length - 1;
    $("#prevBtn").addEventListener("click", () => go(-1));
    $("#nextBtn").addEventListener("click", () => go(1));
    $("#jumpBtn").addEventListener("click", openJump);
    $("#shuffleBtn2").addEventListener("click", shuffleNow);
    updatePager();
  }

  function updatePager() {
    const mid = $("#pagerMid");
    if (mid) mid.textContent = currentList.length ? `共 ${currentList.length} 题` : "";
  }

  function renderQuestionCard(q) {
    const host = $("#cardHost");
    host.innerHTML = "";
    const tpl = $("#tpl-question").content.cloneNode(true);
    host.appendChild(tpl);

    const card = $("#qcard");
    const colorVar = `var(--${q.subject === "xingfa" ? "xf" : q.subject === "minfa" ? "mf" : q.subject === "fali" ? "fl" : q.subject === "xianfa" ? "xa" : "fz"})`;
    card.style.setProperty("--subj", colorVar);
    card.setAttribute("data-subject", q.subject);

    $("#qMeta").innerHTML = `
      <span class="chip">${q.year} 年</span>
      <span class="chip">${esc(q.degree)}</span>
      <span class="chip">${q.paper === "基础课" ? "专业基础" : "专业综合"}</span>
      <span class="chip type">${esc(q.typeLabel)}</span>
      <span class="chip subj" data-subject="${q.subject}">${esc(q.subjectName || subjectName(q.subject))}</span>
      <span class="chip topic">${esc(q.topicName || "未分类")}</span>
      ${q.material ? '<span class="chip type">材料题</span>' : ''}
      <span class="q-no">第 ${q.number} 题</span>`;

    const matEl = $("#qMaterial");
    if (q.material) {
      matEl.hidden = false;
      matEl.innerHTML = `<div class="q-material-head">材料</div>${esc(q.material)}`;
    } else {
      matEl.hidden = true;
      matEl.innerHTML = "";
    }
    $("#qStem").textContent = q.stem;

    const p = progress[q.id];
    const wasDone = !!p;
    state.revealed = wasDone;
    state.selected = new Set((p && Array.isArray(p.c) ? p.c : []));

    const objective = q.type === "single" || q.type === "multiple";
    const options = $("#qOptions");
    const subjective = $("#qSubjective");
    const actions = $("#qActions");
    const result = $("#qResult");
    const explain = $("#qExplain");

    if (objective) {
      subjective.hidden = true;
      options.innerHTML = ["A", "B", "C", "D"].map((k) => `
        <button class="option" data-key="${k}" aria-pressed="false">
          <span class="option-key">${k}</span>
          <span class="option-text">${esc(q.options?.[k] || "（选项缺失）")}</span>
          <span class="mark" aria-hidden="true"></span>
        </button>`).join("");
      options.hidden = false;
    } else {
      options.innerHTML = "";
      options.hidden = true;
      subjective.hidden = false;
      const ta = $("#subjInput");
      ta.value = drafts[q.id] || "";
      updateWordCount();
      ta.addEventListener("input", () => {
        updateWordCount();
        clearTimeout(ta._t);
        ta._t = setTimeout(() => {
          drafts[q.id] = ta.value;
          writeJSON(LS.draft, drafts);
        }, 250);
      });
    }

    if (objective) {
      actions.innerHTML = `
        <button class="btn primary" id="submitBtn">提交答案</button>
        <button class="btn ghost" id="showBtn2">直接看答案</button>
        <span class="hint">${q.type === "multiple" ? "多选题：选全对才得分" : "单选题"} · 快捷键 A–D</span>`;
    } else {
      actions.innerHTML = `
        <button class="btn primary" id="revealBtn">查看参考答案</button>
        <span class="hint">先写下要点，再对照参考答案自评</span>`;
    }

    // 已做过的题目：还原展示
    if (wasDone) {
      if (objective) {
        revealObjective(q, p.c || [], p.r === "right");
      } else {
        revealSubjective(q, true);
      }
    }

    if (objective) {
      const submitBtn = $("#submitBtn");
      const showBtn2 = $("#showBtn2");
      if (submitBtn) submitBtn.addEventListener("click", () => submitObjective(q));
      if (showBtn2) showBtn2.addEventListener("click", () => showObjectiveAnswer(q));
      options.addEventListener("click", (e) => {
        const btn = e.target.closest(".option");
        if (!btn || state.revealed) return;
        const key = btn.dataset.key;
        if (q.type === "single") {
          state.selected = new Set([key]);
        } else {
          if (state.selected.has(key)) state.selected.delete(key);
          else state.selected.add(key);
        }
        paintSelection();
      });
    } else {
      const revealBtn = $("#revealBtn");
      if (revealBtn) revealBtn.addEventListener("click", () => revealSubjective(q, false));
    }

    // 收藏
    const fav = $("#favBtn");
    fav.setAttribute("aria-pressed", String(favorites.has(q.id)));
    fav.innerHTML = `<span class="star">${favorites.has(q.id) ? "★" : "☆"}</span> 收藏`;
    fav.addEventListener("click", () => {
      if (favorites.has(q.id)) {
        favorites.delete(q.id);
        toast("已取消收藏");
      } else {
        favorites.add(q.id);
        toast("已加入收藏");
      }
      writeJSON(LS.fav, [...favorites]);
      fav.setAttribute("aria-pressed", String(favorites.has(q.id)));
      fav.innerHTML = `<span class="star">${favorites.has(q.id) ? "★" : "☆"}</span> 收藏`;
      updateHeaderStats();
      renderSidebar();
    });

    $("#showAnswerBtn").hidden = true;
    $("#showAnswerBtn").addEventListener("click", () => {
      if (objective) showObjectiveAnswer(q);
      else revealSubjective(q, false);
    });

    const reset = $("#resetBtn");
    reset.hidden = !wasDone;
    reset.addEventListener("click", () => {
      delete progress[q.id];
      writeJSON(LS.progress, progress);
      state.selected = new Set();
      state.revealed = false;
      renderQuestionCard(q);
      updateHeaderStats();
      renderSidebar();
      toast("已重置本题");
    });

    if (wasDone) reset.hidden = false;
    paintSelection();
    if (wasDone) markOptions(q, state.selected, statusOf(q) === "right");
  }

  function paintSelection() {
    $$("#qOptions .option").forEach((btn) => {
      const on = state.selected.has(btn.dataset.key);
      btn.classList.toggle("is-selected", on);
      btn.setAttribute("aria-pressed", String(on));
    });
    const submit = $("#submitBtn");
    if (submit) submit.disabled = state.selected.size === 0;
  }

  function answerSet(q) {
    return new Set(String(q.answer || "").toUpperCase().replace(/[^A-D]/g, "").split(""));
  }

  function submitObjective(q) {
    if (state.revealed) return;
    if (!state.selected.size) { toast("请先选择答案"); return; }
    const right = answerSet(q);
    const hasAnswer = right.size > 0;
    const correct = hasAnswer && [...state.selected].sort().join("") === [...right].sort().join("");
    recordProgress(q, hasAnswer ? (correct ? "right" : "wrong") : "seen", [...state.selected]);
    revealObjective(q, [...state.selected], correct);
    updateHeaderStats();
    renderSidebar();
  }

  function showObjectiveAnswer(q) {
    const right = answerSet(q);
    const chosen = [...state.selected];
    const correct = right.size > 0 && chosen.length > 0 && [...chosen].sort().join("") === [...right].sort().join("");
    if (!progress[q.id]) recordProgress(q, right.size ? (correct ? "right" : "seen") : "seen", chosen);
    revealObjective(q, chosen, correct);
    updateHeaderStats();
    renderSidebar();
  }

  function revealObjective(q, chosen, correct) {
    state.revealed = true;
    $$("#qOptions .option").forEach((btn) => {
      btn.disabled = true;
      btn.classList.remove("is-selected");
    });
    markOptions(q, new Set(chosen), correct);
    const actions = $("#qActions");
    if (actions) actions.innerHTML = `<span class="hint">已作答，可用下方“重做本题”重练。</span>`;
    $("#showAnswerBtn").hidden = true;
    const right = [...answerSet(q)];
    const result = $("#qResult");
    result.hidden = false;
    if (!right.length) {
      result.className = "q-result";
      result.innerHTML = `<span class="result-title">本题暂无标准答案</span><span class="result-answer">原卷答案未收录，可先参考解析。</span>`;
    } else if (correct) {
      result.className = "q-result right";
      result.innerHTML = `<span class="result-title">回答正确</span>
        <span class="result-answer">正确答案 ${right.map((k) => `<span class="ans-chip">${k}</span>`).join("")}</span>`;
    } else {
      result.className = "q-result wrong";
      result.innerHTML = `<span class="result-title">${chosen.length ? "回答错误" : "已显示答案"}</span>
        <span class="result-answer">正确答案 ${right.map((k) => `<span class="ans-chip">${k}</span>`).join("")}</span>`;
    }
    renderExplanation(q);
    const reset = $("#resetBtn");
    if (reset) reset.hidden = false;
    const fav = $("#favBtn");
    if (fav) fav.hidden = false;
  }

  function markOptions(q, chosen, correct) {
    const right = answerSet(q);
    $$("#qOptions .option").forEach((btn) => {
      const k = btn.dataset.key;
      btn.classList.remove("is-correct", "is-wrong", "is-selected");
      if (right.has(k)) {
        btn.classList.add("is-correct");
        $(".mark", btn).textContent = "✓";
      } else if (chosen.has(k) && right.size) {
        btn.classList.add("is-wrong");
        $(".mark", btn).textContent = "✕";
      } else if (chosen.has(k)) {
        btn.classList.add("is-selected");
      }
      btn.setAttribute("aria-pressed", String(chosen.has(k)));
    });
    if (!right.size) {
      $$("#qOptions .option").forEach((btn) => {
        if (chosen.has(btn.dataset.key)) btn.classList.add("is-selected");
      });
    }
  }

  function renderExplanation(q, extraHtml = "") {
    const explain = $("#qExplain");
    if (!q.explanation && !extraHtml) {
      explain.hidden = true;
      return;
    }
    explain.hidden = false;
    const parts = String(q.explanation || "").split(/\n+/).map((s) => s.trim()).filter(Boolean);
    explain.innerHTML = `<h4>解析</h4>${parts.map((p) => `<p>${esc(p)}</p>`).join("")}${extraHtml}`;
  }

  function revealSubjective(q, silent) {
    state.revealed = true;
    const actions = $("#qActions");
    if (actions) actions.innerHTML = "";
    const result = $("#qResult");
    result.hidden = true;
    const answerText = (q.answer && q.answer.length > 2 && !/^[A-D]+$/.test(q.answer)) ? q.answer : "";
    const explain = $("#qExplain");
    const parts = String(q.explanation || "").split(/\n+/).map((s) => s.trim()).filter(Boolean);
    if (!answerText && !parts.length) {
      explain.hidden = false;
      explain.innerHTML = `<h4>参考答案</h4><p>原卷未收录本题参考答案，可结合教材相应考点整理。</p>`;
    } else {
      explain.hidden = false;
      explain.innerHTML = `<h4>参考答案与解析</h4>
        ${answerText ? `<p><span class="ref-label">答案：</span>${esc(answerText)}</p>` : ""}
        ${parts.map((p) => `<p>${esc(p)}</p>`).join("")}`;
    }
    const rating = `
      <div class="rate-row" id="rateRow">
        <span class="hint">对照后自评：</span>
        <button class="rate-btn ${statusOf(q) === "mastered" ? "is-active" : ""}" data-rate="mastered">掌握</button>
        <button class="rate-btn ${statusOf(q) === "fuzzy" ? "is-active" : ""}" data-rate="fuzzy">模糊</button>
        <button class="rate-btn ${statusOf(q) === "unknown" ? "is-active" : ""}" data-rate="unknown">不会</button>
      </div>`;
    if (actions) {
      actions.innerHTML = rating;
      actions.hidden = false;
    } else {
      explain.insertAdjacentHTML("beforeend", rating);
    }
    $("#rateRow").addEventListener("click", (e) => {
      const btn = e.target.closest(".rate-btn");
      if (!btn) return;
      recordProgress(q, btn.dataset.rate, []);
      $$("#rateRow .rate-btn").forEach((b) => b.classList.toggle("is-active", b === btn));
      updateHeaderStats();
      renderSidebar();
      toast({ mastered: "已标记为掌握", fuzzy: "已标记为模糊", unknown: "已标记为不会" }[btn.dataset.rate]);
    });
    $("#showAnswerBtn").hidden = true;
    const reset = $("#resetBtn");
    if (reset) reset.hidden = false;
    const fav = $("#favBtn");
    if (fav) fav.hidden = false;
    if (!silent) toast("参考答案已展开");
  }

  function recordProgress(q, result, choice) {
    progress[q.id] = { r: result, c: choice, ts: Date.now() };
    writeJSON(LS.progress, progress);
  }

  function updateWordCount() {
    const ta = $("#subjInput");
    const el = $("#subjWords");
    if (ta && el) el.textContent = `${ta.value.replace(/\s/g, "").length} 字`;
  }

  function go(delta) {
    if (!currentList.length) return;
    const next = state.index + delta;
    if (next < 0 || next >= currentList.length) return;
    state.index = next;
    renderPractice();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function jumpTo(i) {
    if (i < 0 || i >= currentList.length) return;
    state.index = i;
    closeJump();
    renderPractice();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function openJump() {
    if (!currentList.length) return;
    const grid = $("#jumpGrid");
    grid.innerHTML = currentList.map((q, i) => {
      const st = statusOf(q);
      const cls = st === "wrong" || st === "unknown" || st === "fuzzy" ? "wrong" : isDone(q) ? "done" : "";
      return `<button class="${cls} ${i === state.index ? "current" : ""}" data-i="${i}" title="${q.year} ${q.degree} 第${q.number}题 · ${esc(q.topicName || "")}">${i + 1}</button>`;
    }).join("");
    $("#jumpModal").hidden = false;
    document.body.style.overflow = "hidden";
    const cur = $(".jump-grid .current");
    if (cur) cur.scrollIntoView({ block: "center" });
  }

  function closeJump() {
    $("#jumpModal").hidden = true;
    document.body.style.overflow = "";
  }

  function shuffleNow() {
    state.sort = "random";
    state.seed = Math.random();
    state.index = 0;
    $("#sortSelect").value = "random";
    renderView();
    toast("已打乱顺序");
  }

  function bindCrumbClicks() {
    $$("#crumbs [data-clear]").forEach((b) => {
      b.addEventListener("click", () => {
        const which = b.dataset.clear;
        if (which === "all") {
          state.filter = defaultFilter();
          state.practiceStarted = false;
          state.limit = 0;
          state.index = 0;
        } else if (which === "subject") {
          state.filter.subject = "";
          state.filter.group = "";
          state.filter.topic = "";
          state.index = 0;
        } else if (which === "group") {
          state.filter.group = "";
          state.filter.topic = "";
          state.index = 0;
        }
        refreshAll();
      });
    });
  }

  function bindStatic() {
    $("#themeBtn").addEventListener("click", toggleTheme);
    $("#brandHome").addEventListener("click", (e) => {
      e.preventDefault();
      state.filter = defaultFilter();
      state.practiceStarted = false;
      state.limit = 0;
      state.index = 0;
      refreshAll();
    });
    $("#menuBtn").addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
    $("#overlay").addEventListener("click", closeSidebar);

    $$(".mode-btn").forEach((b) => b.addEventListener("click", () => {
      if (state.mode === b.dataset.mode) return;
      state.mode = b.dataset.mode;
      state.index = 0;
      state.limit = 0;
      state.practiceStarted = state.practiceStarted;
      refreshAll();
    }));

    $$("#groupBySeg .seg-btn").forEach((b) => b.addEventListener("click", () => {
      state.groupBy = b.dataset.groupby;
      refreshAll();
    }));

    $("#tree").addEventListener("click", (e) => {
      const sub = e.target.closest("[data-subject]");
      const topic = e.target.closest("[data-topic]");
      const uncat = e.target.closest("[data-uncat]");
      if (uncat) {
        state.filter = { ...defaultFilter(), subject: uncat.dataset.uncat, uncat: uncat.dataset.uncat };
        state.practiceStarted = true;
        state.limit = 0;
        state.index = 0;
        refreshAll();
        if (window.innerWidth < 900) closeSidebar();
        return;
      }
      if (topic) {
        const node = nodeMap.get(topic.dataset.topic);
        state.filter = { ...defaultFilter(), subject: node ? node.subject : state.filter.subject, topic: topic.dataset.topic };
        state.practiceStarted = true;
        state.limit = 0;
        state.index = 0;
        refreshAll();
        if (window.innerWidth < 900) closeSidebar();
        return;
      }
      if (sub) {
        state.filter = { ...defaultFilter(), subject: sub.dataset.subject };
        state.practiceStarted = true;
        state.limit = 0;
        state.index = 0;
        refreshAll();
        if (window.innerWidth < 900) closeSidebar();
      }
    });

    $("#clearAllBtn").addEventListener("click", () => {
      state.filter = defaultFilter();
      state.practiceStarted = false;
      state.limit = 0;
      state.index = 0;
      refreshAll();
      toast("已清除筛选");
    });

    $("#yearSelect").addEventListener("change", (e) => {
      state.filter.year = e.target.value;
      state.limit = 0;
      state.index = 0;
      refreshAll();
    });

    $("#degreeRow").addEventListener("click", (e) => {
      const b = e.target.closest(".pill"); if (!b) return;
      state.filter.degree = b.dataset.degree;
      state.limit = 0;
      state.index = 0;
      refreshAll();
    });
    $("#paperRow").addEventListener("click", (e) => {
      const b = e.target.closest(".pill"); if (!b) return;
      state.filter.paper = b.dataset.paper;
      state.limit = 0;
      state.index = 0;
      refreshAll();
    });
    $("#statusRow").addEventListener("click", (e) => {
      const b = e.target.closest(".pill"); if (!b) return;
      state.filter.status = b.dataset.status;
      state.practiceStarted = true;
      state.limit = 0;
      state.index = 0;
      refreshAll();
    });

    $("#sortSelect").addEventListener("change", (e) => {
      state.sort = e.target.value;
      if (state.sort === "random") state.seed = Math.random();
      state.limit = 0;
      state.index = 0;
      renderView();
      saveUI();
    });

    $("#searchInput").addEventListener("input", (e) => {
      clearTimeout(searchTimer);
      const val = e.target.value.trim();
      searchTimer = setTimeout(() => {
        state.filter.q = val;
        state.practiceStarted = true;
        state.limit = 0;
        state.index = 0;
        renderView();
        saveUI();
      }, 200);
    });

    $("#shuffleBtn").addEventListener("click", shuffleNow);

    $("#jumpModal").addEventListener("click", (e) => {
      if (e.target.closest("[data-close]")) { closeJump(); return; }
      const b = e.target.closest("[data-i]");
      if (b) jumpTo(Number(b.dataset.i));
    });

    document.addEventListener("keydown", (e) => {
      const tag = (e.target.tagName || "").toLowerCase();
      const typing = tag === "input" || tag === "textarea" || tag === "select";
      if (e.key === "Escape") {
        if (!$("#jumpModal").hidden) closeJump();
        closeSidebar();
        return;
      }
      if (typing) return;
      if (!currentQ || !currentList.length) return;
      const k = e.key.toUpperCase();
      if (["A", "B", "C", "D"].includes(k) && (currentQ.type === "single" || currentQ.type === "multiple") && !state.revealed) {
        e.preventDefault();
        if (currentQ.type === "single") state.selected = new Set([k]);
        else if (state.selected.has(k)) state.selected.delete(k);
        else state.selected.add(k);
        paintSelection();
        return;
      }
      if (k === "ENTER") {
        e.preventDefault();
        if (currentQ.type === "single" || currentQ.type === "multiple") {
          if (!state.revealed) submitObjective(currentQ);
          else go(1);
        } else if (!state.revealed) revealSubjective(currentQ, false);
        else go(1);
        return;
      }
      if (k === "ARROWRIGHT") { e.preventDefault(); go(1); }
      if (k === "ARROWLEFT") { e.preventDefault(); go(-1); }
      if (k === "S") { e.preventDefault(); if (currentQ.type === "single" || currentQ.type === "multiple") showObjectiveAnswer(currentQ); else revealSubjective(currentQ, false); }
      if (k === "F") { const fav = $("#favBtn"); if (fav) fav.click(); }
    });
  }

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
  }

  function syncControls() {
    const years = DATA.meta.years || [];
    const sel = $("#yearSelect");
    sel.innerHTML = `<option value="">全部年份</option>` + years.slice().reverse().map((y) => `<option value="${y}">${y} 年</option>`).join("");
    sel.value = state.filter.year || "";
    $("#sortSelect").value = state.sort;
    $("#searchInput").value = state.filter.q || "";
  }

  boot();
})();
