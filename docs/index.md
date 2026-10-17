---
layout: home
hero:
  name: SECCA
  text: Can an agent construct the CAD it sees?
  tagline: Solid-model Evaluation of CAD Construction Agents. A fixed racing-kart task with saved geometry, controlled renders, and reviewable evidence.
  image:
    src: /secca-mark.svg
    alt: SECCA snow crystal and CAD cube
  actions:
    - theme: brand
      text: Run the fixed task
      link: /guide/getting-started
    - theme: alt
      text: Inspect the evidence
      link: /guide/results
features:
  - title: Fixed task
    details: One image and one prompt. Hashes identify the rubric, render settings, and protocol.
  - title: Saved geometry
    details: FCStd and STEP reopen in a separate offline container before fixed white-background renders.
  - title: Recorded review
    details: Three evidence-based reviews. The final score sums the median for each criterion.
---

<div class="experiment-card">
  <img src="/beam-preview.png" alt="Beam Free generated kart, rendered on white" width="960" height="600" />
  <div>
    <p class="experiment-label">Recorded experiment · 2026-10-17</p>
    <h2>Beam Free</h2>
    <p class="experiment-score">25 <small>/ 100</small></p>
    <p>One scored artifact. CAD generation succeeded; curved bodywork and mechanical detail remained limited.</p>
    <p><a href="./guide/results">Read the result and its limits →</a></p>
  </div>
</div>

## Evidence before comparison

SECCA preserves what the agent received, the runtime it used, the CAD it saved, and how reviewers scored the visible result. Valid CAD and visual likeness are separate outcomes.

<div class="evidence-flow">Fixed image + prompt → isolated generation → saved FCStd + STEP → offline inspection + white renders → three reviews → criterion medians</div>

Beam Free used Python to inspect image pixels through text output. The run does not measure native image-input capability. The older Windows-host GLM fixture is historical and cannot establish a strict comparison with this Podman run.

SECCA is also **雪華**, read **せっか** (sekka). Start with the [fixed protocol](./guide/protocol), or [read in Japanese](./ja/).
