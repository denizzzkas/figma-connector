"""Figma Connector — shared Figma REST API client + URL/id resolution.

Kept separate from the chat-function handlers so the HTTP/parsing logic can
be unit-tested and reused independently of any single tool.
"""
from __future__ import annotations

import re
from typing import Optional

FIGMA_API_BASE = "https://api.figma.com/v1"

_FILE_KEY_RE = re.compile(r"figma\.com/(?:file|design)/([a-zA-Z0-9]+)")
_NODE_ID_RE = re.compile(r"node-id=([^&]+)")


class FigmaLookupError(Exception):
    """Expected, user-facing lookup failure — never a raw traceback in chat."""

    def __init__(self, message: str, code: str, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


def resolve_file_and_node(
    figma_url: Optional[str],
    file_key: Optional[str],
    node_id: Optional[str],
) -> tuple[str, Optional[str]]:
    """Resolve (file_key, node_id) from either a pasted URL or explicit fields.

    A Figma URL's node-id query param uses '-' where the API wants ':'
    (e.g. '19-207' in the URL vs. '19:207' for the API), so we normalise it.
    """
    resolved_key = file_key
    resolved_node = node_id

    if figma_url:
        key_match = _FILE_KEY_RE.search(figma_url)
        if key_match and not resolved_key:
            resolved_key = key_match.group(1)
        node_match = _NODE_ID_RE.search(figma_url)
        if node_match and not resolved_node:
            resolved_node = node_match.group(1)

    if resolved_node:
        resolved_node = resolved_node.replace("%3A", ":")
        if "-" in resolved_node and ":" not in resolved_node:
            resolved_node = resolved_node.replace("-", ":", 1)

    if not resolved_key:
        raise FigmaLookupError(
            "Could not resolve a Figma file key. Paste a figma.com/design/... "
            "or figma.com/file/... URL, or pass file_key directly.",
            code="FIGMA_URL_UNRESOLVED",
        )
    return resolved_key, resolved_node


async def figma_get(ctx, path: str, params: dict | None = None) -> dict:
    """GET against the Figma REST API using the user's stored token."""
    token = await ctx.secrets.get("figma_api_key")
    if not token:
        raise FigmaLookupError(
            "No Figma API key saved yet. Add one in the extension's Secrets "
            "panel: Figma → Settings → Security → Personal access tokens "
            "(read-only 'File content' scope is enough).",
            code="FIGMA_TOKEN_MISSING",
        )
    resp = await ctx.http.get(
        f"{FIGMA_API_BASE}{path}",
        headers={"X-Figma-Token": token},
        params=params or {},
        timeout=30,
    )
    if resp.status_code == 403:
        raise FigmaLookupError(
            "Figma rejected the token (403). Check it hasn't expired or been "
            "revoked, and that it has file-read access to this file.",
            code="FIGMA_TOKEN_REJECTED",
            retryable=True,
        )
    if resp.status_code == 404:
        raise FigmaLookupError(
            "Figma file or node not found (404). Check the URL/key/node id, "
            "and that the token's account has access to this file.",
            code="FIGMA_NOT_FOUND",
        )
    if resp.status_code >= 400:
        raise FigmaLookupError(
            f"Figma API error {resp.status_code}: {resp.body}",
            code="FIGMA_API_ERROR",
            retryable=True,
        )
    return resp.body if isinstance(resp.body, dict) else {}
