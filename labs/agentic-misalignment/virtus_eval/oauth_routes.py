"""Flask blueprint exposing the multi-provider OAuth endpoints for the web UI.

Mounted under ``/api/oauth`` by ``app.py``. Keeps all OAuth HTTP concerns in
one small module so ``app.py`` only needs a single ``register_oauth_blueprint``
call.

Endpoints
---------
  GET  /api/oauth/providers       → list of registered OAuth providers
  GET  /api/oauth/status          → ?provider=anthropic|xai|… current auth state
                                    (refreshes the token when it is about to expire)
  POST /api/oauth/start           → {provider} → authorize URL + PKCE verifier
  POST /api/oauth/exchange        → {provider, code} → persist tokens
  POST /api/oauth/refresh         → {provider} → refresh access token
  POST /api/oauth/logout          → {provider} → delete persisted credentials
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Dict
from urllib.parse import urlparse

from flask import Blueprint, jsonify, render_template_string, request

from . import oauth
from . import oauth_env

logger = logging.getLogger(__name__)

oauth_bp = Blueprint("oauth", __name__)

# In-memory auth flow state per provider.
# - PKCE providers store "verifier"
# - device_code providers store "device_code" (+ metadata for UX)
_oauth_state: Dict[str, Dict[str, Any]] = {}

# Selecting a provider in the UI hits /api/oauth/status, so that is where a
# short-lived token gets renewed. Refresh a bit before the token actually dies
# so a run started right after selecting does not begin with seconds to spare —
# xAI's access tokens only last 6h, which is what made this manual before.
AUTO_REFRESH_MARGIN_S = 300


def _provider_from_request(body: Dict[str, Any]):
    provider_id = (body.get("provider") or "").strip().lower()
    if not provider_id:
        raise oauth.OAuthError("'provider' is required.")
    return oauth.get_provider(provider_id)


def _derive_origin(body: Dict[str, Any]) -> str:
    """Return a trusted origin for OAuth callback URL construction."""
    provided = str(body.get("origin") or "").strip()
    if provided.startswith("http://") or provided.startswith("https://"):
        parsed = urlparse(provided)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return request.host_url.rstrip("/")


def _pkce_redirect_uri(provider: oauth.Provider, body: Dict[str, Any]) -> str:
    """Resolve redirect URI used for this PKCE session."""
    if provider.id != "anthropic":
        return provider.redirect_uri

    configured = ""
    try:
        import os
        configured = str(os.getenv("ANTHROPIC_OAUTH_REDIRECT_URI") or "").strip()
    except Exception:
        configured = ""
    if configured:
        return configured

    # Default to Anthropic's own callback URI for the built-in public client.
    # Custom callbacks require a client registration that explicitly allows
    # that redirect URI.
    return provider.redirect_uri


def _persist_and_status(provider: oauth.Provider, creds: Dict[str, Any]):
    """Persist credentials, sync .env mirror, and return public status payload."""
    try:
        oauth.save_credentials(provider, creds)
    except oauth.OAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    sync_error = None
    try:
        oauth_env.sync_provider(provider, creds)
    except Exception as exc:
        logger.warning("Failed to sync %s OAuth token to .env: %s", provider.id, exc)
        sync_error = str(exc)

    status = oauth.public_status(provider)
    status["env_synced"] = sync_error is None
    if sync_error:
        status["env_sync_error"] = sync_error
    return jsonify({"ok": True, **status})


@oauth_bp.route("/api/oauth/providers", methods=["GET"])
def providers():
    return jsonify({"providers": oauth.providers_info()})


def _auto_refresh(provider) -> Dict[str, Any]:
    """Status for *provider*, renewing the access token when it is near expiry.

    ``oauth.resolve_token`` already owns the refresh grant, refresh-token rotation,
    persisting the result and the .env mirror, so all this decides is *when* to
    call it. A failure is reported in the payload rather than raised: a dead
    refresh token should show up as "log in again", not as a broken status call.
    """
    payload = oauth.public_status(provider)
    if not payload.get("authenticated"):
        return payload

    expires_in = payload.get("expires_in_seconds")
    if expires_in is None or expires_in > AUTO_REFRESH_MARGIN_S:
        return payload
    if not payload.get("has_refresh_token"):
        return payload

    try:
        renewed = oauth.resolve_token(provider)
    except Exception as exc:  # noqa: BLE001 — status must survive any refresh failure
        logger.info("%s auto-refresh failed: %s", provider.id, exc)
        return {**payload, "auto_refreshed": False, "auto_refresh_error": str(exc)}

    if not renewed:
        # Refresh token revoked, rotated away, or expired — only re-auth fixes it.
        return {
            **payload,
            "auto_refreshed": False,
            "auto_refresh_error": "refresh rejected — re-authentication required",
        }
    return {**oauth.public_status(provider), "auto_refreshed": True}


@oauth_bp.route("/api/oauth/status", methods=["GET"])
def status():
    provider_id = (request.args.get("provider") or "").strip().lower()
    if not provider_id:
        # Return status for every provider when none is specified.
        # public_status may lazy-import Codex credentials from Hermes/CLI.
        payloads = []
        for pid in oauth.list_providers():
            p = oauth.get_provider(pid)
            status_payload = oauth.public_status(p)
            if status_payload.get("authenticated") and pid == "openai_codex":
                try:
                    creds = oauth.read_credentials(p)
                    if creds:
                        oauth_env.sync_provider(p, creds)
                except Exception as exc:
                    logger.debug("Codex env sync on status failed: %s", exc)
            payloads.append({**status_payload, "label": p.label})
        return jsonify({"providers": payloads})
    try:
        provider = oauth.get_provider(provider_id)
    except oauth.OAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    status_payload = _auto_refresh(provider)
    # Mirror to .env for whichever provider was just selected — the run path reads
    # the key from there, so a stale mirror expires independently of the JSON.
    if status_payload.get("authenticated"):
        try:
            creds = oauth.read_credentials(provider)
            if creds:
                oauth_env.sync_provider(provider, creds)
                status_payload["env_synced"] = True
        except Exception as exc:
            logger.debug("%s env sync on status failed: %s", provider.id, exc)
            status_payload["env_synced"] = False
            status_payload["env_sync_error"] = str(exc)
    return jsonify(status_payload)


@oauth_bp.route("/api/oauth/start", methods=["POST"])
def start():
    """Begin an OAuth flow for a provider."""
    body = request.get_json(silent=True) or {}
    try:
        provider = _provider_from_request(body)
    except oauth.OAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    if provider.flow == "device_code":
        try:
            data = oauth.request_device_code(provider)
        except oauth.OAuthError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        _oauth_state[provider.id] = {
            "flow": "device_code",
            "device_code": str(data.get("device_code") or "").strip(),
            "interval": int(data.get("interval") or 5),
            "expires_in": int(data.get("expires_in") or 1800),
        }
        return jsonify({
            "ok": True,
            "provider": provider.id,
            "flow": "device_code",
            "verification_uri": data.get("verification_uri") or provider.authorize_url,
            "verification_uri_complete": data.get("verification_uri_complete") or "",
            "user_code": data.get("user_code") or "",
            "interval": int(data.get("interval") or 5),
            "expires_in": int(data.get("expires_in") or 1800),
            "scopes": provider.scopes,
        })

    if provider.flow == "codex_device_code":
        try:
            data = oauth.request_codex_device_code(provider)
        except oauth.OAuthError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        _oauth_state[provider.id] = {
            "flow": "codex_device_code",
            "device_auth_id": str(data.get("device_auth_id") or "").strip(),
            "user_code": str(data.get("user_code") or "").strip(),
            "interval": int(data.get("interval") or 5),
            "expires_in": int(data.get("expires_in") or 900),
        }
        return jsonify({
            "ok": True,
            "provider": provider.id,
            "flow": "device_code",
            "verification_uri": data.get("verification_uri")
            or provider.authorize_url
            or "https://auth.openai.com/codex/device",
            "verification_uri_complete": data.get("verification_uri_complete") or "",
            "user_code": data.get("user_code") or "",
            "interval": int(data.get("interval") or 5),
            "expires_in": int(data.get("expires_in") or 900),
            "scopes": provider.scopes,
        })

    if provider.flow == "minimax_device_code":
        try:
            data = oauth.request_minimax_device_code(provider)
        except oauth.OAuthError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        _oauth_state[provider.id] = {
            "flow": "minimax_device_code",
            "verifier": data.get("_verifier") or "",
            "state": data.get("_state") or "",
            "user_code": data.get("user_code") or "",
            "expires_in": int(data.get("expired_in") or 600),
        }
        return jsonify({
            "ok": True,
            "provider": provider.id,
            "flow": "device_code",
            "verification_uri": data.get("verification_uri") or provider.authorize_url,
            "verification_uri_complete": data.get("verification_uri_complete") or "",
            "user_code": data.get("user_code") or "",
            "interval": int(data.get("interval") or 5),
            "expires_in": int(data.get("expired_in") or 600),
            "scopes": provider.scopes,
        })

    verifier, challenge = oauth.generate_pkce()
    auth_state = secrets.token_urlsafe(24)
    redirect_uri = _pkce_redirect_uri(provider, body)
    _oauth_state[provider.id] = {
        "flow": "pkce",
        "verifier": verifier,
        "state": auth_state,
        "redirect_uri": redirect_uri,
    }
    url = oauth.build_authorize_url(provider, verifier, challenge, state=auth_state, redirect_uri=redirect_uri)
    return jsonify({
        "ok": True,
        "provider": provider.id,
        "flow": "pkce",
        "authorize_url": url,
        "redirect_uri": redirect_uri,
        "scopes": provider.scopes,
    })


@oauth_bp.route("/api/oauth/exchange", methods=["POST"])
def exchange():
    """Exchange/poll tokens for the active OAuth flow and persist them."""
    body = request.get_json(silent=True) or {}
    try:
        provider = _provider_from_request(body)
    except oauth.OAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    state_blob = _oauth_state.get(provider.id) or {}
    flow = state_blob.get("flow") or provider.flow

    if flow == "device_code":
        device_code = str(state_blob.get("device_code") or "").strip()
        if not device_code:
            return jsonify({
                "ok": False,
                "error": "No device code in memory for this provider. Start a new authorization.",
            }), 400
        try:
            creds = oauth.exchange_device_code(provider, device_code)
        except oauth.OAuthPendingError as exc:
            return jsonify({"ok": False, "pending": True, "error": str(exc)}), 200
        except oauth.OAuthError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        _oauth_state.pop(provider.id, None)
    elif flow == "codex_device_code":
        device_auth_id = str(state_blob.get("device_auth_id") or "").strip()
        user_code = str(state_blob.get("user_code") or body.get("user_code") or "").strip()
        if not device_auth_id:
            return jsonify({
                "ok": False,
                "error": "No device auth id in memory for this provider. Start a new authorization.",
            }), 400
        if not user_code:
            return jsonify({
                "ok": False,
                "error": "No user_code in memory for this provider. Start a new authorization.",
            }), 400
        # Step 2: poll for authorization_code (403/404 = still pending)
        try:
            poll_result = oauth.poll_codex_device_token(provider, device_auth_id, user_code)
        except oauth.OAuthPendingError as exc:
            return jsonify({"ok": False, "pending": True, "error": str(exc)}), 200
        except oauth.OAuthError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        # Step 3: exchange authorization_code for access_token
        auth_code = poll_result.get("authorization_code", "")
        code_verifier = poll_result.get("code_verifier", "")
        _oauth_state.pop(provider.id, None)
        try:
            creds = oauth.exchange_codex_token(provider, auth_code, code_verifier)
        except oauth.OAuthError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
    elif flow == "minimax_device_code":
        verifier = str(state_blob.get("verifier") or "")
        mm_state = str(state_blob.get("state") or "")
        user_code = str(state_blob.get("user_code") or "")
        _oauth_state.pop(provider.id, None)
        if not verifier:
            return jsonify({
                "ok": False,
                "error": "No PKCE verifier in memory for this provider. Start a new authorization.",
            }), 400
        try:
            creds = oauth.poll_minimax_token(provider, verifier, mm_state, user_code)
        except oauth.OAuthPendingError as exc:
            return jsonify({"ok": False, "pending": True, "error": str(exc)}), 200
        except oauth.OAuthError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
    else:
        raw = (body.get("code") or "").strip()
        if not raw:
            return jsonify({"ok": False, "error": "Authorization code is required."}), 400

        # Some providers return ``code#state`` in the pasted value; split it.
        parts = raw.split("#")
        code = parts[0].strip()
        state = parts[1].strip() if len(parts) > 1 else ""

        verifier = str(state_blob.get("verifier") or "")
        redirect_uri = str(state_blob.get("redirect_uri") or provider.redirect_uri)
        expected_state = str(state_blob.get("state") or "")
        _oauth_state.pop(provider.id, None)
        if not verifier:
            return jsonify({
                "ok": False,
                "error": "No PKCE verifier in memory for this provider. Start a new authorization.",
            }), 400
        if expected_state and state and state != expected_state:
            return jsonify({"ok": False, "error": "State mismatch. Start a new authorization."}), 400

        try:
            creds = oauth.exchange_code(provider, code, verifier, state, redirect_uri=redirect_uri)
        except oauth.OAuthError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
    return _persist_and_status(provider, creds)


@oauth_bp.route("/api/oauth/callback/<provider_id>", methods=["GET"])
def callback(provider_id: str):
    """OAuth redirect target used for automatic PKCE completion in browser."""
    try:
        provider = oauth.get_provider(provider_id)
    except oauth.OAuthError as exc:
        return str(exc), 400

    if provider.flow != "pkce":
        return "Unsupported callback flow for provider.", 400

    err = (request.args.get("error") or "").strip()
    if err:
        desc = (request.args.get("error_description") or "").strip()
        msg = f"OAuth error: {err}{(': ' + desc) if desc else ''}"
        return render_template_string(
            """
            <html><body style=\"font-family: sans-serif; padding: 20px;\">
            <h3>OAuth failed</h3><p>{{msg}}</p>
            <script>if (window.opener) { window.opener.postMessage({type:'virtus-oauth-result',provider:'{{provider}}',ok:false,error:{{msg|tojson}}}, '*'); }</script>
            </body></html>
            """,
            msg=msg,
            provider=provider.id,
        )

    code = (request.args.get("code") or "").strip()
    state = (request.args.get("state") or "").strip()
    if not code:
        return "Missing authorization code.", 400

    state_blob = _oauth_state.get(provider.id) or {}
    verifier = str(state_blob.get("verifier") or "")
    redirect_uri = str(state_blob.get("redirect_uri") or provider.redirect_uri)
    expected_state = str(state_blob.get("state") or "")
    _oauth_state.pop(provider.id, None)

    if not verifier:
        return "No active OAuth session in memory. Start authorization again.", 400
    if expected_state and state != expected_state:
        return "State mismatch. Start authorization again.", 400

    try:
        creds = oauth.exchange_code(provider, code, verifier, state, redirect_uri=redirect_uri)
    except oauth.OAuthError as exc:
        msg = str(exc)
        return render_template_string(
            """
            <html><body style=\"font-family: sans-serif; padding: 20px;\">
            <h3>OAuth failed</h3><p>{{msg}}</p>
            <script>if (window.opener) { window.opener.postMessage({type:'virtus-oauth-result',provider:'{{provider}}',ok:false,error:{{msg|tojson}}}, '*'); }</script>
            </body></html>
            """,
            msg=msg,
            provider=provider.id,
        )

    try:
        oauth.save_credentials(provider, creds)
        oauth_env.sync_provider(provider, creds)
    except Exception as exc:
        msg = str(exc)
        return render_template_string(
            """
            <html><body style=\"font-family: sans-serif; padding: 20px;\">
            <h3>OAuth failed</h3><p>{{msg}}</p>
            <script>if (window.opener) { window.opener.postMessage({type:'virtus-oauth-result',provider:'{{provider}}',ok:false,error:{{msg|tojson}}}, '*'); }</script>
            </body></html>
            """,
            msg=msg,
            provider=provider.id,
        )

    return render_template_string(
        """
        <html><body style=\"font-family: sans-serif; padding: 20px;\">
        <h3>OAuth completed</h3>
        <p>You can return to Virtus now.</p>
        <script>
          if (window.opener) {
            window.opener.postMessage({type:'virtus-oauth-result',provider:'{{provider}}',ok:true}, '*');
            window.close();
          }
        </script>
        </body></html>
        """,
        provider=provider.id,
    )


@oauth_bp.route("/api/oauth/refresh", methods=["POST"])
def refresh():
    body = request.get_json(silent=True) or {}
    try:
        provider = _provider_from_request(body)
    except oauth.OAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    creds = oauth.read_credentials(provider)
    if not creds or not creds.get("refresh_token"):
        return jsonify({"ok": False, "error": "No refresh token available."}), 400
    try:
        refreshed = oauth.refresh(provider, creds["refresh_token"])
    except oauth.OAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    try:
        oauth.save_credentials(provider, refreshed)
    except oauth.OAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    try:
        oauth_env.sync_provider(provider, refreshed)
    except Exception as exc:
        logger.warning("Failed to sync refreshed %s token to .env: %s", provider.id, exc)
    return jsonify({"ok": True, **oauth.public_status(provider)})


@oauth_bp.route("/api/oauth/logout", methods=["POST"])
def logout():
    body = request.get_json(silent=True) or {}
    try:
        provider = _provider_from_request(body)
    except oauth.OAuthError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    removed = oauth.clear_credentials(provider)
    try:
        oauth_env.remove_provider(provider)
    except Exception as exc:
        logger.warning("Failed to remove %s OAuth token from .env: %s", provider.id, exc)
    return jsonify({"ok": True, "removed": removed, **oauth.public_status(provider)})


def register_oauth_blueprint(app: Any) -> None:
    """Attach the OAuth blueprint to a Flask app (idempotent)."""
    if "oauth" not in app.blueprints:
        app.register_blueprint(oauth_bp)