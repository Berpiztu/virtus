"""Sync OAuth tokens into the app's ``.env`` file.

When the user completes an OAuth flow for a provider, we write a
``<NAME>_AUTH`` provider entry into ``.env`` so it shows up in the provider
dropdown automatically and the rest of the app (``model_client``) can use it
like any other provider — no special-casing needed.

Entries written per provider::

    <NAME>_AUTH_BASE_URL=<api_base_url>
    <NAME>_AUTH_API_KEY=<access_token>

On logout we remove those two lines.

The ``.env`` file is rewritten in place, preserving comments, ordering and
any other keys. Only the ``<NAME>_AUTH_*`` keys are touched.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import oauth

logger = logging.getLogger(__name__)

# Path to the app's .env (two levels up from this module).
_DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _provider_env_prefix(provider: oauth.Provider) -> str:
    """Return the ``<NAME>_OAUTH`` env prefix for a provider."""
    # anthropic → ANTHROPIC_OAUTH, xai → XAI_OAUTH
    return f"{provider.id.upper()}_OAUTH"


def _read_dotenv_lines() -> List[str]:
    if not _DOTENV_PATH.exists():
        return []
    try:
        return _DOTENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.debug("Failed to read .env: %s", exc)
        return []


def _write_dotenv_lines(lines: List[str]) -> None:
    text = "\n".join(lines)
    if lines and not text.endswith("\n"):
        text += "\n"
    _DOTENV_PATH.write_text(text, encoding="utf-8")


def _is_auth_key_line(line: str, prefix: str) -> bool:
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return False
    return stripped.startswith(f"{prefix}_BASE_URL=") or stripped.startswith(f"{prefix}_API_KEY=")


def _ensure_providers_list_has(name: str) -> None:
    """Add *name* to the PROVIDERS= line in .env if it isn't already there."""
    lines = _read_dotenv_lines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("PROVIDERS=") or stripped.startswith("#PROVIDERS="):
            continue
        # Parse the current list, preserving inline comments.
        key, _, value = stripped.partition("=")
        # Strip trailing inline comment from the value.
        comment = ""
        if "#" in value:
            value, comment = value.split("#", 1)
            comment = "#" + comment
        items = [v.strip() for v in value.split(",") if v.strip()]
        if name in items:
            return  # already present
        items.append(name)
        new_value = ",".join(items)
        if comment:
            new_value = new_value + " " + comment
        lines[i] = f"PROVIDERS={new_value}"
        _write_dotenv_lines(lines)
        # Keep the in-process env in sync so the running app sees the new
        # provider without a restart.
        os.environ["PROVIDERS"] = ",".join(items)
        return
    # No PROVIDERS= line at all — create one.
    lines.append(f"PROVIDERS={name}")
    _write_dotenv_lines(lines)
    os.environ["PROVIDERS"] = name


def _remove_from_providers_list(name: str) -> None:
    """Remove *name* from the PROVIDERS= line in .env if present."""
    lines = _read_dotenv_lines()
    changed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("PROVIDERS=") or stripped.startswith("#PROVIDERS="):
            continue
        key, _, value = stripped.partition("=")
        comment = ""
        if "#" in value:
            value, comment = value.split("#", 1)
            comment = "#" + comment
        items = [v.strip() for v in value.split(",") if v.strip()]
        if name not in items:
            return
        items = [v for v in items if v != name]
        new_value = ",".join(items)
        if comment:
            new_value = new_value + " " + comment if new_value else comment.lstrip()
        lines[i] = f"PROVIDERS={new_value}"
        os.environ["PROVIDERS"] = ",".join(items)
        changed = True
        break
    if changed:
        _write_dotenv_lines(lines)


def _refresh_providers_env() -> None:
    """Re-read the PROVIDERS= line from .env into os.environ.

    Called after sync/remove so the running process sees the updated list
    without a restart, even when the line already existed in .env.
    """
    for line in _read_dotenv_lines():
        stripped = line.strip()
        if stripped.startswith("PROVIDERS=") and not stripped.startswith("#"):
            _, _, value = stripped.partition("=")
            if "#" in value:
                value = value.split("#", 1)[0]
            items = [v.strip() for v in value.split(",") if v.strip()]
            os.environ["PROVIDERS"] = ",".join(items)
            return


def sync_provider(provider: oauth.Provider, creds: Dict[str, Any]) -> None:
    """Write/update the ``<NAME>_AUTH`` entries in .env for *provider*.

    Adds the provider name to ``PROVIDERS=`` and writes ``<NAME>_AUTH_BASE_URL``
    + ``<NAME>_AUTH_API_KEY``. Existing values are replaced in place; if the
    keys aren't present yet they're appended after the last PROVIDERS= line.
    """
    prefix = _provider_env_prefix(provider)
    access_token = creds.get("access_token", "")
    if not access_token:
        return

    lines = _read_dotenv_lines()
    base_key = f"{prefix}_BASE_URL"
    api_key = f"{prefix}_API_KEY"
    base_value = provider.api_base_url or ""

    seen_base = False
    seen_api = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith(f"{base_key}=") and not line.lstrip().startswith("#"):
            lines[i] = f"{base_key}={base_value}"
            seen_base = True
        elif line.lstrip().startswith(f"{api_key}=") and not line.lstrip().startswith("#"):
            lines[i] = f"{api_key}={access_token}"
            seen_api = True

    if not seen_base or not seen_api:
        # Append after the PROVIDERS= line if found, else at the end.
        insert_at = len(lines)
        for i, line in enumerate(lines):
            if line.strip().startswith("PROVIDERS=") and not line.strip().startswith("#"):
                insert_at = i + 1
                break
        new_lines: List[str] = []
        if not seen_base:
            new_lines.append(f"{base_key}={base_value}")
        if not seen_api:
            new_lines.append(f"{api_key}={access_token}")
        lines = lines[:insert_at] + new_lines + lines[insert_at:]

    _write_dotenv_lines(lines)
    _ensure_providers_list_has(prefix)

    # Also update the in-process environment so the running app picks it up
    # without a restart. We re-read the PROVIDERS list from .env to stay
    # consistent with what _ensure_providers_list_has just wrote.
    _refresh_providers_env()
    os.environ[f"{base_key}"] = base_value
    os.environ[f"{api_key}"] = access_token

    # Invalidate the model_client provider cache so the new token is used.
    try:
        from . import model_client  # local import to avoid cycles
        model_client._MODEL_LIST_CACHE.clear()
    except Exception:
        pass


def remove_provider(provider: oauth.Provider) -> None:
    """Remove the ``<NAME>_AUTH`` entries from .env for *provider*."""
    prefix = _provider_env_prefix(provider)
    lines = _read_dotenv_lines()
    kept = [line for line in lines if not _is_auth_key_line(line, prefix)]
    if len(kept) != len(lines):
        _write_dotenv_lines(kept)
    _remove_from_providers_list(prefix)

    # Clear from the in-process environment too.
    os.environ.pop(f"{prefix}_BASE_URL", None)
    os.environ.pop(f"{prefix}_API_KEY", None)
    _refresh_providers_env()

    try:
        from . import model_client
        model_client._MODEL_LIST_CACHE.clear()
    except Exception:
        pass


def provider_env_status(provider: oauth.Provider) -> Dict[str, Any]:
    """Return a small snapshot of what's currently in .env for *provider*."""
    prefix = _provider_env_prefix(provider)
    return {
        "env_name": prefix,
        "base_url": os.getenv(f"{prefix}_BASE_URL", ""),
        "has_api_key": bool(os.getenv(f"{prefix}_API_KEY", "")),
    }