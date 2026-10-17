# はじめに

モデルAPIを呼ばずに、ローカルのSECCAと固定入力を確認します。

## 必要なもの

| ツール | 用途 |
| --- | --- |
| Python 3.12以降 | ホスト側の実行管理と根拠の処理 |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Pythonコマンドの実行 |
| 稼働中の名前付き接続を持つPodman | 隔離したLinuxコンテナの構築と実行 |
| Git | ソースの取得 |
| Node.js 22以降とnpm | ドキュメントを開発する場合 |

FreeCAD、OpenCode、FreeCAD MCPはコンテナ内で動かします。実験からホストのFreeCADへ接続しないでください。

## 取得したファイルを確認する

1. リポジトリを取得します。

   ```sh
   git clone https://github.com/Sunwood-ai-labs/SECCA.git
   cd SECCA
   ```

2. 固定資産を検査します。

   ```sh
   uv run --frozen python scripts/candidate.py verify-assets
   ```

   `assets/manifest.json` のSHA-256と照合します。不一致があれば、試行の前に原因を解消してください。入力の変更を隠すためにmanifestを作り直さないでください。

3. Podmanのマシンと名前付き接続を確認します。

   ```sh
   podman machine list
   podman system connection list
   podman --connection "<CONNECTION>" info
   ```

   `<CONNECTION>` を稼働中の接続名へ置き換えてください。接続を指定する各コマンドで同じ名前を使い、既定の接続は変更しません。Podmanが利用できない場合は試行を止め、ホスト実行へ切り替えないでください。

4. ランタイムをビルドします。

   ```sh
   uv run --frozen python scripts/candidate.py build --connection "<CONNECTION>" --tag localhost/kart-sbx-secca:v0.1.0
   ```

   実行ツールはタグの `localhost/kart-sbx-` 接頭辞を検査します。ビルドでは外部の依存先を取得しますが、モデルは呼びません。ソースとパッケージの情報を残し、試行ではタグをイメージIDへ解決します。

## 次に進む

[試行の実行](./run)へ進んでください。固定条件を先に確認する場合は[固定プロトコル](./protocol)を参照できます。推論には、選択モデルの利用を認められた提供元アカウントが必要です。

## ドキュメントをプレビューする

```sh
npm ci
npm run docs:check
npm run docs:build
npm run docs:dev
```

公開パスは `/SECCA/`、ビルド先は `docs/.vitepress/dist` です。開発サーバーが表示するURLを使ってください。設定は[VitePressのサイト設定](https://vitepress.dev/reference/site-config)に沿っています。
