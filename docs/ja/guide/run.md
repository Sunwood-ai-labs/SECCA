# 試行を実行する

[準備したランタイム](./getting-started)で、新しい候補の生成物を1件作ります。リポジトリのルートで実行し、山かっこのプレースホルダーは実行前に置き換えてください。

## 新しい試行を準備する

```sh
uv run --frozen python scripts/candidate.py prepare --trial "trials/my-model-001" --model "<provider/model-id>" --connection "<CONNECTION>" --image localhost/kart-sbx-secca:v0.1.0 --api-base-url "<HTTPS_PROVIDER_API_BASE_URL>"
```

利用を認められた提供元の公開HTTPS推論APIを指定してください。準備段階では、モデル、接続先、解決済みイメージID、入力ハッシュを記録します。モデルは呼びません。

APIへ送るモデル名がOpenCodeのモデルIDの後半と異なる場合は、`--api-model "<API_MODEL_ID>"` を追加します。ゲートウェイは記録した値を許可します。別モデルを自動選択する機能ではありません。

認証が必要なら、通常の秘密情報管理の手順で認証情報を設定し、`--credential-env PROVIDER_API_KEY` を追加してください。渡すのは環境変数の**名前**であり、値ではありません。キーはゲートウェイの一時Podman secretへ渡し、候補には渡しません。課金や自動チャージの既存設定は変えないでください。

## 1回実行する

```sh
uv run --frozen python scripts/candidate.py run --trial "trials/my-model-001"
```

選択した提供元を呼び、既存のアカウント設定に応じて費用が発生する場合があります。標準の試行上限は1,800秒です。生成時間にはモデル待ち、内部再試行、MCP処理を含み、準備と後からの検査・描画は含めません。

拒否、タイムアウト、API・ツールのエラーも試行記録へ残してください。形状の補修、品質改善の追加指示、モデルの切替は行いません。手動で再実行する場合は新しい試行フォルダを使います。ツール応答の外側が成功でも、本文にPython例外が含まれる場合があります。集計値だけでなくイベント本文も確認してください。

## 保存CADを検査・描画する

候補が停止した後に実行します。

```sh
uv run --frozen python scripts/cad_artifacts.py inspect --trial "trials/my-model-001"
uv run --frozen python scripts/cad_artifacts.py render --trial "trials/my-model-001"
```

検査と描画には、同じイメージIDの新しいコンテナを使います。外部通信も推論用ソケットも与えません。FCStdの再オープンとSTEPの再インポートを行い、検査記録を保存します。描画はコピーを使い、元CADを保存し直しません。

`evidence/run.json`、`evidence/validation.json`、`evidence/render.json`、`renders/` を確認してください。元CADのハッシュが変わっていないことを確認し、[採点](./scoring)へ進みます。出力なし、描画失敗、評価資料不足は採点不能です。

## 同梱カタログにないモデルを追加する

提供元が公開するモデル情報をJSONへ保存し、`prepare` に `--model-metadata "<FILE>"` を渡してください。取得元URLとカタログ原本のSHA-256を記録します。旧イメージにない対応を追加した場合は、ランタイムを再ビルドします。

JSONの構造とフィールドの制約は[実行リファレンス](https://github.com/Sunwood-ai-labs/SECCA/blob/main/references/run.md)に記載しています。添付対応と入力形式は公開情報のまま保ってください。テキスト入力のみとされるモデルで画像入力を有効にしてはいけません。元画像を作業ファイルとして渡しても、ネイティブな画像対応を示したことにはなりません。

## ランタイムを保存する

```sh
podman --connection "<CONNECTION>" save --format oci-archive --output "runtime.oci.tar" "<IMAGE_ID>"
podman --connection "<CONNECTION>" load --input "runtime.oci.tar"
```

リポジトリに含まれるのは構築手順であり、OCIイメージ本体ではありません。再ビルドは外部パッケージの取得可否に依存します。解決済みランタイムの保存には、可変タグよりイメージアーカイブが適しています。
