"""Figma Connector extension — Imperal Cloud.

Read-only bridge to the Figma REST API. Paste a Figma file/frame URL (or a
raw file key + node id) and get back file/page structure, a specific node's
layers and properties, or a rendered image export (PNG/SVG/PDF) — all via a
single user-supplied Personal Access Token stored as an encrypted secret.

No write / canvas-editing capability is implemented on purpose — Figma only
allows writing to a canvas via its MCP + Plugin API path (a different,
heavier integration), never via a plain REST API token. This extension is
intentionally read-only.
"""
import re
from typing import Optional

from pydantic import BaseModel, Field
from imperal_sdk import Extension, ChatExtension, ActionResult, HealthStatus

FIGMA_API_BASE = "https://api.figma.com/v1"

ext = Extension(
    "figma-connector",
    version="1.0.0",
    display_name="Figma Connector",
    description=(
        "Read-only Figma bridge: paste a file or frame URL and Webbee can "
        "look up file structure, inspect a specific node's layers and "
        "properties, or export a node as PNG/SVG/PDF. Uses your own Figma "
        "Personal Access Token — read scope only, no canvas edits."
    ),
    icon="icon.svg",
    actions_explicit=True,
    capabilities=["figma-connector:read"],
)

ext.secret(
    name="figma_api_key",
    description=(
        "Figma Personal Access Token (Figma → Settings → Security → "
        "Personal access tokens). Read-only 'File content' scope is enough "
        "— never grant write scopes here, this extension does not use them."
    ),
    required=True,
    write_mode="user",
    max_bytes=512,
)(lambda: None)

chat = ChatExtension(
    ext,
    tool_name="figma_connector",
    description="Figma Connector — read-only lookups against the Figma REST API.",
)


@ext.health_check
async def health_check(ctx) -> HealthStatus:
    """Cheap check: is a Figma token even configured? No network call to Figma."""
    token = await ctx.secrets.get("figma_api_key")
    if not token:
        return HealthStatus.degraded("No Figma API key configured yet — read tools will fail until one is set.")
    return HealthStatus.ok({"token_configured": True})


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_FILE_KEY_RE = re.compile(r"figma\.com/(?:file|design)/([a-zA-Z0-9]+)")
_NODE_ID_RE = re.compile(r"node-id=([^&]+)")


class FigmaLookupError(Exception):
    """Expected, user-facing lookup failure — never a raw traceback in chat."""

    def __init__(self, message: str, code: str, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


def _resolve_file_and_node(
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


async def _figma_get(ctx, path: str, params: dict | None = None) -> dict:
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


# ---------------------------------------------------------------------------
# get_file — file + page/frame structure overview
# ---------------------------------------------------------------------------

class GetFileParams(BaseModel):
    figma_url: Optional[str] = Field(
        default=None,
        description="A Figma file or frame URL, e.g. https://www.figma.com/design/<key>/<name>?node-id=19-207",
    )
    file_key: Optional[str] = Field(
        default=None, description="Figma file key, if not passing figma_url."
    )


class FigmaPage(BaseModel):
    id: str = Field(description="Page node id")
    name: str = Field(description="Page name")
    top_level_frame_count: int = Field(description="Number of top-level frames/children on this page")


class GetFileResult(BaseModel):
    file_key: str = Field(description="Resolved Figma file key")
    file_name: str = Field(description="Figma file name")
    last_modified: str = Field(description="ISO timestamp of last edit")
    pages: list[FigmaPage] = Field(description="Top-level pages in the file")


@chat.function(
    "get_file",
    action_type="read",
    data_model=GetFileResult,
    description="Look up a Figma file's name and page/frame structure from a pasted file URL or file key. Read-only.",
)
async def fn_get_file(ctx, params: GetFileParams) -> ActionResult:
    """Fetch top-level file metadata + page list (not full node tree — use get_node for that)."""
    try:
        file_key, _ = _resolve_file_and_node(params.figma_url, params.file_key, None)
        data = await _figma_get(ctx, f"/files/{file_key}", params={"depth": 1})
    except FigmaLookupError as e:
        return ActionResult.error(e.message, retryable=e.retryable, code=e.code)

    doc = data.get("document", {})
    pages = [
        FigmaPage(
            id=p.get("id", ""),
            name=p.get("name", ""),
            top_level_frame_count=len(p.get("children", []) or []),
        )
        for p in doc.get("children", []) or []
    ]
    result = GetFileResult(
        file_key=file_key,
        file_name=data.get("name", ""),
        last_modified=data.get("lastModified", ""),
        pages=pages,
    )
    return ActionResult.success(
        data=result,
        summary=f"'{result.file_name}' — {len(pages)} page(s), last modified {result.last_modified}.",
    )


# ---------------------------------------------------------------------------
# get_node — a specific frame's layers + properties (e.g. the logo frame)
# ---------------------------------------------------------------------------

class GetNodeParams(BaseModel):
    figma_url: Optional[str] = Field(
        default=None,
        description="A Figma frame URL with ?node-id=..., e.g. https://www.figma.com/design/<key>/<name>?node-id=19-207",
    )
    file_key: Optional[str] = Field(default=None, description="Figma file key, if not embedded in figma_url.")
    node_id: Optional[str] = Field(default=None, description="Figma node id, e.g. '19:207' or '19-207'.")


class FigmaLayer(BaseModel):
    id: str = Field(description="Layer/node id")
    name: str = Field(description="Layer name")
    type: str = Field(description="Figma node type, e.g. FRAME, TEXT, VECTOR, COMPONENT")
    width: Optional[float] = Field(default=None, description="Bounding box width in px")
    height: Optional[float] = Field(default=None, description="Bounding box height in px")
    characters: Optional[str] = Field(default=None, description="Text content, only present for TEXT layers")


class GetNodeResult(BaseModel):
    file_key: str = Field(description="Resolved Figma file key")
    node_id: str = Field(description="Resolved Figma node id")
    node_name: str = Field(description="Name of the requested node")
    node_type: str = Field(description="Figma node type of the requested node")
    width: Optional[float] = Field(default=None, description="Node bounding box width in px")
    height: Optional[float] = Field(default=None, description="Node bounding box height in px")
    layers: list[FigmaLayer] = Field(description="Direct child layers of the requested node")


def _flatten_direct_children(node: dict) -> list[FigmaLayer]:
    out = []
    for child in node.get("children", []) or []:
        box = child.get("absoluteBoundingBox") or {}
        out.append(FigmaLayer(
            id=child.get("id", ""),
            name=child.get("name", ""),
            type=child.get("type", ""),
            width=box.get("width"),
            height=box.get("height"),
            characters=child.get("characters"),
        ))
    return out


@chat.function(
    "get_node",
    action_type="read",
    data_model=GetNodeResult,
    description="Inspect one specific Figma node/frame (by URL or file_key+node_id): its size, type and direct child layers — text, sizes, vectors. Read-only.",
)
async def fn_get_node(ctx, params: GetNodeParams) -> ActionResult:
    """Fetch a single node subtree via /files/{key}/nodes?ids=..."""
    try:
        file_key, node_id = _resolve_file_and_node(params.figma_url, params.file_key, params.node_id)
        if not node_id:
            raise FigmaLookupError(
                "No node id found. Paste a URL that includes ?node-id=... or pass node_id directly.",
                code="FIGMA_NODE_ID_MISSING",
            )
        data = await _figma_get(ctx, f"/files/{file_key}/nodes", params={"ids": node_id})
        nodes = data.get("nodes", {})
        entry = nodes.get(node_id)
        if not entry or not entry.get("document"):
            raise FigmaLookupError(
                f"Node {node_id} not found in file {file_key}. Check the node-id in the URL.",
                code="FIGMA_NOT_FOUND",
            )
    except FigmaLookupError as e:
        return ActionResult.error(e.message, retryable=e.retryable, code=e.code)

    doc = entry["document"]
    box = doc.get("absoluteBoundingBox") or {}
    result = GetNodeResult(
        file_key=file_key,
        node_id=node_id,
        node_name=doc.get("name", ""),
        node_type=doc.get("type", ""),
        width=box.get("width"),
        height=box.get("height"),
        layers=_flatten_direct_children(doc),
    )
    return ActionResult.success(
        data=result,
        summary=f"'{result.node_name}' ({result.node_type}) — {len(result.layers)} direct layer(s).",
    )


# ---------------------------------------------------------------------------
# export_image — render a node to PNG / SVG / PDF
# ---------------------------------------------------------------------------

class ExportImageParams(BaseModel):
    figma_url: Optional[str] = Field(
        default=None,
        description="A Figma frame URL with ?node-id=..., e.g. https://www.figma.com/design/<key>/<name>?node-id=19-207",
    )
    file_key: Optional[str] = Field(default=None, description="Figma file key, if not embedded in figma_url.")
    node_id: Optional[str] = Field(default=None, description="Figma node id, if not embedded in figma_url.")
    format: str = Field(default="png", description="Export format: 'png', 'svg', 'pdf', or 'jpg'.")
    scale: float = Field(default=2.0, ge=0.5, le=4.0, description="Export scale for png/jpg, 0.5-4.0.")


class ExportImageResult(BaseModel):
    file_key: str = Field(description="Resolved Figma file key")
    node_id: str = Field(description="Resolved Figma node id")
    format: str = Field(description="Export format used")
    image_url: str = Field(description="Temporary signed URL to the rendered image (Figma-hosted, expires)")


@chat.function(
    "export_image",
    action_type="read",
    data_model=ExportImageResult,
    description="Export a specific Figma node as a PNG, SVG, PDF or JPG and return a temporary download URL. Read-only.",
)
async def fn_export_image(ctx, params: ExportImageParams) -> ActionResult:
    """Fetch a render URL for one node via /images/{key}."""
    try:
        file_key, node_id = _resolve_file_and_node(params.figma_url, params.file_key, params.node_id)
        if not node_id:
            raise FigmaLookupError(
                "No node id found. Paste a URL that includes ?node-id=... or pass node_id directly.",
                code="FIGMA_NODE_ID_MISSING",
            )
        fmt = params.format.lower()
        if fmt not in ("png", "svg", "pdf", "jpg"):
            raise FigmaLookupError(
                "format must be one of: png, svg, pdf, jpg",
                code="FIGMA_FORMAT_INVALID",
            )
        query = {"ids": node_id, "format": fmt}
        if fmt in ("png", "jpg"):
            query["scale"] = params.scale
        data = await _figma_get(ctx, f"/images/{file_key}", params=query)
        images = data.get("images", {})
        url = images.get(node_id)
        if not url:
            err = data.get("err")
            raise FigmaLookupError(
                f"Figma could not render node {node_id}: {err or 'no image returned'}",
                code="FIGMA_RENDER_FAILED",
                retryable=True,
            )
    except FigmaLookupError as e:
        return ActionResult.error(e.message, retryable=e.retryable, code=e.code)

    result = ExportImageResult(file_key=file_key, node_id=node_id, format=fmt, image_url=url)
    return ActionResult.success(
        data=result,
        summary=f"Exported node {node_id} as {fmt.upper()}. Link expires — download it soon.",
    )
