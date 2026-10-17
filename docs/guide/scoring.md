# Score a result

Use the canonical [`assets/rubric.json`](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/rubric.json). Scoring measures visible resemblance, not CAD validity or mechanical function.

## Criteria and anchors

| Criterion | Maximum | Visible evidence |
| --- | ---: | --- |
| Silhouette and proportions | 25 | Low overall form, visible wheel-to-body proportions |
| Component layout | 20 | Wheels, seat, steering wheel, engine, bodywork, and their placement |
| Characteristic geometry | 30 | Bucket seat, nose, bumpers, tires, rims, bent frame |
| Mechanical detail | 20 | Steering mechanism, engine, exhaust, drive, brake features |
| Color and material regions | 5 | Correspondence of frame, body, seat, and tire color regions |

Anchors are 0% for missing or unrelated forms, 25% for rough substitutes with large differences, 50% for approximation with substantial differences, 75% for local differences, and 100% for close correspondence within the observable views. Apply each anchor to that criterion's maximum and give concrete visual reasons.

## Create a neutral review packet

```sh
uv run --frozen python scripts/scores.py packet --trial "trials/my-model-001" --output "reviews/candidate-a"
```

Give independent reviewers the packet's images, rubric, and review template. Withhold the model name, previous scores, execution logs, and other reviewers' scores. Each reviewer must see the reference and the three generated canonical views.

## Collect three reviews

1. Save the coordinator's initial review before reading the other reviews. Record that the coordinator knows the model identity.
2. Start two independent reviewers in fresh contexts. For Codex agents, use `fork_turns="none"`. Inherited conversation history does not count as model-blinded review.
3. Record each criterion score and visible evidence. A nonzero score needs evidence for credit. A score below full marks needs evidence for deductions.
4. Preserve `context_provenance`, including the statement, other reviews read, timezone-qualified timestamp, and signer. Verify the actual launch method, materials, and images rather than rely on a blinded-context self-claim.
5. Record the evaluator model separately from the generation model. If its actual model ID is unavailable, record it as unknown.

Use the [reviewer prompt](https://github.com/Sunwood-ai-labs/SECCA/blob/main/references/reviewer-prompt.txt). Evidence entries contain `kind` and a concrete `observation`.

## Aggregate criterion medians

```sh
uv run --frozen python scripts/scores.py aggregate --trial "trials/my-model-001" --reviews "reviews/coordinator.json" "reviews/blind-a.json" "reviews/blind-b.json"
```

For each criterion, take the median of the three scores. Sum those five medians. Do not average totals or take the median of total scores. In the Beam experiment, the criterion medians are `9 + 9 + 4 + 2 + 1 = 25`.

Preserve all three reviews, their conditions, the aggregation method, the number of attempts, and the number of scored outputs. Do not infer exact dimensions, hidden connections, or manufacturing fitness from the rendered views. A visual review is not an automatic image-similarity metric.

## Excluded outcomes

Format export, BRep validity, solid count, generation time, and recorded cost do not add likeness points. Report them separately. An attempt with no output, failed rendering, or insufficient review material is unscorable and retains its failure status.
