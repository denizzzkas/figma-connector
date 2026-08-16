"""Figma Connector — Pydantic param/result models for the chat tools."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# shared style building blocks
# ---------------------------------------------------------------------------

class FigmaColor(BaseModel):
    hex: str = Field(description="Color as '#rrggbb' (or '#rrggbbaa' if alpha < 1)")
    r: float = Field(description="Red channel, 0-1 (raw Figma value)")
    g: float = Field(description="Green channel, 0-1 (raw Figma value)")
    b: float = Field(description="Blue channel, 0-1 (raw Figma value)")
    a: float = Field(default=1.0, description="Alpha, 0-1")


class FigmaGradientStop(BaseModel):
    position: float = Field(description="Position along the gradient axis, 0-1")
    color: FigmaColor


class FigmaPaint(BaseModel):
    type: str = Field(description="SOLID, GRADIENT_LINEAR, GRADIENT_RADIAL, GRADIENT_ANGULAR, GRADIENT_DIAMOND, IMAGE, or PATTERN")
    visible: bool = Field(default=True)
    opacity: float = Field(default=1.0, description="Paint opacity, 0-1")
    color: Optional[FigmaColor] = Field(default=None, description="Solid color, only for type=SOLID")
    gradient_stops: list[FigmaGradientStop] = Field(default_factory=list, description="Color stops, only for gradient types")


class FigmaEffect(BaseModel):
    type: str = Field(description="DROP_SHADOW, INNER_SHADOW, LAYER_BLUR, or BACKGROUND_BLUR")
    visible: bool = Field(default=True)
    radius: Optional[float] = Field(default=None, description="Blur/shadow radius in px")
    spread: Optional[float] = Field(default=None, description="Shadow spread in px (shadows only)")
    color: Optional[FigmaColor] = Field(default=None, description="Shadow color (shadows only)")
    offset_x: Optional[float] = Field(default=None, description="Shadow x offset in px (shadows only)")
    offset_y: Optional[float] = Field(default=None, description="Shadow y offset in px (shadows only)")


class FigmaTextStyle(BaseModel):
    font_family: Optional[str] = Field(default=None)
    font_weight: Optional[float] = Field(default=None, description="Numeric font weight, e.g. 400, 700")
    font_size: Optional[float] = Field(default=None, description="Font size in px")
    line_height_px: Optional[float] = Field(default=None)
    letter_spacing: Optional[float] = Field(default=None, description="Space between characters in px")
    text_align_horizontal: Optional[str] = Field(default=None, description="LEFT, CENTER, RIGHT, or JUSTIFIED")
    text_align_vertical: Optional[str] = Field(default=None, description="TOP, CENTER, or BOTTOM")
    text_case: Optional[str] = Field(default=None, description="ORIGINAL, UPPER, LOWER, or TITLE")
    text_decoration: Optional[str] = Field(default=None, description="NONE, UNDERLINE, or STRIKETHROUGH")


# ---------------------------------------------------------------------------
# get_file
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


# ---------------------------------------------------------------------------
# get_node
# ---------------------------------------------------------------------------

class GetNodeParams(BaseModel):
    figma_url: Optional[str] = Field(
        default=None,
        description="A Figma frame URL with ?node-id=..., e.g. https://www.figma.com/design/<key>/<name>?node-id=19-207",
    )
    file_key: Optional[str] = Field(default=None, description="Figma file key, if not embedded in figma_url.")
    node_id: Optional[str] = Field(default=None, description="Figma node id, e.g. '19:207' or '19-207'.")
    include_geometry: bool = Field(
        default=False,
        description=(
            "Also fetch resolved vector curves (SVG path data) for VECTOR/BOOLEAN_OPERATION/"
            "STAR/LINE/ELLIPSE/POLYGON child layers. Costs one extra Figma API call — leave off "
            "unless you actually need the exact curve geometry."
        ),
    )
    max_depth: int = Field(
        default=1, ge=1, le=8,
        description=(
            "How many levels deep to walk into nested children. 1 = only direct children "
            "(default, matches old behaviour). Raise this to see layers nested inside groups/"
            "components/auto-layout frames, e.g. an icon inside a button inside a card."
        ),
    )


class FigmaLayer(BaseModel):
    id: str = Field(description="Layer/node id")
    name: str = Field(description="Layer name")
    type: str = Field(description="Figma node type, e.g. FRAME, TEXT, VECTOR, COMPONENT")
    depth: int = Field(default=1, description="Nesting depth relative to the requested node (1 = direct child)")
    parent_path: str = Field(default="", description="Ancestor layer names joined by ' > ', e.g. 'Card > Button'")
    width: Optional[float] = Field(default=None, description="Bounding box width in px")
    height: Optional[float] = Field(default=None, description="Bounding box height in px")
    characters: Optional[str] = Field(default=None, description="Text content, only present for TEXT layers")

    opacity: float = Field(default=1.0, description="Layer opacity, 0-1")
    corner_radius: Optional[float] = Field(default=None, description="Uniform corner radius in px, if set")
    fills: list[FigmaPaint] = Field(default_factory=list, description="Fill paints (solid color or gradient)")
    strokes: list[FigmaPaint] = Field(default_factory=list, description="Stroke paints")
    stroke_weight: Optional[float] = Field(default=None, description="Stroke thickness in px")
    effects: list[FigmaEffect] = Field(default_factory=list, description="Shadows and blurs")
    text_style: Optional[FigmaTextStyle] = Field(default=None, description="Typography, only present for TEXT layers")
    fill_geometry_svg_paths: list[str] = Field(
        default_factory=list,
        description="Resolved outline as SVG path 'd' strings — only populated when include_geometry=True and the layer has vector geometry",
    )


class GetNodeResult(BaseModel):
    file_key: str = Field(description="Resolved Figma file key")
    node_id: str = Field(description="Resolved Figma node id")
    node_name: str = Field(description="Name of the requested node")
    node_type: str = Field(description="Figma node type of the requested node")
    width: Optional[float] = Field(default=None, description="Node bounding box width in px")
    height: Optional[float] = Field(default=None, description="Node bounding box height in px")
    layers: list[FigmaLayer] = Field(description="Direct child layers of the requested node")


# ---------------------------------------------------------------------------
# export_image
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


# ---------------------------------------------------------------------------
# list_styles — enumerate named design tokens (colors/text/effects/grids)
# ---------------------------------------------------------------------------

class FileScopedParams(BaseModel):
    figma_url: Optional[str] = Field(
        default=None, description="A Figma file URL, e.g. https://www.figma.com/design/<key>/<name>",
    )
    file_key: Optional[str] = Field(default=None, description="Figma file key, if not passing figma_url.")


class FigmaStyleInfo(BaseModel):
    style_id: str = Field(description="Style node id (usable as a node_id with get_node)")
    name: str = Field(description="Style name, e.g. 'Navy/900' or 'Heading/H1'")
    style_type: str = Field(description="FILL, TEXT, EFFECT, or GRID")
    description: str = Field(default="", description="Author-written description, if any")


class ListStylesResult(BaseModel):
    file_key: str = Field(description="Resolved Figma file key")
    styles: list[FigmaStyleInfo] = Field(description="Every named local style defined in the file")


# ---------------------------------------------------------------------------
# list_components — enumerate reusable components / component sets
# ---------------------------------------------------------------------------

class FigmaComponentInfo(BaseModel):
    component_id: str = Field(description="Component node id (usable as a node_id with get_node)")
    name: str = Field(description="Component name")
    description: str = Field(default="", description="Author-written description, if any")
    component_set_id: Optional[str] = Field(default=None, description="Parent component set id, if this is a variant")


class ListComponentsResult(BaseModel):
    file_key: str = Field(description="Resolved Figma file key")
    components: list[FigmaComponentInfo] = Field(description="Every reusable component defined in the file")


# ---------------------------------------------------------------------------
# get_comments — read-only feedback/annotations left on the file
# ---------------------------------------------------------------------------

class FigmaComment(BaseModel):
    comment_id: str = Field(description="Comment id")
    message: str = Field(description="Comment text")
    author: str = Field(default="", description="Display name of whoever wrote it")
    created_at: str = Field(default="", description="ISO timestamp")
    resolved: bool = Field(default=False, description="Whether the comment thread is marked resolved")
    node_id: Optional[str] = Field(default=None, description="Node this comment is pinned to, if positioned on a layer")


class GetCommentsResult(BaseModel):
    file_key: str = Field(description="Resolved Figma file key")
    comments: list[FigmaComment] = Field(description="All comments on the file, unresolved and resolved")


# ---------------------------------------------------------------------------
# get_image_fills — real bitmap assets (photos/textures) used as fills
# ---------------------------------------------------------------------------

class FigmaImageFill(BaseModel):
    image_ref: str = Field(description="Figma's internal image reference id")
    url: str = Field(description="Temporary signed download URL for the original bitmap (expires)")


class GetImageFillsResult(BaseModel):
    file_key: str = Field(description="Resolved Figma file key")
    images: list[FigmaImageFill] = Field(description="Every distinct bitmap image used as a fill anywhere in the file")
