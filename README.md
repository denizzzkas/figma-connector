# Figma Connector — Imperal Cloud Extension

Read-only bridge to the Figma REST API. Paste a Figma file or frame URL in
chat and get back file/page structure, a specific node's layers and
properties, or a rendered image export — using your own Figma Personal
Access Token.

Built on the [Imperal SDK](https://panel.imperal.io) (`imperal-sdk`), talking
directly to the [Figma REST API](https://www.figma.com/developers/api) over
HTTPS. No write / canvas-editing capability — Figma only allows writing to a
canvas via its Plugin API + MCP path, never through a plain REST token, so
this extension is intentionally read-only.

## Features

- **`get_file`** — file name, last-modified date, and every page with its
  top-level frame count.
- **`get_node`** — a specific frame/node by URL or node-id: name, type,
  bounding box, and its immediate child layers.
- **`export_image`** — export a node as PNG, JPG, SVG or PDF; returns a
  temporary download URL.

All three tools accept a Figma URL directly — the file key and node-id are
parsed straight out of the pasted link (`?node-id=19-207` etc.), no manual
URL surgery needed. You can also pass `file_key` / `node_id` explicitly.

## Getting started

In Imperal chat:
```
Show me the structure of my Figma file <url>
```

Open **Panel → Figma Connector → Secrets** and paste your Figma Personal
Access Token (Figma → Settings → Security → Personal access tokens). Only
the read-only "File content" scope is needed — never grant write scopes,
this extension does not use them. The token is stored encrypted and is never
sent through chat.

## Requirements

- A Figma account with at least read access to the file you want to inspect.
- A Figma Personal Access Token.

## Notes

- Export links returned by Figma expire — download promptly.
- Errors (missing token, file/node not found, bad export format) come back
  as clear chat messages, never raw tracebacks.

## License

LGPL-3.0 — see [LICENSE](LICENSE).
