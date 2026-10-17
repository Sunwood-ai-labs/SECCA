# Isolation

SECCA runs the agent, FreeCAD GUI, and FreeCAD MCP together in a per-trial container. Containerizing only the agent would leave host access possible through FreeCAD's arbitrary Python execution.

## Candidate boundary

| Control | Configuration |
| --- | --- |
| Network | `none` |
| User | UID 10000 |
| Root filesystem | Read-only |
| Linux capabilities | All dropped |
| Privilege escalation | `no-new-privileges` |
| Host bind mounts | None |
| Published ports and management sockets | None |
| State | Fresh workspace, home, FreeCAD document, and API socket per trial |

Only the original image and selected execution inputs are copied into the candidate. Prior CAD, scoring material, host configuration, and other trials remain outside it. Runtime construction includes generic boot code and MCP sources, not judging assets.

## API transport

The candidate sends loopback HTTP to an adapter. The adapter connects to a private per-trial Unix socket. A separate gateway permits inference POST requests for the recorded model at one fixed public HTTPS provider endpoint.

The gateway rejects arbitrary destinations, CONNECT, redirects, private IPs, other models, provider history or file references, and web search. A read-only mount of the socket volume still permits socket connections, so request validation occurs at the gateway. API credentials belong to the gateway, not the candidate.

## Postprocessing boundary

The runner stops the candidate before it collects CAD. Inspection and rendering run in a fresh `network none` container without the inference socket. Both source hashes and result hashes are recorded. Source CAD is not resaved after presentation changes.

## Verification and limits

The repository preserves an earlier 2026-10-17 [runtime verification snapshot](https://github.com/Sunwood-ai-labs/SECCA/blob/main/references/verified-runtime.json) and its evidence. That snapshot tested 19 isolation checks, Linux Unix-socket behavior, runtime startup, offline CAD replay, and a failure path **without new model inference**. Its image ID belongs to that recorded snapshot, not every later runtime build.

The [current runtime verification instructions](https://github.com/Sunwood-ai-labs/SECCA/blob/main/references/runtime.md) describe source checks, unit tests, and real FreeCAD replay. The [public-release verification record](https://github.com/Sunwood-ai-labs/SECCA/blob/main/references/release-verification.json) identifies the tested release image. Preserve the actual image ID and verification report for the image you use. The Beam experiment separately records a real provider run.

These checks establish observed behavior under recorded conditions. They are not a proof against every escape or availability attack. Candidate stdout, queues, logs, and volume disk consumption do not have a complete tested quota boundary. Do not describe the environment as absolutely secure.
