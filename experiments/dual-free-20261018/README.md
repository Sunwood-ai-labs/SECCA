# Two free-model CAD samples, 2026-10-18

DeepSeek V4.1 Flash Free scored **50/100**. Nemotron 3.5 Super VL Free scored
**28.75/100**. Each model ran once in an independent Podman sandbox.

| DeepSeek V4.1 Flash Free | Nemotron 3.5 Super VL Free |
| --- | --- |
| ![DeepSeek preview](deepseek/trial-01/renders/preview.png) | ![Nemotron preview](nemotron/trial-01/renders/preview.png) |
| FCStd and STEP valid, 26 solids each | FCStd valid, 30 solids; STEP imports zero shapes |

Read the [report](REPORT.md), [result JSON](RESULT.json), and
[export manifest](export-manifest.json) for conditions, scores, original hashes,
transformations, and omitted records.

Verify this public package from the repository root, without model inference:

```sh
uv run --frozen python experiments/tools/export_dual.py --verify experiments/dual-free-20261018
```

日本語要約：同じ画像と依頼文で各モデルを1回ずつ実行し、別々のPodman環境で生成した。
DeepSeekは50点で、FCStdとSTEPがともに有効だった。Nemotronは28.75点で、FCStdは
有効だがSTEPには形状がなかった。見た目の採点はCAD形式の検査と分けている。
今回の各1生成物の評価であり、モデル全体の性能順位ではない。
