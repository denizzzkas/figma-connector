"""Figma Connector — chat-function tools: list_styles, list_components, get_comments, get_image_fills.

Split out from tools.py to keep each module under ~300 lines (see main.py).
These four cover the file-wide/library-scoped Figma REST endpoints, as
opposed to tools.py which is scoped to a single node/frame or export.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

from app import chat
from figma_client import FigmaLookupError, figma_get, resolve_file_and_node
from models import (
    FigmaComment,
    FigmaComponentInfo,
    FigmaImageFill,
    FigmaStyleInfo,
    FileScopedParams,
    GetCommentsResult,
    GetImageFillsResult,
    ListComponentsResult,
    ListStylesResult,
)


@chat.function(
    "list_styles",
    action_type="read",
    data_model=ListStylesResult,
    description=(
        "List every named local style (design token) defined in a Figma file — color/fill styles, "
        "text styles, effect styles and grid styles — with their name and style_id. Use this to see "
        "the file's real design-system palette/type-scale by name (e.g. 'Navy/900', 'Heading/H1') "
        "rather than reading raw hex values off individual layers. Read-only."
    ),
)
async def fn_list_styles(ctx, params: FileScopedParams) -> ActionResult:
    """Fetch /files/{key}/styles — the file's published local styles."""
    try:
        file_key, _ = resolve_file_and_node(params.figma_url, params.file_key, None)
        data = await figma_get(ctx, f"/files/{file_key}/styles")
    except FigmaLookupError as e:
        return ActionResult.error(e.message, retryable=e.retryable, code=e.code)

    styles = [
        FigmaStyleInfo(
            style_id=s.get("node_id", s.get("key", "")),
            name=s.get("name", ""),
            style_type=s.get("style_type", ""),
            description=s.get("description", ""),
        )
        for s in (data.get("meta", {}).get("styles") or data.get("styles") or [])
    ]
    result = ListStylesResult(file_key=file_key, styles=styles)
    return ActionResult.success(
        data=result,
        summary=f"{len(styles)} local style(s) found in file {file_key}.",
    )


@chat.function(
    "list_components",
    action_type="read",
    data_model=ListComponentsResult,
    description=(
        "List every reusable component defined in a Figma file — name, component_id (usable directly "
        "as a node_id with get_node), description, and its parent component_set_id if it's a variant. "
        "Use this to discover a design system's building blocks (buttons, icons, cards) by name before "
        "inspecting one in detail with get_node. Read-only."
    ),
)
async def fn_list_components(ctx, params: FileScopedParams) -> ActionResult:
    """Fetch /files/{key}/components — the file's published components."""
    try:
        file_key, _ = resolve_file_and_node(params.figma_url, params.file_key, None)
        data = await figma_get(ctx, f"/files/{file_key}/components")
    except FigmaLookupError as e:
        return ActionResult.error(e.message, retryable=e.retryable, code=e.code)

    components = [
        FigmaComponentInfo(
            component_id=c.get("node_id", c.get("key", "")),
            name=c.get("name", ""),
            description=c.get("description", ""),
            component_set_id=c.get("component_set_id"),
        )
        for c in (data.get("meta", {}).get("components") or data.get("components") or [])
    ]
    result = ListComponentsResult(file_key=file_key, components=components)
    return ActionResult.success(
        data=result,
        summary=f"{len(components)} component(s) found in file {file_key}.",
    )


@chat.function(
    "get_comments",
    action_type="read",
    data_model=GetCommentsResult,
    description=(
        "Read every comment left on a Figma file — text, author, timestamp, resolved status, and which "
        "node (if any) it's pinned to. Use this to see design feedback/annotations without opening Figma. "
        "Read-only, requires the file_comments:read scope on the token."
    ),
)
async def fn_get_comments(ctx, params: FileScopedParams) -> ActionResult:
    """Fetch /files/{key}/comments — all comment threads on the file."""
    try:
        file_key, _ = resolve_file_and_node(params.figma_url, params.file_key, None)
        data = await figma_get(ctx, f"/files/{file_key}/comments")
    except FigmaLookupError as e:
        return ActionResult.error(e.message, retryable=e.retryable, code=e.code)

    comments = []
    for c in data.get("comments", []) or []:
        client_meta = c.get("client_meta") or {}
        comments.append(FigmaComment(
            comment_id=c.get("id", ""),
            message=c.get("message", ""),
            author=(c.get("user") or {}).get("handle", ""),
            created_at=c.get("created_at", ""),
            resolved=bool(c.get("resolved_at")),
            node_id=client_meta.get("node_id"),
        ))
    result = GetCommentsResult(file_key=file_key, comments=comments)
    return ActionResult.success(
        data=result,
        summary=f"{len(comments)} comment(s) found in file {file_key}.",
    )


@chat.function(
    "get_image_fills",
    action_type="read",
    data_model=GetImageFillsResult,
    description=(
        "List every distinct bitmap image (photo/texture) used as a fill anywhere in a Figma file, with "
        "a temporary download URL for each original file. Use this to pull out real photography/imagery "
        "assets a design references, not just vector shapes. Read-only."
    ),
)
async def fn_get_image_fills(ctx, params: FileScopedParams) -> ActionResult:
    """Fetch /files/{key}/images — download URLs for every imageRef used in the file."""
    try:
        file_key, _ = resolve_file_and_node(params.figma_url, params.file_key, None)
        data = await figma_get(ctx, f"/files/{file_key}/images")
    except FigmaLookupError as e:
        return ActionResult.error(e.message, retryable=e.retryable, code=e.code)

    images_map = data.get("meta", {}).get("images") or data.get("images") or {}
    images = [FigmaImageFill(image_ref=ref, url=url) for ref, url in images_map.items() if url]
    result = GetImageFillsResult(file_key=file_key, images=images)
    return ActionResult.success(
        data=result,
        summary=f"{len(images)} distinct image fill(s) found in file {file_key}.",
    )
