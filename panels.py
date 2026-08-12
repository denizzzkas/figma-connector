"""Figma Connector — left sidebar panel.

A small, always-available status/help surface: shows whether the Figma API
key is configured, and reminds the user of the three read-only commands.
Kept intentionally light — no network call to Figma on render.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext


@ext.panel(
    "figma_connector_status", slot="left", title="Figma Connector",
    icon="Figma", refresh="manual", default_width=320, min_width=280,
)
async def figma_connector_status_panel(ctx, **params) -> ui.UINode:
    """Primary left-slot surface: token status + quick usage reminder."""
    token = await ctx.secrets.get("figma_api_key")
    configured = bool(token)

    status_alert = (
        ui.Alert(
            "Figma API key is set — ready to look up files, nodes and export images.",
            title="Connected",
            type="success",
        )
        if configured
        else ui.Alert(
            "No Figma API key yet — add one below to start using this extension.",
            title="Not connected",
            type="warning",
        )
    )

    key_action = ui.Button(
        label="Update API key" if configured else "Set API key",
        variant="secondary" if configured else "primary",
        full_width=True,
        icon="KeyRound",
        on_click=ui.Navigate(path=f"/ext/{ext.app_id}/secrets#figma_api_key"),
    )

    return ui.Stack([
        ui.Header("Figma Connector", level=3, subtitle="Read-only Figma REST API bridge"),
        status_alert,
        key_action,
        ui.Link(
            "Where do I get a Figma Personal Access Token? →",
            href="https://www.figma.com/developers/api#access-tokens",
        ),
        ui.Divider("Commands"),
        ui.KeyValue([
            {"label": "get_file", "value": "File name, pages, top-level frame counts"},
            {"label": "get_node", "value": "One frame's size, type & direct child layers"},
            {"label": "export_image", "value": "Render a node as PNG / SVG / PDF / JPG"},
        ]),
        ui.Divider(),
        ui.Text(
            "Paste a Figma file or frame URL in chat — the file key and "
            "node-id are parsed out automatically.",
            variant="caption",
        ),
    ], gap=4)
