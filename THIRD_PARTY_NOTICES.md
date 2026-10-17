# Third-party notices

| Component | Role | License and provenance |
| --- | --- | --- |
| [FreeCAD MCP](https://github.com/neka-nat/freecad-mcp) | Vendored MCP server and FreeCAD addon | MIT. Copyright 2025 Shirokuma (k tanaka). Original notice is preserved in `container/vendor/freecad-mcp/LICENSE`. The exact 29-file snapshot and upstream checkout commit are recorded in `container/vendor/source-manifest.json`; local working-tree files are identified by hash and are not claimed to be a pristine upstream release. |
| [FreeCAD](https://github.com/FreeCAD/FreeCAD) | Native CAD creation, validation, and rendering | Distributed by its upstream and Debian package maintainers under their applicable licenses. Installed by the container build; its binary is not vendored in this Git repository. |
| [OpenCode](https://github.com/anomalyco/opencode) | Agent execution harness | Upstream license applies. Version 1.19.3 is installed by the container build. |
| [uv](https://github.com/astral-sh/uv) | Python dependency management | Upstream MIT or Apache-2.0 licenses apply. |
| [VitePress](https://github.com/vuejs/vitepress) | Documentation website | MIT. Dependencies are listed in `package-lock.json`. |

Runtime package versions are captured in each built image's `/opt/debian-packages.lock`. Python dependencies for the vendored server are fixed by its `uv.lock`. The container's base-image digests and selected package versions are pinned, but Debian repository availability and transitive package changes can affect a future rebuild. Transfer a saved OCI image to reproduce an exact existing runtime. A tag alone does not establish identity; compare image IDs and package/source records.

The user-provided reference screenshot and generated benchmark records are excluded from the root MIT grant as explained in [NOTICE.md](NOTICE.md).
