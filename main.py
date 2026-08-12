"""Figma Connector — Imperal Cloud extension entrypoint.

Read-only bridge to the Figma REST API. Paste a Figma file/frame URL (or a
raw file key + node id) and get back file/page structure, a specific node's
layers and properties, or a rendered image export (PNG/SVG/PDF) — all via a
single user-supplied Personal Access Token stored as an encrypted secret.

No write / canvas-editing capability is implemented on purpose — Figma only
allows writing to a canvas via its MCP + Plugin API path (a different,
heavier integration), never via a plain REST API token. This extension is
intentionally read-only.

Implementation lives in separate modules (kept under ~300 lines each):
  - figma_client.py — URL/id resolution + the shared Figma HTTP helper
  - models.py        — Pydantic params/results for the chat tools
  - app.py            — Extension/secret/health_check/ChatExtension setup
  - tools.py          — the three @chat.function handlers
  - panels.py         — the left-sidebar status panel
This file just re-exports `ext` and forces a clean module reload so the
production host never runs a stale cached version after a redeploy.
"""
from __future__ import annotations

import os
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)

for _m in ("app", "figma_client", "models", "tools", "panels"):
    if _m in sys.modules:
        del sys.modules[_m]

from app import ext, chat  # noqa: F401
import tools  # noqa: F401
import panels  # noqa: F401
