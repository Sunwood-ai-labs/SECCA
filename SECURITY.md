# Security policy

SECCA executes model-generated Python and CAD content. Its containment controls reduce file and network access; they are not a proof against kernel or container-runtime vulnerabilities. Use a dedicated Podman machine for adversarial trials and keep its runtime patched.

## Report a vulnerability

Use the repository's [private vulnerability reporting](https://github.com/Sunwood-ai-labs/SECCA/security/advisories/new) when available. Describe the affected commit, exact runtime identity, and a minimal reproduction without real credentials or unrelated host files. If the private form is unavailable, open an issue requesting a private contact without publishing exploit details or secrets.

## Boundaries to preserve

- The candidate and its FreeCAD process share one disposable, non-root container with no external network and no host-directory or management-socket mounts.
- An independent gateway allows only a fixed public HTTPS destination, selected model, and client-executed inference routes. Credentials are gateway-only.
- Artifact collection rejects links and unsafe archive members. Inspection and rendering run offline after the candidate stops.
- Existing cross-run and host-access probes are evidence for the tested runtime, not a guarantee for every platform.

CPU, memory, process, request, response, and artifact limits are enforced where implemented. Candidate stdout, host-side event queues, and persistent-volume disk growth are not fully quota-bounded. A runaway trial can still exhaust resources. The provider receives the model requests and tool results; local containment does not change provider retention rules.

The project is initially maintained on a best-effort basis. No response-time or supported-version guarantee is asserted.
