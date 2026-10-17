# Contribute to SECCA

SECCA means **Solid-model Evaluation of CAD Construction Agents**. The Japanese name is 雪華, read せっか.

## Set up the checkout

Use Python 3.12 or newer, uv, and Node.js 24 for development. Podman is required only for container integration and model trials.

```sh
uv sync --frozen
uv run --frozen python -m unittest discover -s scripts -p 'test_*.py'
uv run --frozen python scripts/candidate.py verify-assets
uv run --frozen python scripts/scores.py verify-baseline
uv run --frozen python tools/check_publication.py
npm ci
npm run docs:build
```

Run the runtime integration check documented in the [execution guide](references/run.md) after a change to the container, MCP transport, security boundary, or postprocessing. Use an explicit named Podman connection. Do not run a paid model trial as an incidental test.

## Preserve the experiment contract

- Keep `assets/**` unchanged for the existing protocol. Its image, prompt, rubric, render settings, and historical baseline are hashbound. A changed task needs a new protocol and separate records.
- Never copy another trial, the rubric, baseline CAD, host configuration, or repository contents into a candidate sandbox. The container build context is an allowlist.
- Treat stored candidate outputs as untrusted data. Stop the candidate before collection and inspect or render only in a separate offline container.
- Record every trial, including refusals, provider errors, timeouts, and absent outputs. Do not replace them with invented scores.
- Score visual fidelity separately from CAD validity, execution time, token usage, and cost. Keep the coordinator-first and fresh-context judging procedure.
- Do not compare the historical Windows GLM sample with a Podman sample as a controlled model ranking.

## Send a change

Explain the concrete behavior, affected protocol, and checks in the pull request. Include failure evidence for a runtime fix and build evidence for a documentation change. Do not include API keys, host credentials, local trial volumes, container archives, dependency directories, or generated website output.

Adding public experiment data requires provenance, input hashes, exact runtime identity, original or explicitly transformed evidence, and a data-rights note. A request to contribute does not authorize reuse of a reference image whose rights are unknown.
