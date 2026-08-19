"""Figma Connector — pure-parsing helpers for get_node.

Split out of tools.py to keep each module under ~300 lines (see main.py).
Everything here is stateless: dict-in, model-out (or list-out) parsing of
raw Figma REST API node/paint/effect/style shapes. No I/O, no chat.function
registration — those live in tools.py / tools_library.py.
"""
from __future__ import annotations

from models import (
    FigmaColor,
    FigmaEffect,
    FigmaGradientStop,
    FigmaLayer,
    FigmaPaint,
    FigmaTextStyle,
)

# Node types that can carry resolved vector outlines via geometry=paths.
_VECTOR_LIKE_TYPES = {
    "VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "ELLIPSE", "POLYGON", "RECTANGLE",
}


def _parse_color(c: dict | None) -> FigmaColor | None:
    if not c:
        return None
    r, g, b = c.get("r", 0.0), c.get("g", 0.0), c.get("b", 0.0)
    a = c.get("a", 1.0)
    hex_str = "#{:02x}{:02x}{:02x}".format(
        round(max(0.0, min(1.0, r)) * 255),
        round(max(0.0, min(1.0, g)) * 255),
        round(max(0.0, min(1.0, b)) * 255),
    )
    if a < 1.0:
        hex_str += "{:02x}".format(round(max(0.0, min(1.0, a)) * 255))
    return FigmaColor(hex=hex_str, r=r, g=g, b=b, a=a)


def _parse_paint(p: dict) -> FigmaPaint:
    stops = [
        FigmaGradientStop(position=s.get("position", 0.0), color=_parse_color(s.get("color")) or FigmaColor(hex="#000000", r=0, g=0, b=0, a=1))
        for s in (p.get("gradientStops") or [])
    ]
    return FigmaPaint(
        type=p.get("type", "SOLID"),
        visible=p.get("visible", True),
        opacity=p.get("opacity", 1.0),
        color=_parse_color(p.get("color")),
        gradient_stops=stops,
    )


def _parse_effect(e: dict) -> FigmaEffect:
    offset = e.get("offset") or {}
    return FigmaEffect(
        type=e.get("type", ""),
        visible=e.get("visible", True),
        radius=e.get("radius"),
        spread=e.get("spread"),
        color=_parse_color(e.get("color")),
        offset_x=offset.get("x"),
        offset_y=offset.get("y"),
    )


def _parse_text_style(style: dict) -> FigmaTextStyle:
    return FigmaTextStyle(
        font_family=style.get("fontFamily"),
        font_weight=style.get("fontWeight"),
        font_size=style.get("fontSize"),
        line_height_px=style.get("lineHeightPx"),
        letter_spacing=style.get("letterSpacing"),
        text_align_horizontal=style.get("textAlignHorizontal"),
        text_align_vertical=style.get("textAlignVertical"),
        text_case=style.get("textCase"),
        text_decoration=style.get("textDecoration"),
    )


def _flatten_direct_children(
    node: dict,
    geometry_by_id: dict[str, list[str]] | None = None,
    max_depth: int = 1,
    _depth: int = 1,
    _parent_path: str = "",
) -> list[FigmaLayer]:
    """Walk `node`'s children up to `max_depth` levels, flattening into one list.

    depth=1 (the default) reproduces the original behaviour exactly: only
    direct children, with depth=1 and empty parent_path. Raising max_depth
    recurses into each child's own children too (groups, auto-layout
    frames, component instances), tagging each layer with how deep it is
    and the chain of ancestor names so nested layers stay identifiable.
    """
    geometry_by_id = geometry_by_id or {}
    out: list[FigmaLayer] = []
    for child in node.get("children", []) or []:
        box = child.get("absoluteBoundingBox") or {}
        style = child.get("style")
        out.append(FigmaLayer(
            id=child.get("id", ""),
            name=child.get("name", ""),
            type=child.get("type", ""),
            depth=_depth,
            parent_path=_parent_path,
            width=box.get("width"),
            height=box.get("height"),
            characters=child.get("characters"),
            opacity=child.get("opacity", 1.0),
            corner_radius=child.get("cornerRadius"),
            fills=[_parse_paint(p) for p in (child.get("fills") or []) if isinstance(p, dict)],
            strokes=[_parse_paint(p) for p in (child.get("strokes") or []) if isinstance(p, dict)],
            stroke_weight=child.get("strokeWeight"),
            effects=[_parse_effect(e) for e in (child.get("effects") or []) if isinstance(e, dict)],
            text_style=_parse_text_style(style) if style else None,
            fill_geometry_svg_paths=geometry_by_id.get(child.get("id", ""), []),
        ))
        if _depth < max_depth and child.get("children"):
            next_path = f"{_parent_path} > {child.get('name', '')}" if _parent_path else child.get("name", "")
            out.extend(_flatten_direct_children(
                child, geometry_by_id, max_depth=max_depth, _depth=_depth + 1, _parent_path=next_path,
            ))
    return out


def _extract_svg_paths(geometry_node: dict) -> list[str]:
    """Pull SVG path 'd' strings out of a node's fillGeometry (from geometry=paths)."""
    paths = geometry_node.get("fillGeometry") or []
    return [p.get("path", "") for p in paths if isinstance(p, dict) and p.get("path")]


def _collect_all_descendants(node: dict, max_depth: int, _depth: int = 1) -> list[dict]:
    """Flatten every descendant dict (not just direct children) up to max_depth levels.

    Used only to gather candidate node ids (e.g. for a geometry=paths follow-up
    call) once max_depth > 1 — the display layers themselves are still built by
    _flatten_direct_children, which tracks depth/parent_path independently.
    """
    out: list[dict] = []
    for child in node.get("children", []) or []:
        out.append(child)
        if _depth < max_depth and child.get("children"):
            out.extend(_collect_all_descendants(child, max_depth, _depth + 1))
    return out
