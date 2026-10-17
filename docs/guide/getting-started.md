# Get started

Prepare a local SECCA checkout and verify its fixed inputs without calling a model API.

## Requirements

| Tool | Purpose |
| --- | --- |
| Python 3.12 or newer | Host orchestration and evidence tools |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Run Python commands |
| Podman with a working named connection | Build and run isolated Linux containers |
| Git | Retrieve the source |
| Node.js 22 or newer and npm | Optional documentation development |

FreeCAD, OpenCode, and FreeCAD MCP run inside the container. Do not connect the experiment to a host FreeCAD instance.

## Verify the checkout

1. Clone the repository.

   ```sh
   git clone https://github.com/Sunwood-ai-labs/SECCA.git
   cd SECCA
   ```

2. Verify frozen assets.

   ```sh
   uv run --frozen python scripts/candidate.py verify-assets
   ```

   The command checks the SHA-256 values in `assets/manifest.json`. A mismatch must be resolved before a trial. Do not regenerate the manifest to hide a changed input.

3. Inspect the Podman machine and named connections.

   ```sh
   podman machine list
   podman system connection list
   podman --connection "<CONNECTION>" info
   ```

   Replace `<CONNECTION>` with a working connection name in every command that requires it. Leave the default connection unchanged. If Podman is unavailable, stop the trial rather than substitute host execution.

4. Build the runtime.

   ```sh
   uv run --frozen python scripts/candidate.py build --connection "<CONNECTION>" --tag localhost/kart-sbx-secca:v0.1.0
   ```

   The runner validates the `localhost/kart-sbx-` tag prefix. Building fetches external dependencies but does not invoke a model. The build records its source and package information. A trial resolves the tag to an image ID.

## Choose the next action

Continue with [Run a trial](./run). To understand the frozen task first, read [Fixed protocol](./protocol). A provider account and permission to use the selected model are required for inference.

## Preview the documentation

```sh
npm ci
npm run docs:check
npm run docs:build
npm run docs:dev
```

The site uses `/SECCA/` as its base and writes build output to `docs/.vitepress/dist`. Use the URL printed by the development server. The configuration follows [VitePress site configuration](https://vitepress.dev/reference/site-config).
