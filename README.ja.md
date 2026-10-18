<p align="center"><img src="brand/secca-header.svg" alt="SECCA · 雪華。Solid-model Evaluation of CAD Construction Agents。" width="900"></p>

<p align="center"><a href="README.md">English</a> · <strong>日本語</strong></p>

<p align="center">
  <a href="https://github.com/Sunwood-ai-labs/SECCA/actions/workflows/ci.yml"><img src="https://github.com/Sunwood-ai-labs/SECCA/actions/workflows/ci.yml/badge.svg" alt="CIの状態"></a>
  <a href="https://github.com/Sunwood-ai-labs/SECCA/actions/workflows/pages.yml"><img src="https://github.com/Sunwood-ai-labs/SECCA/actions/workflows/pages.yml/badge.svg" alt="ドキュメント公開の状態"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/code-MIT-087f8c" alt="コードのライセンスはMIT"></a>
  <img src="https://img.shields.io/badge/runtime-Podman-123b4a" alt="Podmanランタイム">
</p>

SECCAは、固定のレーシングカート画像と依頼文から、CAD構築エージェントがFreeCAD・STEPファイルを作る過程を評価するプロジェクトです。固定プロトコル、隔離実行ツール、白背景の描画画像、採点根拠を保存します。正式名は **Solid-model Evaluation of CAD Construction Agents**。日本語名は **雪華（せっか）** です。

[ドキュメント](https://sunwood-ai-labs.github.io/SECCA/ja/) · [試行の実行](docs/ja/guide/run.md) · [結果と限界](docs/ja/guide/results.md) · [プロトコル](assets/protocol.json)

## ❄️ 固定課題と確認できる根拠

- 候補へ渡すのは、元画像と固定の日本語依頼文です。
- OpenCode、FreeCAD、FreeCAD MCPを新しいPodmanコンテナで動かします。ホストのCAD、他試行、採点資料は渡しません。
- 保存CADを別の通信できないコンテナで開き、固定の斜視・上面・右面を白背景で描画します。
- モデル名を知るコーディネータ1件と、新しいコンテキストでモデル名を伏せた独立評価2件を保存します。項目ごとの中央値を合計します。

現在の課題は見た目の再現を評価する実験です。正確な寸法、機械としての動作、製造適性、モデル全体の性能を示すものではありません。

## 🧪 公開実験

### 保存された4生成物を比較する

保存された各1生成物を、画像・得点・CAD検査で見比べられます。

| モデル・採点根拠 | 点数 | 実行条件 |
| --- | ---: | --- |
| [GLM 5.3 Flash Free](assets/baseline/likeness-score.json) | **43/100点** | Windows・非隔離 |
| [Beam Free](experiments/beam-free-20261017/trial-02/score.json) | **25/100点** | Podman B・Python画素解析 |
| [Nemotron 3.5 Super VL Free](experiments/dual-free-20261018/nemotron/trial-01/score.json) | **28.75/100点** | 独立したPodman A・画像添付 |
| [DeepSeek V4.1 Flash Free](experiments/dual-free-20261018/deepseek/trial-01/score.json) | **50/100点** | 独立したPodman A・画像添付 |

入力した参照画像。

![入力したレーシングカートの参照画像](assets/reference.jpg)

| GLM 5.3 Flash Free · 43/100点 | Beam Free · 25/100点 |
| --- | --- |
| ![GLM 5.3 Flash Free](experiments/reference-view-20261018/renders/glm-preview.png) | ![Beam Free](experiments/reference-view-20261018/renders/beam-preview.png) |
| **Nemotron 3.5 Super VL Free · 28.75/100点** | **DeepSeek V4.1 Flash Free · 50/100点** |
| ![Nemotron 3.5 Super VL Free](experiments/reference-view-20261018/renders/nemotron-preview.png) | ![DeepSeek V4.1 Flash Free](experiments/reference-view-20261018/renders/deepseek-preview.png) |

上の4画像は、参照に近い前方3/4の視点へカメラだけを調整した追加描画です。参照画像のカメラ数値は不明で、厳密な一致ではありません。表示した点数は元の採点画像による既存評価のままで、追加画像では再採点していません。

| モデル | FCStd | STEP | 生成時間 |
| --- | --- | --- | ---: |
| GLM | 77有効ソリッド | 77有効ソリッド | 509.969秒 |
| Beam | 33有効ソリッド | 33有効ソリッド | 152.219秒 |
| Nemotron | 30有効ソリッド | 形状なし | 71.464秒 |
| DeepSeek | 26有効ソリッド | 26有効ソリッド | 442.688秒 |

| 項目・配点 | GLM | Beam | Nemotron | DeepSeek |
| --- | ---: | ---: | ---: | ---: |
| 輪郭・比率 /25 | 13 | 9 | 6.25 | 12.5 |
| 部品の配置 /20 | 13 | 9 | 5 | 15 |
| 特徴的な形状 /30 | 8 | 4 | 7.5 | 7.5 |
| 機械的な細部 /20 | 4 | 2 | 5 | 10 |
| 配色 /5 | 5 | 1 | 5 | 5 |
| 項目別中央値の合計 /100 | **43** | **25** | **28.75** | **50** |

各モデルの保存された1生成物を並べた参考比較です。Podman Aの2候補はFreeCAD 1.0.0を含む同じ固定イメージ、Bは別のイメージを使いました。Beamはネイティブな画像入力を使っていません。GLMはFreeCAD 1.1.3で、配点を生成後、数値採点前に作成しています。後のPodman試行では生成前から配点を固定しました。GLM・Nemotron・DeepSeekは各1生成です。Beamは2試行のうち1件を採点しました。

以前の比較画像は世界座標に対してカメラを固定し、モデルごとに異なる車体の前方向を補正していませんでした。GLMは+Y、BeamとDeepSeekは+X、Nemotronは−Xが前方なので、同じ世界座標のカメラでも車体を見る向きが変わります。追加描画では車体の前方向に合わせ、前方左45°・仰角約35.264°から見ています。CADの形状や配置は変えていません。

追加の4画像はすべてFreeCAD 1.0.0を含む同じ`sha256:b9e296032f921c96de5843b19e1a182ce5067d6cdca25a5d3ab7e7da23fe89cb`イメージで描画しました。これは表示用の追加処理であり、過去の生成環境を変更したり、標準の描画条件やプロトコルを置き換えたりしたものではありません。元CAD、元の採点画像、点数は維持しています。見た目の点数とCADの成立は別の評価です。条件の異なる各1回の記録から、モデル全体の順位や速度の優劣は示していません。

[追加描画・カメラ設定の記録](experiments/reference-view-20261018/README.md) · 元の採点斜視画像: [GLM](assets/baseline/evidence/kart-front-isometric-white.png) · [Beam](experiments/beam-free-20261017/trial-02/renders/isometric.png) · [Nemotron](experiments/dual-free-20261018/nemotron/trial-01/renders/isometric.png) · [DeepSeek](experiments/dual-free-20261018/deepseek/trial-01/renders/isometric.png)

### Nemotron・DeepSeek · 2026-10-18

同じ固定入力とランタイムイメージを使い、モデルごとに独立したPodman環境で1生成物ずつ作りました。各生成物をコーディネータ1件と、新しいコンテキストでモデル名を伏せた独立評価2件で採点し、項目別中央値を合計しています。CADの成立は再現度とは別に判定し、Nemotronは空のSTEPにより出力一式の検査に不合格でした。

この2生成物の結果から、モデル全体の順位や速度の優劣は示していません。CAD本試行の推論リクエスト本文は保存しておらず、画像ペイロードを通信記録と照合することはできません。OpenCodeの記録費用は各0ドルですが、請求明細は独立監査していません。過去のBeamとWindows版GLMはランタイムが異なるため、別の記録として扱います。

[実験ファイルと根拠](experiments/dual-free-20261018/README.md) · [結果と採点理由](docs/ja/guide/results.md)

### Beam Free · 2026-10-17

| 実験 | 結果 | 対象 |
| --- | --- | --- |
| Beam Free、2026-10-17 | 1生成物の評価は **25/100点** | 2試行のうち1件を採点。初回は準備段階でHTTP 403。 |

採点した試行の生成時間は152.219秒、OpenCodeの記録費用は0ドルでした。費用はクライアントの記録値で、請求明細を監査した値ではありません。保存したFCStdとSTEPは再オープンでき、各33ソリッド、無効形状0でした。CADの成立は再現度の点数へ加算しません。

Beam Freeのカタログは入力をテキストのみとしています。エージェント自身がPythonで参照画像の画素を調べました。今回は**ネイティブな画像入力機能の実測ではありません**。旧GLMの43点はWindowsホスト版であり、今回の隔離実行との厳密な比較には使えません。

[実験レポート](experiments/beam-free-20261017/REPORT.md) · [採点](experiments/beam-free-20261017/trial-02/score.json) · [CAD検査](experiments/beam-free-20261017/trial-02/evidence/validation.json)

### GLM 5.3 Flash Free · 2026-10-17、旧基準例

`opencode/glm-5.3-flash-free` は、WindowsホストのOpenCode 1.19.3とFreeCAD 1.1.3で1生成物を作りました。再現度は**43/100点**で、保存した両形式は各77有効ソリッド、外形も一致しています。生成時間は509.969秒でした。平板のシート、簡略化されたノーズとバンパー、ハンドルの向き、機械細部の不足が減点につながっています。

配点は生成後、数値採点前に作成しました。先行評価45点と、新しいコンテキストでモデル名を伏せた独立評価42・42点から、項目別中央値を合計した結果が43点です。評価者は同じアシスタントモデル系統でした。OS隔離のないホスト実行の過去の記録です。採点画像のカメラ設定も後の固定描画方式とは異なるため、条件差を含む参考比較として扱います。

[基準例の記録](references/baseline.md) · [採点](assets/baseline/likeness-score.json) · [CAD検査](assets/baseline/evidence/geometry-validation.json) · [FCStd](assets/baseline/workspace/racing-kart.FCStd) · [STEP](assets/baseline/workspace/racing-kart.step) · [採点した斜視画像](assets/baseline/evidence/kart-front-isometric-white.png)

## 🚀 はじめに

Python 3.12以降、[uv](https://docs.astral.sh/uv/)、稼働中の**名前付き接続**を持つPodmanが必要です。ホストへのFreeCAD・OpenCodeのインストールは不要です。コマンドはリポジトリのルートで実行してください。

1. リポジトリを取得し、固定資産を検査します。この段階ではモデルAPIを呼びません。

   ```sh
   git clone https://github.com/Sunwood-ai-labs/SECCA.git
   cd SECCA
   uv run --frozen python scripts/candidate.py verify-assets
   ```

2. Podmanのマシンと接続を確認し、ランタイムをビルドします。`<CONNECTION>` は稼働中の接続名へ置き換えてください。実行ツールはタグの `localhost/kart-sbx-` 接頭辞を必須としています。

   ```sh
   podman machine list
   podman system connection list
   uv run --frozen python scripts/candidate.py build --connection "<CONNECTION>" --tag localhost/kart-sbx-secca:v0.1.0
   ```

3. [試行の実行手順](docs/ja/guide/run.md)に沿って、利用を認められた提供元とモデルを選び、新しい試行を準備・実行・回収します。実行時は提供元APIを呼び、既存のアカウント設定に応じて費用が発生する場合があります。

コンテナの構築手順はバージョンと解決済みイメージIDを記録します。依存先を将来も完全に同じ状態で再取得できる保証はありません。別のマシンでも同じランタイムを使う場合は、OCIイメージを保存してください。

## 📐 採点と比較

| 項目 | 配点 |
| --- | ---: |
| 輪郭・比率 | 25 |
| 部品の配置 | 20 |
| 特徴的な形状 | 30 |
| 機械的な細部 | 20 |
| 配色 | 5 |

評価者は参照画像と標準の3方向画像を確認し、各点数に見える部位の根拠を添えます。時間、費用、書き出しの成功、ソリッド数、未確認の寸法は加点しません。失敗や採点不能は状態を残し、架空の点数で補いません。[採点手順](docs/ja/guide/scoring.md)を参照してください。

依頼文、参照画像、ツールのバージョン、ランタイム、描画条件、配点が変われば比較条件も変わります。差分を記録し、厳密な比較では同じ条件で基準モデルも再実行してください。このリポジトリはモデルの順位表を確立していません。

## 🗂️ リポジトリ構成

| パス | 内容 |
| --- | --- |
| `assets/` | 固定の依頼文・画像・プロトコル・配点・描画条件、旧基準例 |
| `scripts/`、`container/` | 試行実行、API中継、CAD検査、採点、同梱MCP |
| `references/` | 詳細手順と検証原記録 |
| `experiments/` | 公開実験のレポートと成果物 |
| `docs/`、`brand/` | 日英ドキュメントとオリジナルSVGロゴ |

## 🛠️ 開発と検証

```sh
uv run --frozen python -m unittest discover -s scripts -p "test_*.py"
uv run --frozen python scripts/candidate.py verify-assets
npm ci
npm run docs:check
npm run docs:build
npm run docs:dev
```

ビルド先は `docs/.vitepress/dist`、公開パスは `/SECCA/` です。プレビューはVitePressが表示するURLを使います。単体テスト、ランタイムの起動確認、保存CADの再検査は、新しいモデルによる生成とは区別します。[隔離と検証の限界](docs/ja/guide/isolation.md)を参照してください。

## 📄 権利と来歴

[MITライセンス](LICENSE)は、記載された範囲のプロジェクトコードとオリジナルロゴに適用されます。同梱FreeCAD MCPには[独自のMITライセンス](container/vendor/freecad-mcp/LICENSE)があります。参照画像はユーザー提供のスクリーンショットで、元の出典・作者・ライセンスは記録されていません。**コードのライセンスから、画像の利用・再配布許諾を推定しないでください。** 生成CADや描画画像も、描かれたデザインの権利を確定するものではありません。[来歴と権利](docs/ja/guide/provenance.md)、[データ来歴](NOTICE.md)に記載しています。

[貢献方法](CONTRIBUTING.md) · [セキュリティ](SECURITY.md) · [引用情報](CITATION.cff)
