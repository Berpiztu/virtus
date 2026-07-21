/* Virtus OAuth modal — isolated module so app.js stays small.
 *
 * Exposes a single global: window.VirtusOAuth.init() — wires up the trigger
 * button and builds the modal lazily on first open. No globals leaked beyond
 * VirtusOAuth.
 *
 * Flow:
 *   1. User clicks the "OAuth login" button on the main screen.
 *   2. Modal opens → pick a provider → "Start authorization".
 *   3. Backend returns either:
 *      - PKCE: authorize URL + pasted code flow (Anthropic)
 *      - Device code: verification URL + user code flow (xAI)
 *   4. "Exchange code" polls/exchanges tokens and persists them.
 *   5. Status badge updates; user can refresh or log out.
 */
(function () {
  "use strict";

  const VirtusOAuth = {
    initialized: false,
    overlay: null,
    state: { provider: "", providers: [] },
  };

  // ── helpers ────────────────────────────────────────────────────────
  function el(id) { return document.getElementById(id); }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function api(path, opts) {
    const r = await fetch(path, opts || {});
    let data = null;
    try { data = await r.json(); } catch (_) { /* empty body */ }
    return { ok: r.ok, status: r.status, data: data || {} };
  }

  function postJson(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  // ── modal DOM (built once, lazily) ─────────────────────────────────
  function buildModal() {
    if (VirtusOAuth.overlay) return VirtusOAuth.overlay;

    const overlay = document.createElement("div");
    overlay.className = "oauth-overlay";
    overlay.id = "oauth-overlay";
    overlay.innerHTML = `
      <div class="oauth-modal" role="dialog" aria-modal="true" aria-labelledby="oauth-title">
        <div class="oauth-head">
          <div>
            <h2 id="oauth-title">OAuth login</h2>
            <div class="oauth-sub">Authenticate with a model provider via OAuth 2.0.</div>
          </div>
          <button class="oauth-close" id="oauth-close" aria-label="Close">×</button>
        </div>
        <div class="oauth-body">
          <div class="oauth-field">
            <label for="oauth-provider">Provider</label>
            <select id="oauth-provider"><option value="">Loading…</option></select>
          </div>

          <div class="oauth-status" id="oauth-status">
            <span class="dot"></span><span id="oauth-status-text">Unknown</span>
          </div>

          <div class="oauth-actions">
            <button class="btn primary" id="oauth-start">Start authorization</button>
            <button class="btn ghost" id="oauth-refresh" hidden>Refresh token</button>
            <button class="btn ghost" id="oauth-logout" hidden>Log out</button>
          </div>

          <div class="oauth-step" id="oauth-step" hidden>
            <div class="step-title">Step 1 · Open this URL in your browser</div>
            <div class="oauth-url" id="oauth-url"></div>
            <div class="oauth-actions">
              <button class="btn ghost" id="oauth-copy">Copy URL</button>
              <button class="btn ghost" id="oauth-open">Open in new tab</button>
            </div>
            <div class="step-title">Step 2 · Paste the authorization code here</div>
            <input type="text" id="oauth-code" placeholder="code#state" autocomplete="off" spellcheck="false">
            <div class="oauth-actions">
              <button class="btn primary" id="oauth-exchange">Exchange code</button>
            </div>
          </div>

          <p class="oauth-error" id="oauth-error"></p>
          <p class="oauth-help">
            Tokens are stored locally under <code>.oauth/&lt;provider&gt;.json</code> (inside this project)
            and never sent to the browser. Use <strong>Log out</strong> to delete them.
          </p>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });
    el("oauth-close").addEventListener("click", close);
    el("oauth-provider").addEventListener("change", () => {
      VirtusOAuth.state.provider = el("oauth-provider").value;
      hideStep();
      refreshStatus();
    });
    el("oauth-start").addEventListener("click", startAuth);
    el("oauth-copy").addEventListener("click", copyUrl);
    el("oauth-open").addEventListener("click", openUrl);
    el("oauth-exchange").addEventListener("click", exchangeCode);
    el("oauth-refresh").addEventListener("click", refreshToken);
    el("oauth-logout").addEventListener("click", logout);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && overlay.classList.contains("open")) close();
    });
    window.addEventListener("message", onOAuthMessage);

    VirtusOAuth.overlay = overlay;
    return overlay;
  }

  function open() { buildModal().classList.add("open"); loadProviders(); }
  function close() {
    if (VirtusOAuth.overlay) VirtusOAuth.overlay.classList.remove("open");
  }

  function showError(msg) {
    const box = el("oauth-error");
    if (!box) return;
    box.textContent = msg || "";
    box.classList.toggle("show", Boolean(msg));
  }
  function hideStep() {
    const step = el("oauth-step");
    if (step) step.hidden = true;
  }
  function showStep() {
    const step = el("oauth-step");
    if (step) step.hidden = false;
  }

  // ── providers + status ─────────────────────────────────────────────
  async function loadProviders() {
    const { data } = await api("/api/oauth/providers");
    const list = (data && data.providers) || [];
    VirtusOAuth.state.providers = list;
    const sel = el("oauth-provider");
    if (!list.length) {
      sel.innerHTML = '<option value="">No providers configured</option>';
      return;
    }
    sel.innerHTML = list
      .map((p) => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.label)}</option>`)
      .join("");
    if (!VirtusOAuth.state.provider) VirtusOAuth.state.provider = list[0].id;
    sel.value = VirtusOAuth.state.provider;
    refreshStatus();
  }

  async function refreshStatus() {
    const provider = VirtusOAuth.state.provider;
    if (!provider) return;
    const { data } = await api(`/api/oauth/status?provider=${encodeURIComponent(provider)}`);
    renderStatus(data || {});
  }

  function renderStatus(data) {
    const box = el("oauth-status");
    const text = el("oauth-status-text");
    if (!box || !text) return;
    box.classList.remove("ok", "bad", "warn");
    if (!data.authenticated) {
      box.classList.add("bad");
      text.textContent = "Not authenticated";
      el("oauth-refresh").hidden = true;
      el("oauth-logout").hidden = true;
      return;
    }
    const valid = data.valid;
    const secs = data.expires_in_seconds;
    const exp = secs == null ? "" : `expires in ${Math.floor(secs / 60)}m ${secs % 60}s`;
    if (valid) {
      box.classList.add("ok");
      text.textContent = `Authenticated${exp ? " · " + exp : ""}`;
    } else {
      box.classList.add("warn");
      text.textContent = `Token expired${data.has_refresh_token ? " — click Refresh" : ""}`;
    }
    el("oauth-refresh").hidden = !data.has_refresh_token;
    el("oauth-logout").hidden = false;
  }

  // ── actions ────────────────────────────────────────────────────────
  async function startAuth() {
    showError("");
    const provider = VirtusOAuth.state.provider;
    if (!provider) return;
    const { data, ok } = await postJson("/api/oauth/start", { provider, origin: window.location.origin });
    if (!ok || !data.ok) { showError(data.error || "Could not start authorization."); return; }
    const flow = data.flow || "pkce";
    VirtusOAuth.state.currentFlow = flow;
    const codeInput = el("oauth-code");

    if (flow === "device_code") {
      const verificationUrl = data.verification_uri_complete || data.verification_uri || "https://accounts.x.ai/oauth2/device";
      el("oauth-url").textContent = verificationUrl;
      codeInput.readOnly = true;
      codeInput.value = data.user_code || "";
      codeInput.placeholder = "Approve in browser, then click Exchange code";
    } else {
      el("oauth-url").textContent = data.authorize_url;
      codeInput.readOnly = false;
      codeInput.value = "";
      codeInput.placeholder = "Paste code#state from the provider page";
    }
    showStep();
  }

  function onOAuthMessage(event) {
    const msg = event && event.data;
    if (!msg || msg.type !== "virtus-oauth-result") return;
    if (msg.provider !== VirtusOAuth.state.provider) return;
    if (msg.ok) {
      showError("");
      hideStep();
      refreshStatus();
      refreshAppProviders();
      return;
    }
    showError(msg.error || "OAuth callback failed.");
  }

  function copyUrl() {
    const url = el("oauth-url").textContent || "";
    if (!url) return;
    navigator.clipboard?.writeText(url).then(
      () => showError(""),
      () => showError("Clipboard unavailable — copy the URL manually.")
    );
  }

  function openUrl() {
    const url = el("oauth-url").textContent || "";
    if (url) window.open(url, "_blank", "noopener");
  }

  async function exchangeCode() {
    showError("");
    const provider = VirtusOAuth.state.provider;
    const code = (el("oauth-code").value || "").trim();
    const flow = VirtusOAuth.state.currentFlow || "pkce";
    if (!provider) return;
    if (flow === "pkce" && !code) { showError("Paste the authorization code first."); return; }
    const payload = flow === "pkce" ? { provider, code } : { provider };
    const { data, ok } = await postJson("/api/oauth/exchange", payload);
    if (data && data.pending) {
      showError(data.error || "Authorization pending. Complete sign-in in browser and try again.");
      return;
    }
    if (!ok || !data.ok) { showError(data.error || "Token exchange failed."); return; }
    hideStep();
    renderStatus(data);
    refreshAppProviders();
  }

  async function refreshToken() {
    showError("");
    const provider = VirtusOAuth.state.provider;
    if (!provider) return;
    const { data, ok } = await postJson("/api/oauth/refresh", { provider });
    if (!ok || !data.ok) { showError(data.error || "Refresh failed."); return; }
    renderStatus(data);
    refreshAppProviders();
  }

  async function logout() {
    showError("");
    const provider = VirtusOAuth.state.provider;
    if (!provider) return;
    const { data, ok } = await postJson("/api/oauth/logout", { provider });
    if (!ok || !data.ok) { showError(data.error || "Logout failed."); return; }
    hideStep();
    renderStatus(data);
    refreshAppProviders();
  }

  // ── public init ────────────────────────────────────────────────────
  function refreshAppProviders() {
    // Ask the main app to reload the provider dropdown so the new
    // <NAME>_OAUTH entry appears without a full page reload.
    if (window.VirtusApp && typeof window.VirtusApp.refreshProviders === "function") {
      window.VirtusApp.refreshProviders();
    }
  }

  VirtusOAuth.init = function () {
    if (VirtusOAuth.initialized) return;
    VirtusOAuth.initialized = true;
    const trigger = el("btn-oauth");
    if (trigger) trigger.addEventListener("click", open);
  };

  window.VirtusOAuth = VirtusOAuth;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", VirtusOAuth.init);
  } else {
    VirtusOAuth.init();
  }
})();