---
name: secca
description: Run and score SECCA's fixed image-conditioned racing-kart CAD task in isolated Podman runtimes with FreeCAD MCP. Preserve the protocol, candidate isolation, saved CAD, white renders, and evidence-based reviews.
---

# SECCA

SECCA is **Solid-model Evaluation of CAD Construction Agents**. 日本語の呼び名は「雪華（せっか）」。

このスキルは実験を管理する側で使う。生成モデルにはスキル本文、採点基準、過去のCADを渡さない。

固定条件は [assets/protocol.json](assets/protocol.json)。候補への入力は [参照画像](assets/reference.jpg) と [依頼文](assets/prompt.txt) のみ。

> 添付画像のレーシングカートをFreeCAD MCPで作成し、racing-kart.FCStdとracing-kart.stepに保存してください。

## 実行する

1. リポジトリのルートで `uv sync --frozen` を実行する。[実行手順](references/run.md)でPodmanの稼働中の名前付き接続と専用ランタイムイメージを確認する。OpenCodeとFreeCAD MCPの両方をコンテナ内で動かす。ホストのFreeCADには接続しない。
2. `candidate.py prepare` で新しい実験を用意する。モデルID、API接続先、イメージIDを固定する。生成側へ渡すのは元画像、依頼文、選択モデルの実行設定だけ。
3. `candidate.py run` で試行専用コンテナを起動し、1回実行する。コンテナのネットワークは `none`。モデルAPIへの通信は専用Unixソケット経由のゲートウェイに限定する。[隔離条件](references/sandbox.md)を満たさなければ実行しない。
4. 候補コンテナを停止してから、`cad_artifacts.py inspect` と `render` を実行する。検査と描画にも別の通信できないコンテナを使う。保存CADのコピーから[固定描画条件](assets/render-spec.json)で白背景画像を作る。元CADは保存し直さない。
5. `scores.py packet` で評価資料を分離する。コーディネータの先行採点1件と、履歴を引き継がない独立評価2件を保存し、`scores.py aggregate` で集計する。評価前に [採点手順](references/scoring.md) を読む。

## 比較条件を守る

- 入力、配点、描画条件のSHA-256を検証する。変更が必要なら別プロトコルとして記録し、同条件の結果へ混ぜない。
- ホストのホーム、スキル全体、基準CAD、他試行、採点資料、管理用ソケットを候補へマウントしない。試行間で作業フォルダ、ホーム、FreeCAD文書、APIソケットを共有しない。
- ホストの `HOME`、`USERPROFILE`、`CODEX_HOME` を変更しない。APIキーは明示した環境変数からゲートウェイの一時secretへ渡す。候補へキーを渡したり、値を記録したりしない。無料モデルから有料モデルへ自動切替しない。
- 形状を手直ししたり、品質改善の追加指示を送ったりしない。内部の自動再試行は記録し、手動の再実行は別試行に分ける。
- Podmanが使えなくてもホスト実行へ切り替えない。API接続先やモデルの自動変更も行わない。
- CADの成立、ソリッド数、時間、費用は再現度の点数へ加算しない。
- 出力なし、描画失敗、評価資料不足は状態と根拠を残して採点不能とする。未実行の結果や架空の点数で埋めない。

## 結果を渡す

モデルID、試行数、入力、実行時間の範囲、エラー、CAD検査、白背景画像、項目別点数、採点者の条件を記録する。生成時間にはモデルの待ち時間と内部再試行を含め、準備と後処理を含めない。

最終回答は点数と生成画像を先に示し、根拠、CADファイル、記録へのリンクを添える。1生成物の目視採点をモデル全体の性能点として扱わない。

## 基準例と検査

- [基準結果](references/baseline.md)と `assets/baseline` に、GLMの1試行と43点の原記録を保存している。旧試行はWindowsホスト実行であり、Podman版の結果ではない。厳密な比較には隔離環境での再生成が必要。
- `candidate.py verify-assets` で固定資産を検査する。
- `scores.py verify-baseline` で43点を再計算する。
- スクリプトのテストや基準CADの再描画を、新モデルの実行成功として数えない。

各スクリプトは `uv run --frozen python scripts/<名前>.py` で実行する。軽量テストと、推論なしでFreeCAD MCP・保存CAD・STEP・白背景PNGを確認するコマンドは [ランタイム検証](references/runtime.md) を読む。
