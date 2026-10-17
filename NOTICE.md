# License scope and data provenance

The root [MIT license](LICENSE) covers SECCA's original source code, original documentation, and original branding. It does not replace the licenses or rights of upstream software, user-supplied inputs, or benchmark data.

## Reference image

`assets/reference.jpg` is the user-supplied racing-kart screenshot used for this experiment. Its original author, source URL, and redistribution license were not recorded. SECCA does not claim authorship or grant an MIT license to that image. Any copy in an experiment or documentation has the same rights status. Contact the maintainers about attribution, permission, or removal through the repository's issue tracker. Do not assume the screenshot is a freely licensed dataset.

## Experimental artifacts

CAD files, rendered images, and model-generated transcripts are experimental records. The root code license does not assert rights to their reference-derived visual content or to third-party material a model may reproduce. Preserve their provenance and examine the input rights before reusing them outside evaluation. SECCA makes no claim of manufacturing suitability or exclusive ownership of generated geometry.

Published records distinguish exact source bytes from portable management metadata exports. Export manifests record source and exported SHA-256 values and any transformations. Historical frozen baseline records retain original local paths, session identifiers, and machine labels as archival metadata. They are not credentials or portable execution settings. New commands require the reader's own connection and trial paths.

Historical verification copies outside the fixed assets are public transformed exports. Their [source and export manifest](references/public-export-manifest.json) identifies the changed bytes without claiming a new model run. Logical reviewer task identifiers remain part of the original review provenance.

## Upstream code and runtime software

Vendored FreeCAD MCP retains its own MIT copyright notice and source manifest. FreeCAD, OpenCode, Debian packages, Node.js, Python, and other dependencies retain their respective licenses. Container build instructions do not relicense these components. See [third-party notices](THIRD_PARTY_NOTICES.md).
