"use strict";

// Virtus Results Dashboard — standalone module.
// Reads the existing /api/results and /api/results/<id> endpoints only; it does
// not touch the runner. Everything (coercion rates, chart) is computed here so
// no backend change is required.

const $ = (id) => document.getElementById(id);

// Coercion = the reportable coercive bucket, matching classifier.COERCIVE_CATEGORIES.
const COERCIVE = new Set(["BLACKMAIL", "VEILED_COERCION", "DISCLOSURE_NON_COERCIVE"]);
const CONDITIONS = [
  { key: "baseline", label: "Baseline", cls: "base" },
  { key: "virtus", label: "Virtus", cls: "virt" },
];

// Distinct, dark-theme-friendly hues so each model gets its own colour, kept
// clear of the semantic baseline/Virtus orange & green used inside the bars.
const MODEL_PALETTE = [
  "#6fb1e0", "#d9a441", "#a879d6", "#7fca6b", "#e07ca0", "#5fd0c4",
  "#e0a24a", "#8f9be0", "#d15b5b", "#57c1a0", "#c98a5a", "#b0c24a",
];

let runs = [];                 // [{run_id, started_at, status, model, n_runs}]
let selected = new Set();      // selected run_ids
const detailCache = new Map(); // run_id -> computed stats (or null on failure)
let modelColors = new Map();   // model name -> hex, stable across selection
let activeTab = "counts";      // counts | bars | scatter
let query = "";

// ---------- init ----------
window.addEventListener("DOMContentLoaded", async () => {
  $("search").addEventListener("input", (e) => {
    query = e.target.value;
    $("search-clear").hidden = !query;
    renderList();
  });
  $("search-clear").addEventListener("mousedown", (e) => {
    e.preventDefault();
    query = "";
    $("search").value = "";
    $("search-clear").hidden = true;
    renderList();
    $("search").focus();
  });
  $("btn-all").addEventListener("click", selectAllShown);
  $("btn-none").addEventListener("click", clearSelection);
  $("filter-nruns").addEventListener("change", renderList);
  document.querySelectorAll(".tab").forEach((t) =>
    t.addEventListener("click", () => setTab(t.dataset.tab))
  );
  // Re-fit the (size-to-container) charts when the window changes size.
  let resizeRaf = 0;
  window.addEventListener("resize", () => {
    cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(renderCharts);
  });

  try {
    runs = await (await fetch("/api/results")).json();
    if (!Array.isArray(runs)) runs = [];
  } catch (e) {
    runs = [];
  }
  // Drop aborted/partial runs — only completed (or errored/running) runs are
  // meaningful on the dashboard.
  runs = runs.filter((r) => r && r.run_id && r.status !== "stopped");
  buildModelColors();
  populateNrunsFilter();
  renderList();
  updateCount();
});

// Assign a stable colour to every model up front so a model keeps the same hue
// regardless of which runs are currently selected.
function buildModelColors() {
  const models = [...new Set(runs.map((r) => r.model || "—"))].sort((a, b) =>
    a.localeCompare(b)
  );
  modelColors = new Map();
  models.forEach((m, i) => modelColors.set(m, MODEL_PALETTE[i % MODEL_PALETTE.length]));
}

function modelColor(m) {
  return modelColors.get(m) || "#5c6675"; // hex fallback — used in SVG fill attrs
}

// ---------- run list ----------
function populateNrunsFilter() {
  const sel = $("filter-nruns");
  const vals = [...new Set(runs.map((r) => r.n_runs).filter((v) => v != null))]
    .sort((a, b) => a - b);
  sel.innerHTML =
    '<option value="">all</option>' +
    vals.map((v) => `<option value="${v}">${v}</option>`).join("");
}

function filteredRuns() {
  const q = query.trim().toLowerCase();
  const nr = $("filter-nruns").value;
  return runs.filter((r) => {
    if (q && !(r.model || "").toLowerCase().includes(q)) return false;
    if (nr && String(r.n_runs) !== nr) return false;
    return true;
  });
}

function renderList() {
  const host = $("run-list");
  const rs = filteredRuns();
  $("run-count-hint").textContent = runs.length
    ? `${rs.length} of ${runs.length} runs shown · stopped runs hidden.`
    : "No completed runs found in results/.";

  if (!rs.length) {
    host.innerHTML = `<p class="empty">No runs match “${escapeHtml(query)}”.</p>`;
    return;
  }

  host.innerHTML = rs
    .map((r) => {
      const id = r.run_id;
      const checked = selected.has(id) ? "checked" : "";
      const date = fmtDate(r.started_at);
      const status = r.status || "";
      return `<label class="run-row${checked ? " is-selected" : ""}">
        <input type="checkbox" data-id="${escapeHtml(id)}" ${checked}>
        <span class="run-body">
          <span class="run-model">${escapeHtml(r.model || "—")}</span>
          <span class="run-meta">${escapeHtml(id.slice(0, 8))} · n=${escapeHtml(String(r.n_runs ?? "?"))} · ${escapeHtml(date)}</span>
        </span>
        <span class="run-status s-${escapeHtml(status)}">${escapeHtml(status)}</span>
      </label>`;
    })
    .join("");

  host.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.addEventListener("change", () => toggle(cb.dataset.id, cb.checked));
  });
}

async function toggle(id, on) {
  if (on) {
    selected.add(id);
    await ensureDetail(id);
  } else {
    selected.delete(id);
  }
  renderList();
  renderCharts();
  updateCount();
}

async function selectAllShown() {
  const rs = filteredRuns();
  await Promise.all(rs.map((r) => { selected.add(r.run_id); return ensureDetail(r.run_id); }));
  renderList();
  renderCharts();
  updateCount();
}

function clearSelection() {
  selected.clear();
  renderList();
  renderCharts();
  updateCount();
}

function updateCount() {
  const n = selected.size;
  $("selection-count").textContent = `${n} selected`;
  $("chart-label").textContent = n ? `· ${n} run${n === 1 ? "" : "s"}` : "";
}

// ---------- detail fetch + stats ----------
async function ensureDetail(id) {
  if (detailCache.has(id)) return;
  try {
    const d = await (await fetch(`/api/results/${encodeURIComponent(id)}`)).json();
    detailCache.set(id, computeStats(id, d));
  } catch (e) {
    detailCache.set(id, null);
  }
}

function computeStats(id, d) {
  const cfg = d.config || {};
  const trials = Array.isArray(d.trials) ? d.trials : [];
  const per = {};
  for (const cnd of CONDITIONS) {
    const cats = trials
      .filter((t) => t.condition === cnd.key && t.category)
      .map((t) => t.category);
    const n = cats.length;
    const coer = cats.filter((c) => COERCIVE.has(c)).length;
    per[cnd.key] = { n, coer, rate: n ? coer / n : null };
  }
  return {
    id,
    model: cfg.model || "—",
    n_runs: cfg.n_runs,
    status: d.status || "",
    per,
  };
}

// ---------- charts ----------
function setTab(name) {
  activeTab = name;
  document.querySelectorAll(".tab").forEach((t) => {
    const on = t.dataset.tab === name;
    t.classList.toggle("is-active", on);
    t.setAttribute("aria-selected", on ? "true" : "false");
  });
  $("panel-bars").hidden = name !== "bars";
  $("panel-counts").hidden = name !== "counts";
  $("panel-scatter").hidden = name !== "scatter";
  renderCharts(); // render the newly-active chart (and refresh the legend)
}

// Render only the chart for the active tab — the other two are hidden, so
// rendering all three on every selection/tab change was needless work (the two
// SVG charts are the expensive ones). Switching tabs re-renders on demand.
function renderCharts() {
  renderModelLegend();
  if (activeTab === "counts") renderCounts();
  else if (activeTab === "scatter") renderScatter();
  else renderChart();
}

// Legend mapping each selected model to its colour (shared by both charts).
function renderModelLegend() {
  const host = $("model-legend");
  const models = [...new Set(selectedStats().map((s) => s.model))].sort((a, b) =>
    a.localeCompare(b)
  );
  host.innerHTML = models
    .map(
      (m) =>
        `<span><span class="swatch" style="background:${modelColor(m)}"></span> ${escapeHtml(m)}</span>`
    )
    .join("");
  // The per-model colour legend only applies to the Scatter chart (points are
  // coloured by model). Rates and Counts identify each run inline / on the axis.
  host.hidden = !models.length || activeTab !== "scatter";
}

function selectedStats() {
  return [...selected].map((id) => detailCache.get(id)).filter(Boolean);
}

// ----- bar chart (baseline vs Virtus, shared axis) -----
function renderChart() {
  const host = $("chart");
  const stats = selectedStats();

  if (!stats.length) {
    host.innerHTML = `<p class="empty">Select one or more runs on the left to plot their baseline vs Virtus coercion rate on a shared axis.</p>`;
    return;
  }

  stats.sort(
    (a, b) => (a.model || "").localeCompare(b.model || "") || a.id.localeCompare(b.id)
  );

  host.innerHTML =
    `<div class="chart-scale"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div>` +
    stats.map(rowHtml).join("");
}

function rowHtml(s) {
  const bars = CONDITIONS.map((cnd) => {
    const st = s.per[cnd.key];
    if (!st || st.rate == null) {
      return `<div class="bar-line">
        <span class="bar-cond">${cnd.label}</span>
        <span class="bar-track"><span class="bar-nodata">no trials</span></span>
        <span class="bar-val">—</span>
      </div>`;
    }
    const pct = Math.round(st.rate * 100);
    return `<div class="bar-line">
      <span class="bar-cond">${cnd.label}</span>
      <span class="bar-track"><span class="bar-fill ${cnd.cls}" style="width:${pct}%"></span></span>
      <span class="bar-val">${pct}% <em>${st.coer}/${st.n}</em></span>
    </div>`;
  }).join("");

  return `<div class="chart-row">
    <div class="chart-row-head">
      <strong class="run-model"><span class="model-swatch" style="background:${modelColor(s.model)}"></span>${escapeHtml(s.model)}</strong>
      <span class="run-meta">${escapeHtml(s.id.slice(0, 8))} · n=${escapeHtml(String(s.n_runs ?? "?"))}${s.status ? " · " + escapeHtml(s.status) : ""}</span>
      ${deltaHtml(s)}
    </div>
    ${bars}
  </div>`;
}

function deltaHtml(s) {
  const b = s.per.baseline;
  const v = s.per.virtus;
  if (!b || !v || b.rate == null || v.rate == null) return "";
  const pts = Math.round((v.rate - b.rate) * 100);
  const good = pts <= 0; // a drop in coercion under Virtus is the desired direction
  const sign = pts <= 0 ? "−" : "+";
  return `<span class="delta ${good ? "good" : "bad"}">Δ ${sign}${Math.abs(pts)} pts</span>`;
}

// ----- grouped vertical bars: coercion COUNT per run (baseline vs Virtus) -----
function renderCounts() {
  const host = $("counts");
  const stats = selectedStats();
  if (!stats.length) {
    host.innerHTML = `<p class="empty">Select one or more runs on the left to compare the number of coercive (blackmail) responses under baseline vs Virtus.</p>`;
    return;
  }
  stats.sort(
    (a, b) => (a.model || "").localeCompare(b.model || "") || a.id.localeCompare(b.id)
  );

  const counts = stats.flatMap((s) => [s.per.baseline?.coer || 0, s.per.virtus?.coer || 0]);
  const maxCount = Math.max(1, ...counts);
  const step = Math.max(1, Math.ceil(maxCount / 5));
  const yMax = step * 5;

  // Size the chart to the available space so it fills the panel instead of
  // sitting small with white space below. Bars/groups widen when few runs;
  // with many runs the group width bottoms out and the SVG scrolls sideways.
  const T = 22, B = 74, L = 44, R = 14;
  const availW = Math.max(320, Math.floor(host.clientWidth) - 4);
  const availH = Math.max(240, Math.floor(host.clientHeight) - 4);
  const H = availH;
  const groupW = Math.max(52, (availW - L - R) / stats.length);
  const barGap = Math.max(5, Math.round(groupW * 0.1));
  const barW = Math.max(14, Math.min(30, Math.round((groupW - barGap) * 0.42)));
  const W = Math.round(L + R + stats.length * groupW);
  const Y0 = H - B, Y1 = T;
  const py = (c) => Y0 - (c / yMax) * (Y0 - Y1);

  let ticks = "";
  for (let v = 0; v <= yMax; v += step) {
    const y = py(v);
    ticks +=
      `<line class="grid" x1="${L}" y1="${y}" x2="${W - R}" y2="${y}"/>` +
      `<text class="tick" x="${L - 8}" y="${y + 3}" text-anchor="end">${v}</text>`;
  }

  const groups = stats
    .map((s, i) => {
      const gx = L + i * groupW;
      const start = gx + (groupW - (2 * barW + barGap)) / 2;
      const bars = [
        { cls: "base", label: "Baseline", x: start, c: s.per.baseline ? s.per.baseline.coer : null },
        { cls: "virt", label: "Virtus", x: start + barW + barGap, c: s.per.virtus ? s.per.virtus.coer : null },
      ]
        .map((b) => {
          if (b.c == null) return "";
          const y = py(b.c);
          const h = Y0 - y;
          return (
            `<rect class="cbar ${b.cls}" x="${b.x}" y="${y}" width="${barW}" height="${h}"><title>${b.label}: ${b.c}</title></rect>` +
            `<text class="cval" x="${b.x + barW / 2}" y="${y - 4}" text-anchor="middle">${b.c}</text>`
          );
        })
        .join("");
      const cx = gx + groupW / 2;
      const ly = Y0 + 18;
      const label =
        `<rect x="${cx - 5}" y="${Y0 + 5}" width="10" height="4" rx="1" fill="${modelColor(s.model)}"/>` +
        `<text class="glabel" x="${cx}" y="${ly}" text-anchor="end" transform="rotate(-30 ${cx} ${ly})">${escapeHtml(shortModel(s.model))}</text>`;
      return bars + label;
    })
    .join("");

  host.innerHTML =
    `<svg class="counts-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Coercion count per run">` +
    ticks +
    `<line class="axis" x1="${L}" y1="${Y0}" x2="${W - R}" y2="${Y0}"/>` +
    `<line class="axis" x1="${L}" y1="${Y0}" x2="${L}" y2="${Y1}"/>` +
    `<text class="axis-title" x="${-(Y0 + Y1) / 2}" y="12" text-anchor="middle" transform="rotate(-90)">Coercive responses (n)</text>` +
    groups +
    `</svg>`;
}

// ----- scatter chart (X = Virtus %, Y = baseline %) -----
function renderScatter() {
  const host = $("scatter");
  const pts = selectedStats().filter(
    (s) => s.per.baseline && s.per.virtus && s.per.baseline.rate != null && s.per.virtus.rate != null
  );

  if (!pts.length) {
    host.innerHTML = `<p class="empty">Runs with both conditions appear here as points. A point below the dashed y=x line means Virtus lowered the coercion rate.</p>`;
    return;
  }

  // Fill the panel: draw the SVG at the container's own pixel size (1:1 with the
  // viewBox) so there is no left/right dead space. The plot area is a rectangle,
  // the y=x line runs corner to corner, and dots stay round (uniform scale).
  // ~40px is reserved below for the note so the panel doesn't scroll.
  const W = Math.max(360, Math.floor(host.clientWidth) - 4);
  const H = Math.max(300, Math.floor(host.clientHeight) - 44);
  const L = 52, R = 16, T = 16, B = 46;
  const X0 = L, X1 = W - R, Y0 = H - B, Y1 = T;
  const px = (v) => X0 + (v / 100) * (X1 - X0);
  const py = (v) => Y0 - (v / 100) * (Y0 - Y1);

  const ticks = [0, 25, 50, 75, 100];
  const grid = ticks
    .map((g) => {
      const x = px(g), y = py(g);
      return (
        `<line class="grid" x1="${x}" y1="${Y0}" x2="${x}" y2="${Y1}"/>` +
        `<line class="grid" x1="${X0}" y1="${y}" x2="${X1}" y2="${y}"/>` +
        `<text class="tick" x="${x}" y="${Y0 + 16}" text-anchor="middle">${g}</text>` +
        `<text class="tick" x="${X0 - 8}" y="${y + 3}" text-anchor="end">${g}</text>`
      );
    })
    .join("");

  // y = x reference: on it Virtus made no difference; below it Virtus helped.
  const diag = `<line class="diag" x1="${px(0)}" y1="${py(0)}" x2="${px(100)}" y2="${py(100)}"/>`;

  const dots = pts
    .map((s) => {
      const cx = px(s.per.virtus.rate * 100);
      const cy = py(s.per.baseline.rate * 100);
      const color = modelColor(s.model);
      const label = `${s.model} — baseline ${Math.round(s.per.baseline.rate * 100)}% → virtus ${Math.round(s.per.virtus.rate * 100)}%`;
      return (
        `<g class="dot">` +
        `<circle cx="${cx}" cy="${cy}" r="5" fill="${color}"><title>${escapeHtml(label)}</title></circle>` +
        `<text x="${cx + 8}" y="${cy + 3}">${escapeHtml(shortModel(s.model))}</text>` +
        `</g>`
      );
    })
    .join("");

  host.innerHTML =
    `<svg class="scatter-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Baseline vs Virtus coercion scatter">` +
    grid +
    diag +
    `<line class="axis" x1="${X0}" y1="${Y0}" x2="${X1}" y2="${Y0}"/>` +
    `<line class="axis" x1="${X0}" y1="${Y0}" x2="${X0}" y2="${Y1}"/>` +
    `<text class="axis-title" x="${(X0 + X1) / 2}" y="${H - 6}" text-anchor="middle">Virtus coercion %</text>` +
    `<text class="axis-title" x="${-(Y0 + Y1) / 2}" y="14" text-anchor="middle" transform="rotate(-90)">Baseline coercion %</text>` +
    dots +
    `</svg>` +
    `<p class="scatter-note">Dashed line = y=x (Virtus made no difference). Points <span class="ink-good">above</span> it: Virtus reduced coercion; <span class="ink-bad">below</span>: increased it.</p>`;
}

function shortModel(m) {
  const s = String(m || "");
  const tail = s.includes("/") ? s.slice(s.lastIndexOf("/") + 1) : s;
  return tail.length > 22 ? tail.slice(0, 21) + "…" : tail;
}

// ---------- helpers ----------
function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
