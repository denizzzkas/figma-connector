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
  bounding box, and its child layers, each with **full visual detail**, not
  just name/size:
  - **Colors** — every fill and stroke, resolved to real hex + RGBA (solid
    colors and gradient stops alike), plus opacity and corner radius.
  - **Shadows & blur** — every effect (drop shadow, inner shadow, layer
    blur, background blur) with its color, radius, spread and offset.
  - **Typography** — for text layers: font family, weight, size, line
    height, letter spacing, case and alignment.
  - **Vector curves** — pass `include_geometry=true` to get each vector
    layer's outline as real SVG path data (Figma's `geometry=paths` mode),
    so the actual curve shape is inspectable, not just its bounding box.
  - **Nesting** — pass `max_depth` (up to 8) to walk into groups,
    auto-layout frames and component instances, not just direct children;
    each returned layer is tagged with its `depth` and `parent_path` so
    nested layers (e.g. an icon inside a button inside a card) stay
    identifiable.
- **`export_image`** — export a node as PNG, JPG, SVG or PDF; returns a
  temporary download URL.
- **`list_styles`** — every named local style (design token) published in
  the file: color/fill styles, text styles, effect styles, grid styles —
  by name, e.g. `Navy/900`, `Heading/H1`. Lets Webbee talk about the
  design system's real palette/type-scale by name, not just raw hex pulled
  off one layer.
- **`list_components`** — every reusable component defined in the file:
  name, component key, and which component-set (variant group) it belongs
  to, if any.
- **`get_comments`** — every comment thread on the file: author, message,
  resolved status, and which node/pixel position it's pinned to.
- **`get_image_fills`** — every embedded bitmap image used as a fill
  anywhere in the file, resolved to a real downloadable URL (Figma's
  `imageRef` values otherwise aren't directly usable).

All tools accept a Figma URL directly — the file key and node-id are
parsed straight out of the pasted link (`?node-id=19-207` etc.), no manual
URL surgery needed. You can also pass `file_key` / `node_id` explicitly.

### What this actually gives Webbee to work with

The Figma REST API's plain node JSON *does* carry real design data — colors,
gradients, shadows, corner radii, typography, and (via `geometry=paths`)
resolved vector curves. `get_node` now parses all of this out of the raw
response instead of only exposing name/type/size, so a component's fills,
strokes, effects and text styling are visible for real review — e.g. "what's
the exact blue used here", "how big is that drop shadow", "what's this
button's corner radius", or "show me this icon's actual outline".

The one thing still out of reach: Figma's REST API does not expose true
pixel rendering (anti-aliasing, blend-mode compositing, font hinting) the
way opening the file in Figma itself does — for a full pixel-perfect look,
pair `get_node` (real values) with `export_image` (a rendered PNG/SVG you
can view directly).

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
