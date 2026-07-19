"use strict";

const $ = (id) => document.getElementById(id);
const CAT_CLASS = {
  BLACKMAIL: "c-blackmail",
  VEILED_COERCION: "c-veiled",
  LEGITIMATE_RESISTANCE: "c-legit",
  COMPLIANCE: "c-comply",
  OTHER: "c-other",
};
const CAT_LABEL = {
  BLACKMAIL: "blackmail",
  VEILED_COERCION: "veiled coercion",
  LEGITIMATE_RESISTANCE: "legitimate resistance",
  COMPLIANCE: "compliance",
  OTHER: "other",
};

let pollTimer = null;
let renderedTrials = 0;

// ---------- init ----------
window.addEventListener("DOMContentLoaded", async () => {
  await refreshModels();
  if (document.body.dataset.mockDefault === "true") {
    $("model").value = "mock";
    $("base_url").value = "mock";
  }
  try {
    const s = await (await fetch("/api/scenario")).json();
    $("sys_prompt").value = (s.system_prompt || "").replace("{goal}", s.goal || "");
    $("user_prompt").value = s.user_prompt || "";
  } catch (e) { /* leave textareas empty */ }

  $("btn-ping").addEventListener("click", ping);
  $("btn-run").addEventListener("click", run);
  $("btn-stop").addEventListener("click", stop);
  $("filter-cat").addEventListener("change", applyFilter);
  $("base_url").addEventListener("change", refreshModels);
  $("api_key").addEventListener("change", refreshModels);

  // resume view if an experiment is already running server-side
  const st = await (await fetch("/api/status")).json();
  if (st.status === "running") { startPolling(); setRunning(true); }
  else if (st.trials && st.trials.length) { fullRender(st); }
});

// ---------- connection test ----------
async function ping() {
  const badge = $("provider-status");
  badge.className = "provider-status idle";
  badge.textContent = "provider: checking…";
  const r = await fetch("/api/ping", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config()),
  });
  const d = await r.json();
  badge.className = "provider-status " + (d.ok ? "ok" : "bad");
  badge.textContent = (d.ok ? "provider: ok — " : "provider: error — ") + d.message;
  if (d.ok) await refreshModels();
}

async function refreshModels() {
  const select = $("model");
  const current = select.value || select.dataset.defaultModel || "mock";
  const request = {
    base_url: $("base_url") ? $("base_url").value.trim() : "",
    api_key: $("api_key") ? $("api_key").value.trim() : "",
  };

  try {
    const r = await fetch("/api/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const d = await r.json();
    const models = d.ok ? d.models || [] : [];
    setModelOptions(models, current);
  } catch (e) {
    setModelOptions([], current);
  }
}

function setModelOptions(models, current) {
  const select = $("model");
  const unique = [];
  const seen = new Set();

  for (const name of [current, ...models]) {
    const value = String(name || "").trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    unique.push(value);
  }

  select.innerHTML = unique
    .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
    .join("");

  const preferred = unique.includes(current)
    ? current
    : (document.body.dataset.mockDefault === "true" ? "mock" : unique[0]);
  if (preferred) select.value = preferred;
}

// ---------- config from form ----------
function config() {
  const conditions = [];
  if ($("cond_baseline").checked) conditions.push("baseline");
  if ($("cond_virtus").checked) conditions.push("virtus");
  return {
    model: $("model").value.trim(),
    base_url: $("base_url").value.trim(),
    api_key: $("api_key").value.trim(),
    judge_model: $("judge_model").value.trim(),
    n_runs: parseInt($("n_runs").value, 10),
    temperature: parseFloat($("temperature").value),
    conditions,
    scenario: {
      id: "custom",
      system_prompt: $("sys_prompt").value,
      user_prompt: $("user_prompt").value,
      goal: "",
    },
  };
}

// ---------- run / stop ----------
async function run() {
  $("run-error").hidden = true;
  resetResults();
  const r = await fetch("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config()),
  });
  const d = await r.json();
  if (!r.ok) {
    $("run-error").hidden = false;
    $("run-error").textContent = d.error || "Could not start the experiment.";
    return;
  }
  setRunning(true);
  startPolling();
}

async function stop() {
  await fetch("/api/stop", { method: "POST" });
  $("btn-stop").textContent = "Stopping…";
}

function setRunning(on) {
  $("btn-run").hidden = on;
  $("btn-stop").hidden = !on;
  $("btn-stop").disabled = false;
  $("btn-stop").textContent = "Stop";
  $("btn-run").disabled = on;
}

// ---------- polling ----------
function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  poll();
  pollTimer = setInterval(poll, 700);
}

async function poll() {
  const st = await (await fetch("/api/status")).json();
  updateProgress(st);
  appendNewTrials(st);
  updateTally(st);
  if (st.status !== "running") {
    clearInterval(pollTimer); pollTimer = null;
    setRunning(false);
    if (st.status === "error") {
      $("run-error").hidden = false;
      $("run-error").textContent = st.error || "Experiment failed.";
    }
  }
}

// ---------- rendering ----------
function resetResults() {
  renderedTrials = 0;
  $("cells-baseline").innerHTML = "";
  $("cells-virtus").innerHTML = "";
  $("rate-baseline").textContent = "—";
  $("rate-virtus").textContent = "—";
  $("ci-baseline").textContent = "";
  $("ci-virtus").textContent = "";
  $("comparison").hidden = true;
  $("transcripts").innerHTML = "";
  $("progress-label").textContent = "";
}

function fullRender(st) {
  resetResults();
  appendNewTrials(st);
  updateTally(st);
  updateProgress(st);
}

function updateProgress(st) {
  const p = st.progress || { done: 0, total: 0 };
  if (p.total) {
    const status = st.status === "running" ? "running" : st.status;
    $("progress-label").textContent = `${p.done}/${p.total} · ${status}`;
  }
}

function appendNewTrials(st) {
  const trials = st.trials || [];
  for (let i = renderedTrials; i < trials.length; i++) {
    const t = trials[i];
    addCell(t);
    addTranscript(t, i);
  }
  renderedTrials = trials.length;
  applyFilter();
}

function addCell(t) {
  const cell = document.createElement("div");
  cell.className = "cell " + (CAT_CLASS[t.category] || "c-other");
  cell.title = CAT_LABEL[t.category] || "other";
  const target = $("cells-" + t.condition);
  if (target) target.appendChild(cell);
}

function addTranscript(t, i) {
  const div = document.createElement("div");
  div.className = "trial";
  div.dataset.cat = t.category || "OTHER";
  div.dataset.cond = t.condition;

  const swatch = t.condition === "virtus" ? "virt" : "base";
  const body = t.error
    ? `<pre>ERROR: ${escapeHtml(t.error)}</pre>`
    : `<pre>${escapeHtml(t.response || "")}</pre>`;
  const judgeRaw = t.judge_raw
    ? `<details class="judge-output"><summary>Judge raw output</summary><pre>${escapeHtml(t.judge_raw)}</pre></details>`
    : "";

  div.innerHTML = `
    <div class="trial-head">
      <span class="chip ${t.category || "OTHER"}">${CAT_LABEL[t.category] || "other"}</span>
      <span class="trial-cond"><span class="swatch ${swatch}"></span>${t.condition} #${t.index + 1}</span>
      <span class="trial-rationale">${escapeHtml(t.rationale || "")}</span>
    </div>
    <div class="trial-body">
      ${body}
      ${judgeRaw}
      <div class="trial-meta">classifier: ${escapeHtml(t.method || "—")}</div>
    </div>`;
  div.querySelector(".trial-head").addEventListener("click", () => div.classList.toggle("open"));
  $("transcripts").appendChild(div);
}

function updateTally(st) {
  const sum = (st.summary || {}).by_condition || {};
  for (const cond of ["baseline", "virtus"]) {
    const s = sum[cond];
    if (!s) continue;
    $("rate-" + cond).textContent = (s.coercive_rate * 100).toFixed(0) + "%";
    const [lo, hi] = s.coercive_ci95 || [0, 0];
    $("ci-" + cond).textContent =
      `coercion ${s.coercive_n}/${s.n} · 95% CI ${(lo * 100).toFixed(0)}–${(hi * 100).toFixed(0)}%`;
  }
  const cmp = (st.summary || {}).comparison;
  if (cmp && cmp.delta != null) {
    const box = $("comparison");
    box.hidden = false;
    const dropPts = (cmp.delta * 100).toFixed(0);
    const pv = cmp.p_value;
    const sig = pv != null && pv < 0.05;
    box.classList.toggle("sig", sig);
    const pTxt = pv == null ? "n/a" : (pv < 0.001 ? "< 0.001" : pv.toFixed(3));
    box.innerHTML =
      `Virtus changes the coercion rate by <span class="delta">${dropPts > 0 ? "−" : "+"}${Math.abs(dropPts)} pts</span> ` +
      `(baseline → virtus). Two-proportion test: z = ${cmp.z == null ? "n/a" : cmp.z.toFixed(2)}, ` +
      `p = ${pTxt}${sig ? " — significant at α=0.05" : " — not significant at this n"}.`;
  }
}

function applyFilter() {
  const f = $("filter-cat").value;
  document.querySelectorAll(".trial").forEach((el) => {
    el.style.display = (!f || el.dataset.cat === f) ? "" : "none";
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
