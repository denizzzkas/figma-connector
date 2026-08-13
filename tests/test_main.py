"""Tests for figma-connector extension."""
import pytest
from imperal_sdk.testing import MockContext, MockSecretStore

from app import ext
from figma_client import FigmaLookupError, resolve_file_and_node
from tools import fn_get_file, fn_get_node, fn_export_image
from models import GetFileParams, GetNodeParams, ExportImageParams

FILE_URL = "https://www.figma.com/design/FzzvYCgqrorlgu0TakV4Pa/Brand-book?node-id=19-207&t=xyz"


def _ctx(with_token: bool = True) -> "Context":
    ctx = MockContext(user_id="imp_u_test")
    ctx.secrets = MockSecretStore({"figma_api_key": "fake-token"} if with_token else {})
    return ctx


def test_extension_registered():
    assert ext.app_id == "figma-connector"
    assert ext.version == "1.0.0"
    assert ext.display_name and ext.display_name != ext.app_id
    assert len(ext.description) >= 40
    assert "figma_api_key" in ext.secrets


def test_resolve_file_and_node_from_url():
    file_key, node_id = resolve_file_and_node(FILE_URL, None, None)
    assert file_key == "FzzvYCgqrorlgu0TakV4Pa"
    assert node_id == "19:207"


def test_resolve_file_and_node_missing_key_raises():
    with pytest.raises(FigmaLookupError):
        resolve_file_and_node(None, None, None)


@pytest.mark.asyncio
async def test_get_file_missing_token_errors():
    ctx = _ctx(with_token=False)
    result = await fn_get_file(ctx, GetFileParams(figma_url=FILE_URL))
    assert result.status == "error"
    assert "Figma API key" in (result.error or "")


@pytest.mark.asyncio
async def test_get_file_success():
    ctx = _ctx()
    ctx.http.mock_get(
        "/files/FzzvYCgqrorlgu0TakV4Pa",
        {
            "name": "Brand-book",
            "lastModified": "2026-08-01T00:00:00Z",
            "document": {"children": [{"id": "0:1", "name": "Page 1", "children": [{}, {}]}]},
        },
    )
    result = await fn_get_file(ctx, GetFileParams(figma_url=FILE_URL))
    assert result.status == "success"
    assert result.data.file_name == "Brand-book"
    assert result.data.pages[0].top_level_frame_count == 2


@pytest.mark.asyncio
async def test_get_node_success():
    ctx = _ctx()
    ctx.http.mock_get(
        "/files/FzzvYCgqrorlgu0TakV4Pa/nodes",
        {
            "nodes": {
                "19:207": {
                    "document": {
                        "id": "19:207",
                        "name": "Logo Lockups",
                        "type": "FRAME",
                        "absoluteBoundingBox": {"width": 800, "height": 600},
                        "children": [
                            {"id": "19:208", "name": "Primary Mark", "type": "COMPONENT",
                             "absoluteBoundingBox": {"width": 200, "height": 200}},
                        ],
                    }
                }
            }
        },
    )
    result = await fn_get_node(ctx, GetNodeParams(figma_url=FILE_URL))
    assert result.status == "success"
    assert result.data.node_name == "Logo Lockups"
    assert result.data.width == 800
    assert len(result.data.layers) == 1


@pytest.mark.asyncio
async def test_get_node_not_found_errors():
    ctx = _ctx()
    ctx.http.mock_get("/files/FzzvYCgqrorlgu0TakV4Pa/nodes", {"nodes": {}})
    result = await fn_get_node(ctx, GetNodeParams(figma_url=FILE_URL))
    assert result.status == "error"


@pytest.mark.asyncio
async def test_get_node_returns_full_style_data():
    """A layer's colors, stroke, shadow and typography should survive parsing intact."""
    ctx = _ctx()
    ctx.http.mock_get(
        "/files/FzzvYCgqrorlgu0TakV4Pa/nodes",
        {
            "nodes": {
                "19:207": {
                    "document": {
                        "id": "19:207",
                        "name": "Logo Lockups",
                        "type": "FRAME",
                        "absoluteBoundingBox": {"width": 800, "height": 600},
                        "children": [
                            {
                                "id": "19:208",
                                "name": "Primary Mark",
                                "type": "RECTANGLE",
                                "absoluteBoundingBox": {"width": 200, "height": 200},
                                "opacity": 0.9,
                                "cornerRadius": 12,
                                "fills": [
                                    {"type": "SOLID", "visible": True, "opacity": 1,
                                     "color": {"r": 0.0, "g": 0.075, "b": 0.2, "a": 1}},
                                ],
                                "strokes": [
                                    {"type": "SOLID", "visible": True, "opacity": 1,
                                     "color": {"r": 1, "g": 1, "b": 1, "a": 1}},
                                ],
                                "strokeWeight": 2,
                                "effects": [
                                    {"type": "DROP_SHADOW", "visible": True, "radius": 8, "spread": 0,
                                     "color": {"r": 0, "g": 0, "b": 0, "a": 0.25},
                                     "offset": {"x": 0, "y": 4}},
                                ],
                            },
                            {
                                "id": "19:209",
                                "name": "Headline",
                                "type": "TEXT",
                                "absoluteBoundingBox": {"width": 400, "height": 40},
                                "characters": "Imperal",
                                "style": {
                                    "fontFamily": "Inter",
                                    "fontWeight": 700,
                                    "fontSize": 32,
                                    "lineHeightPx": 40,
                                    "letterSpacing": 0.5,
                                    "textAlignHorizontal": "LEFT",
                                    "textAlignVertical": "TOP",
                                    "textCase": "ORIGINAL",
                                    "textDecoration": "NONE",
                                },
                            },
                        ],
                    }
                }
            }
        },
    )
    result = await fn_get_node(ctx, GetNodeParams(figma_url=FILE_URL))
    assert result.status == "success"
    layers = {l.name: l for l in result.data.layers}

    mark = layers["Primary Mark"]
    assert mark.opacity == 0.9
    assert mark.corner_radius == 12
    assert mark.fills[0].type == "SOLID"
    assert mark.fills[0].color.hex == "#001333"
    assert mark.strokes[0].color.hex == "#ffffff"
    assert mark.stroke_weight == 2
    assert mark.effects[0].type == "DROP_SHADOW"
    assert mark.effects[0].radius == 8
    assert mark.effects[0].offset_y == 4
    assert mark.effects[0].color.a == 0.25

    headline = layers["Headline"]
    assert headline.text_style.font_family == "Inter"
    assert headline.text_style.font_weight == 700
    assert headline.text_style.font_size == 32
    assert headline.text_style.letter_spacing == 0.5


@pytest.mark.asyncio
async def test_get_node_include_geometry_fetches_svg_paths(monkeypatch):
    """include_geometry=True should make a second Figma call with geometry=paths and attach the curves.

    MockHTTP matches purely by URL substring (it ignores query params), so it
    can't tell apart two calls to the same /nodes path with different `ids`/
    `geometry` params. We monkeypatch tools.figma_get directly instead, which
    also lets us assert the exact params fn_get_node sends on each call.
    """
    calls: list[dict] = []

    async def fake_figma_get(ctx, path, params=None):
        calls.append({"path": path, "params": params or {}})
        if params and params.get("geometry") == "paths":
            return {
                "nodes": {
                    "19:210": {
                        "document": {
                            "id": "19:210",
                            "fillGeometry": [{"path": "M0 0L64 0L64 64L0 64Z", "windingRule": "NONZERO"}],
                        }
                    }
                }
            }
        return {
            "nodes": {
                "19:207": {
                    "document": {
                        "id": "19:207",
                        "name": "Logo Lockups",
                        "type": "FRAME",
                        "absoluteBoundingBox": {"width": 800, "height": 600},
                        "children": [
                            {"id": "19:210", "name": "Icon Outline", "type": "VECTOR",
                             "absoluteBoundingBox": {"width": 64, "height": 64}},
                        ],
                    }
                }
            }
        }

    monkeypatch.setattr("tools.figma_get", fake_figma_get)
    ctx = _ctx()
    result = await fn_get_node(ctx, GetNodeParams(figma_url=FILE_URL, include_geometry=True))
    assert result.status == "success"
    icon = result.data.layers[0]
    assert icon.fill_geometry_svg_paths == ["M0 0L64 0L64 64L0 64Z"]

    # Second call must have asked Figma for real vector outlines on the VECTOR child.
    geometry_calls = [c for c in calls if c["params"].get("geometry") == "paths"]
    assert len(geometry_calls) == 1
    assert geometry_calls[0]["params"]["ids"] == "19:210"


@pytest.mark.asyncio
async def test_export_image_success():
    ctx = _ctx()
    ctx.http.mock_get(
        "/images/FzzvYCgqrorlgu0TakV4Pa",
        {"images": {"19:207": "https://figma-alpha-api.s3.amazonaws.com/fake.png"}},
    )
    result = await fn_export_image(ctx, ExportImageParams(figma_url=FILE_URL, format="png"))
    assert result.status == "success"
    assert result.data.image_url.startswith("https://")


@pytest.mark.asyncio
async def test_export_image_bad_format_errors():
    ctx = _ctx()
    result = await fn_export_image(ctx, ExportImageParams(figma_url=FILE_URL, format="webp"))
    assert result.status == "error"
