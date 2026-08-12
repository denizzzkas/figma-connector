"""Figma Connector — Extension setup, secret declaration, health check."""
from __future__ import annotations

from imperal_sdk import Extension, ChatExtension, HealthStatus

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
