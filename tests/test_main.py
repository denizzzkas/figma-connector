"""Tests for figma-connector extension."""
import pytest
from imperal_sdk.testing import MockContext, MockSecretStore

from main import (
    FigmaLookupError,
    ext,
    fn_get_file,
    fn_get_node,
    fn_export_image,
    GetFileParams,
    GetNodeParams,
    ExportImageParams,
    _resolve_file_and_node,
)

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
    file_key, node_id = _resolve_file_and_node(FILE_URL, None, None)
    assert file_key == "FzzvYCgqrorlgu0TakV4Pa"
    assert node_id == "19:207"


def test_resolve_file_and_node_missing_key_raises():
    with pytest.raises(FigmaLookupError):
        _resolve_file_and_node(None, None, None)


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
