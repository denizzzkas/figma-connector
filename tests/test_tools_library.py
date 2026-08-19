"""Tests for tools_library.py — file-wide/library-scoped Figma tools.

Split out of test_main.py to keep each test module under ~300 lines,
mirroring the tools.py / tools_library.py production split.
"""
import pytest
from imperal_sdk.testing import MockContext, MockSecretStore

from tools_library import (
    fn_get_comments,
    fn_get_image_fills,
    fn_list_components,
    fn_list_styles,
)
from models import FileScopedParams

FILE_URL = "https://www.figma.com/design/FzzvYCgqrorlgu0TakV4Pa/Brand-book?node-id=19-207&t=xyz"


def _ctx(with_token: bool = True) -> "Context":
    ctx = MockContext(user_id="imp_u_test")
    ctx.secrets = MockSecretStore({"figma_api_key": "fake-token"} if with_token else {})
    return ctx


@pytest.mark.asyncio
async def test_list_styles_success():
    ctx = _ctx()
    ctx.http.mock_get(
        "/files/FzzvYCgqrorlgu0TakV4Pa/styles",
        {
            "meta": {
                "styles": [
                    {"node_id": "1:1", "name": "Navy/900", "style_type": "FILL", "description": "Primary navy"},
                    {"node_id": "1:2", "name": "Heading/H1", "style_type": "TEXT", "description": ""},
                ]
            }
        },
    )
    result = await fn_list_styles(ctx, FileScopedParams(figma_url=FILE_URL))
    assert result.status == "success"
    assert len(result.data.styles) == 2
    assert result.data.styles[0].name == "Navy/900"
    assert result.data.styles[0].style_type == "FILL"


@pytest.mark.asyncio
async def test_list_components_success():
    ctx = _ctx()
    ctx.http.mock_get(
        "/files/FzzvYCgqrorlgu0TakV4Pa/components",
        {
            "meta": {
                "components": [
                    {"node_id": "2:1", "name": "Button/Primary", "description": "CTA button",
                     "component_set_id": "2:0"},
                ]
            }
        },
    )
    result = await fn_list_components(ctx, FileScopedParams(figma_url=FILE_URL))
    assert result.status == "success"
    assert len(result.data.components) == 1
    assert result.data.components[0].name == "Button/Primary"
    assert result.data.components[0].component_set_id == "2:0"


@pytest.mark.asyncio
async def test_get_comments_success():
    ctx = _ctx()
    ctx.http.mock_get(
        "/files/FzzvYCgqrorlgu0TakV4Pa/comments",
        {
            "comments": [
                {
                    "id": "c1", "message": "Fix the kerning here",
                    "user": {"handle": "denis"},
                    "created_at": "2026-08-01T00:00:00Z",
                    "resolved_at": None,
                    "client_meta": {"node_id": "19:207"},
                },
            ]
        },
    )
    result = await fn_get_comments(ctx, FileScopedParams(figma_url=FILE_URL))
    assert result.status == "success"
    assert len(result.data.comments) == 1
    assert result.data.comments[0].message == "Fix the kerning here"
    assert result.data.comments[0].author == "denis"
    assert result.data.comments[0].resolved is False
    assert result.data.comments[0].node_id == "19:207"


@pytest.mark.asyncio
async def test_get_image_fills_success():
    ctx = _ctx()
    ctx.http.mock_get(
        "/files/FzzvYCgqrorlgu0TakV4Pa/images",
        {"meta": {"images": {"abc123": "https://figma-alpha-api.s3.amazonaws.com/img.png"}}},
    )
    result = await fn_get_image_fills(ctx, FileScopedParams(figma_url=FILE_URL))
    assert result.status == "success"
    assert len(result.data.images) == 1
    assert result.data.images[0].image_ref == "abc123"
    assert result.data.images[0].url.startswith("https://")
