"""Figma Connector — chat-function tools: get_file, get_node, export_image."""
from __future__ import annotations

from imperal_sdk import ActionResult

from app import chat
from figma_client import FigmaLookupError, figma_get, resolve_file_and_node
from models import (
    ExportImageParams,
    ExportImageResult,
    FigmaLayer,
    FigmaPage,
    GetFileParams,
    GetFileResult,
    GetNodeParams,
    GetNodeResult,
)


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
    "get_file",
    action_type="read",
    data_model=GetFileResult,
    description="Look up a Figma file's name and page/frame structure from a pasted file URL or file key. Read-only.",
)
async def fn_get_file(ctx, params: GetFileParams) -> ActionResult:
    """Fetch top-level file metadata + page list (not full node tree — use get_node for that)."""
    try:
        file_key, _ = resolve_file_and_node(params.figma_url, params.file_key, None)
        data = await figma_get(ctx, f"/files/{file_key}", params={"depth": 1})
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


@chat.function(
    "get_node",
    action_type="read",
    data_model=GetNodeResult,
    description="Inspect one specific Figma node/frame (by URL or file_key+node_id): its size, type and direct child layers — text, sizes, vectors. Read-only.",
)
async def fn_get_node(ctx, params: GetNodeParams) -> ActionResult:
    """Fetch a single node subtree via /files/{key}/nodes?ids=..."""
    try:
        file_key, node_id = resolve_file_and_node(params.figma_url, params.file_key, params.node_id)
        if not node_id:
            raise FigmaLookupError(
                "No node id found. Paste a URL that includes ?node-id=... or pass node_id directly.",
                code="FIGMA_NODE_ID_MISSING",
            )
        data = await figma_get(ctx, f"/files/{file_key}/nodes", params={"ids": node_id})
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


@chat.function(
    "export_image",
    action_type="read",
    data_model=ExportImageResult,
    description="Export a specific Figma node as a PNG, SVG, PDF or JPG and return a temporary download URL. Read-only.",
)
async def fn_export_image(ctx, params: ExportImageParams) -> ActionResult:
    """Fetch a render URL for one node via /images/{key}."""
    try:
        file_key, node_id = resolve_file_and_node(params.figma_url, params.file_key, params.node_id)
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
        data = await figma_get(ctx, f"/images/{file_key}", params=query)
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
