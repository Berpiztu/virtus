"""Multi-provider OAuth helper for the Virtus agentic-misalignment web app.

Self-contained: does NOT depend on Hermes' ``hermes_constants`` or the legacy
``providers/anthropic_adapter.py`` (which was copied from NousResearch/hermes-agent).
That adapter only handles Anthropic; this module is provider-agnostic so it can
also serve xAI and any other provider that exposes OAuth (PKCE or device-code).

Design
------
A ``Provider`` dataclass describes one provider's OAuth endpoints and client
configuration. Providers are registered in ``PROVIDERS``. Each provider stores
its credentials in its own JSON file under ``<project>/.oauth/<provider>.json``
so tokens never cross providers and remain scoped to this repository.

Public API
----------
- ``list_providers()`` → list of registered provider ids
- ``get_provider(provider_id)`` → Provider
- ``providers_info()`` → serializable list for the UI
- ``generate_pkce()`` → (verifier, challenge)
- ``build_authorize_url(provider, verifier, challenge, state)`` → URL
- ``exchange_code(provider, code, verifier, state)`` → creds dict
- ``refresh(provider, refresh_token)`` → creds dict
- ``save_credentials(provider, creds)`` / ``read_credentials(provider)``
- ``clear_credentials(provider)`` / ``is_valid(creds)``
- ``resolve_token(provider)`` → usable access token (refreshing if needed)
- ``public_status(provider)`` → safe serializable snapshot
- ``OAuthError``

Adding a new provider only requires appending a ``Provider(...)`` entry to the
``PROVIDERS`` registry below — no other code changes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Provider registry ───────────────────────────────────────────────────
@dataclass(frozen=True)
class Provider:
    """OAuth 2.0 configuration for one provider.

    Fields
    ------
    id:
        Short identifier used in URLs, filenames and the UI (``"anthropic"``,
        ``"xai"``).
    label:
        Human-readable name shown in the modal.
    client_id:
        OAuth client_id. For public PKCE clients this is a fixed public value.
    authorize_url:
        Authorization endpoint the user's browser is sent to.
    token_url:
        Token endpoint used for both ``authorization_code`` and
        ``refresh_token`` grants.
    redirect_uri:
        Redirect URI registered with the provider. For CLI/web flows this is
        typically the provider's own ``code/callback`` page that displays the
        code for the user to paste back.
    scopes:
        Space-delimited scope string sent in the authorize request.
    api_base_url:
        Default OpenAI-compatible base URL for this provider, used when
        writing the OAuth token into the app's ``.env`` as a ``<NAME>_AUTH``
        provider so the rest of the app can talk to it without special-casing.
    flow:
        OAuth flow type: ``"pkce"`` or ``"device_code"``.
    use_pkce:
        Whether to send ``code_challenge`` / ``code_challenge_method``.
    code_challenge_method:
        Usually ``"S256"``.
    token_exchange_content_type:
        ``"application/json"`` (Anthropic) or
        ``"application/x-www-form-urlencoded"`` (xAI / RFC 6749 default).
    user_agent:
        User-Agent header sent to the token endpoint.
    extra_authorize_params:
        Extra query params merged into the authorize URL (e.g. ``code=true``
        for Anthropic, which asks the provider to display the code instead of
        redirecting a localhost server we'd have to run).
    """

    id: str
    label: str
    client_id: str
    authorize_url: str
    token_url: str
    redirect_uri: str
    scopes: str
    api_base_url: str = ""
    flow: str = "pkce"
    use_pkce: bool = True
    code_challenge_method: str = "S256"
    token_exchange_content_type: str = "application/x-www-form-urlencoded"
    user_agent: str = "virtus-cli/1.0 (external, cli)"
    extra_authorize_params: Dict[str, str] = field(default_factory=dict)


# Anthropic — same PKCE flow Claude Code / OpenCode / Hermes use.
# The ``code=true`` param makes Anthropic render the authorization code on
# console.anthropic.com so the user can paste it back without a local
# redirect server.
_ANTHROPIC = Provider(
    id="anthropic",
    label="Anthropic (Claude Pro/Max)",
    client_id=os.getenv("ANTHROPIC_OAUTH_CLIENT_ID", "9d1c250a-e61b-44d9-88ed-5944d1962f5e").strip(),
    authorize_url="https://claude.ai/oauth/authorize",
    token_url="https://console.anthropic.com/v1/oauth/token",
    redirect_uri=os.getenv("ANTHROPIC_OAUTH_REDIRECT_URI", "https://console.anthropic.com/oauth/code/callback").strip(),
    scopes=os.getenv("ANTHROPIC_OAUTH_SCOPES", "org:create_api_key user:profile user:inference").strip(),
    api_base_url="https://api.anthropic.com/v1",
    token_exchange_content_type="application/json",
    extra_authorize_params={"code": "true"},
)

# xAI — OAuth 2.0 device-code flow (same approach Hermes uses for xai-oauth).
# Keeps API-key and OAuth paths side-by-side for xAI.
_XAI = Provider(
    id="xai",
    label="xAI (Grok)",
    client_id=os.getenv("XAI_OAUTH_CLIENT_ID", "b1a00492-073a-47ea-816f-4c329264a828").strip(),
    authorize_url="https://accounts.x.ai/oauth2/device",
    token_url="https://auth.x.ai/oauth2/token",
    redirect_uri="",
    scopes=os.getenv("XAI_OAUTH_SCOPES", "openid profile email offline_access grok-cli:access api:access").strip(),
    api_base_url="https://api.x.ai/v1",
    flow="device_code",
    token_exchange_content_type="application/x-www-form-urlencoded",
)

# Registry — append new providers here.
PROVIDERS: Dict[str, Provider] = {
    _ANTHROPIC.id: _ANTHROPIC,
    _XAI.id: _XAI,
}


def _provider_enabled(provider: Provider) -> bool:
    """Return True when provider has the minimum config required for OAuth."""
    if provider.id == "xai":
        return bool(provider.client_id)
    return True


def list_providers() -> List[str]:
    """Return registered provider ids in a stable order."""
    return [pid for pid, p in PROVIDERS.items() if _provider_enabled(p)]


def get_provider(provider_id: str) -> Provider:
    """Look up a provider by id. Raises ``OAuthError`` if unknown."""
    key = (provider_id or "").strip().lower()
    provider = PROVIDERS.get(key)
    if provider is None:
        raise OAuthError(f"Unknown OAuth provider: {provider_id!r}")
    if not _provider_enabled(provider):
        if key == "xai":
            raise OAuthError(
                "xAI OAuth is not configured. Set XAI_OAUTH_CLIENT_ID in .env "
                "then restart the server."
            )
        raise OAuthError(f"OAuth provider is not configured: {provider_id!r}")
    return provider


def providers_info() -> List[Dict[str, Any]]:
    """Return a serializable list of providers for the UI."""
    return [
        {"id": p.id, "label": p.label, "scopes": p.scopes, "flow": p.flow}
        for p in PROVIDERS.values()
        if _provider_enabled(p)
    ]


# ── Credential storage ──────────────────────────────────────────────────
# Store OAuth credentials inside the current project to keep auth material
# repository-scoped and avoid leaking state across unrelated workspaces.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VIRTUS_OAUTH_HOME = _PROJECT_ROOT / ".oauth"

# Legacy location used by previous iterations. We keep a one-way fallback so
# existing users remain authenticated after upgrading, then migrate on write.
_LEGACY_VIRTUS_OAUTH_HOME = Path.home() / ".virtus" / "oauth"


def _credentials_file(provider: Provider) -> Path:
    return _VIRTUS_OAUTH_HOME / f"{provider.id}.json"


def _legacy_credentials_file(provider: Provider) -> Path:
    return _LEGACY_VIRTUS_OAUTH_HOME / f"{provider.id}.json"


def read_credentials(provider: Provider) -> Optional[Dict[str, Any]]:
    """Read persisted OAuth credentials for *provider*, or ``None``."""
    paths = (_credentials_file(provider), _legacy_credentials_file(provider))
    for path in paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("access_token"):
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Failed to read %s OAuth credentials from %s: %s", provider.id, path, exc)
    return None


def save_credentials(provider: Provider, creds: Dict[str, Any]) -> None:
    """Persist OAuth credentials for *provider*."""
    path = _credentials_file(provider)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(creds, indent=2), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except OSError as exc:
        raise OAuthError(f"Could not save credentials for {provider.id}: {exc}")

    # Best-effort cleanup of the legacy location to avoid stale status reads.
    legacy = _legacy_credentials_file(provider)
    try:
        if legacy.exists():
            legacy.unlink()
    except OSError:
        pass


def clear_credentials(provider: Provider) -> bool:
    """Delete persisted credentials for *provider*. Returns True if removed."""
    removed = False
    for path in (_credentials_file(provider), _legacy_credentials_file(provider)):
        try:
            if path.exists():
                path.unlink()
                removed = True
        except OSError as exc:
            logger.debug("Failed to remove %s OAuth credentials from %s: %s", provider.id, path, exc)
    return removed


# ── PKCE ────────────────────────────────────────────────────────────────
def generate_pkce() -> Tuple[str, str]:
    """Generate a PKCE code_verifier and its S256 code_challenge."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


# ── Authorize URL ───────────────────────────────────────────────────────
def build_authorize_url(
    provider: Provider,
    verifier: str,
    challenge: str,
    state: Optional[str] = None,
    redirect_uri: Optional[str] = None,
) -> str:
    """Build the provider's authorization URL for the user to open."""
    if provider.flow != "pkce":
        raise OAuthError(f"{provider.id} uses {provider.flow}, not PKCE.")
    params: Dict[str, str] = {
        "client_id": provider.client_id,
        "response_type": "code",
        "redirect_uri": (redirect_uri or provider.redirect_uri),
        "scope": provider.scopes,
        "state": state or verifier,
    }
    if provider.use_pkce:
        params["code_challenge"] = challenge
        params["code_challenge_method"] = provider.code_challenge_method
    params.update(provider.extra_authorize_params)
    return f"{provider.authorize_url}?{urllib.parse.urlencode(params)}"


# ── Token exchange / refresh ────────────────────────────────────────────
def _post_token(
    provider: Provider,
    payload: Dict[str, str],
) -> Dict[str, Any]:
    """POST to the token endpoint and return the parsed JSON response."""
    content_type = provider.token_exchange_content_type
    if content_type == "application/json":
        data = json.dumps(payload).encode()
    else:
        data = urllib.parse.urlencode(payload).encode()

    req = urllib.request.Request(
        provider.token_url,
        data=data,
        headers={
            "Content-Type": content_type,
            "User-Agent": provider.user_agent,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode()
        except Exception:
            pass
        raise OAuthError(f"{provider.id} token request failed ({exc.code}): {body or exc.reason}")
    except Exception as exc:
        raise OAuthError(f"{provider.id} token request failed: {exc}")

    if not result.get("access_token"):
        raise OAuthError(f"{provider.id} token response missing access_token")
    return result


def exchange_code(
    provider: Provider,
    code: str,
    verifier: str,
    state: Optional[str] = None,
    redirect_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """Exchange an authorization code for access/refresh tokens."""
    if provider.flow != "pkce":
        raise OAuthError(f"{provider.id} uses {provider.flow}, not authorization_code.")
    payload = {
        "grant_type": "authorization_code",
        "client_id": provider.client_id,
        "code": code,
        "redirect_uri": (redirect_uri or provider.redirect_uri),
    }
    if state:
        payload["state"] = state
    if provider.use_pkce:
        payload["code_verifier"] = verifier

    result = _post_token(provider, payload)
    expires_in = int(result.get("expires_in", 3600))
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "expires_at_ms": int(time.time() * 1000) + expires_in * 1000,
        "scopes": provider.scopes,
        "token_type": result.get("token_type", "bearer"),
    }


def refresh(provider: Provider, refresh_token: str) -> Dict[str, Any]:
    """Refresh an access token using a refresh token."""
    if not refresh_token:
        raise OAuthError(f"{provider.id}: refresh_token is required")
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": provider.client_id,
    }
    result = _post_token(provider, payload)
    expires_in = int(result.get("expires_in", 3600))
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", refresh_token),
        "expires_at_ms": int(time.time() * 1000) + expires_in * 1000,
        "scopes": provider.scopes,
        "token_type": result.get("token_type", "bearer"),
    }


def request_device_code(provider: Provider) -> Dict[str, Any]:
    """Request a device_code + user_code for OAuth device authorization."""
    if provider.flow != "device_code":
        raise OAuthError(f"{provider.id} does not use device code flow.")

    payload = urllib.parse.urlencode({
        "client_id": provider.client_id,
        "scope": provider.scopes,
    }).encode()
    req = urllib.request.Request(
        "https://auth.x.ai/oauth2/device/code",
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": provider.user_agent,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode()
        except Exception:
            pass
        raise OAuthError(f"{provider.id} device-code request failed ({exc.code}): {body or exc.reason}")
    except Exception as exc:
        raise OAuthError(f"{provider.id} device-code request failed: {exc}")

    device_code = str(result.get("device_code") or "").strip()
    if not device_code:
        raise OAuthError(f"{provider.id} device-code response missing device_code")
    return result


def exchange_device_code(provider: Provider, device_code: str) -> Dict[str, Any]:
    """Poll token endpoint for a device_code (xAI device auth flow)."""
    if provider.flow != "device_code":
        raise OAuthError(f"{provider.id} does not use device code flow.")
    if not device_code:
        raise OAuthError("device_code is required")

    payload = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": device_code,
        "client_id": provider.client_id,
    }).encode()
    req = urllib.request.Request(
        provider.token_url,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": provider.user_agent,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode()
        except Exception:
            pass
        parsed = {}
        if body:
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = {}
        err = str(parsed.get("error") or "").strip().lower()
        if err in {"authorization_pending", "slow_down"}:
            raise OAuthPendingError(
                "Authorization pending. Complete sign-in in your browser, then click Exchange again."
            )
        raise OAuthError(f"{provider.id} token request failed ({exc.code}): {body or exc.reason}")
    except Exception as exc:
        raise OAuthError(f"{provider.id} token request failed: {exc}")

    if not result.get("access_token"):
        raise OAuthError(f"{provider.id} token response missing access_token")
    expires_in = int(result.get("expires_in", 3600))
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "expires_at_ms": int(time.time() * 1000) + expires_in * 1000,
        "scopes": provider.scopes,
        "token_type": result.get("token_type", "bearer"),
    }


# ── Helpers ─────────────────────────────────────────────────────────────
def is_valid(creds: Optional[Dict[str, Any]]) -> bool:
    """Return True if *creds* has a non-expired access token."""
    if not creds or not creds.get("access_token"):
        return False
    expires_at = int(creds.get("expires_at_ms", 0) or 0)
    if not expires_at:
        return True  # no expiry known
    now_ms = int(time.time() * 1000)
    return now_ms < (expires_at - 60_000)  # 60s buffer


def resolve_token(provider: Provider) -> Optional[str]:
    """Return a usable access token for *provider*, refreshing if needed."""
    creds = read_credentials(provider)
    if not creds:
        return None
    if is_valid(creds):
        return creds["access_token"]
    refresh_token = creds.get("refresh_token", "")
    if not refresh_token:
        return None
    try:
        refreshed = refresh(provider, refresh_token)
    except OAuthError as exc:
        logger.debug("%s OAuth refresh failed: %s", provider.id, exc)
        return None
    try:
        save_credentials(provider, refreshed)
    except OAuthError:
        pass
    return refreshed["access_token"]


def public_status(provider: Provider) -> Dict[str, Any]:
    """Return a safe, serializable snapshot of the provider's OAuth state."""
    creds = read_credentials(provider)
    if not creds:
        return {"provider": provider.id, "authenticated": False}
    expires_at = int(creds.get("expires_at_ms", 0) or 0)
    now_ms = int(time.time() * 1000)
    return {
        "provider": provider.id,
        "authenticated": True,
        "expires_at_ms": expires_at,
        "expires_in_seconds": max(0, (expires_at - now_ms) // 1000) if expires_at else None,
        "has_refresh_token": bool(creds.get("refresh_token")),
        "valid": is_valid(creds),
    }


class OAuthError(RuntimeError):
    """Raised for OAuth flow failures (exchange, refresh, storage)."""


class OAuthPendingError(OAuthError):
    """Raised when device-code polling is still waiting for user approval."""