"""Figma Connector — Pydantic param/result models for the chat tools."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


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
