# Podmanで同じ入力を実行する

リポジトリのルートで実行する。`TRIAL` は新規フォルダ、`CONNECTION` は稼働中の名前付きPodman接続を表す。接続の既定値は変更しない。

ホスト側にはPython 3.12以降、uv、Podmanを用意し、`uv sync --frozen` で開発用依存関係を取得する。FreeCADとOpenCodeはコンテナに含めるため、ホストへのインストールは不要。

## ランタイムを用意する

```text
podman machine list
podman system connection list
uv run --frozen python scripts/candidate.py build --connection "<CONNECTION>" --tag localhost/kart-sbx-secca:v0.1.0
```

ビルド時は固定のベースイメージ、OpenCode 1.19.3、FreeCADとMCPソースを使う。依存パッケージとソースのハッシュを残し、実験では可変タグを解決したイメージIDを固定する。採点資料や基準CADをビルドコンテキストへ入れない。

MCPソースは同梱している。更新用の外部ソースを使う場合だけ `--mcp-source` を指定し、条件差として扱う。ベースイメージや依存パッケージの取得には通信が必要。

別PCへ完全に同じランタイムを移す場合は、`podman --connection "<CONNECTION>" save --format oci-archive --output "<runtime.oci.tar>" "<IMAGE>"` で保存し、移転先で `podman --connection "<CONNECTION>" load --input "<runtime.oci.tar>"` を使う。スキルのZIPにはランタイムイメージ本体を含めない。

## 準備・生成する

```text
uv run --frozen python scripts/candidate.py verify-assets
uv run --frozen python scripts/candidate.py prepare --trial "<TRIAL>" --model "<provider/model-id>" --connection "<CONNECTION>" --image localhost/kart-sbx-secca:v0.1.0 --api-base-url "<HTTPS provider API base URL>"
uv run --frozen python scripts/candidate.py run --trial "<TRIAL>"
```

API接続先は提供側の正規の推論APIを指定する。ゲートウェイの接続先として固定し、候補のOpenCodeはローカルの中継先を使う。現在の中継対象はOpenAI互換のchat/responsesとAnthropicのmessages形式。対応しないAPIをホスト経由へ切り替えない。

モデルIDの後半とOpenCodeが送るAPI側のモデル名が異なる場合だけ、ゲートウェイが許可する値を `--api-model` で明示して記録する。これは送信モデルの自動置換ではない。

認証が必要なら、利用を認められた環境変数名を `--credential-env NAME` で指定する。値を引数やファイルに書かない。キーはゲートウェイの一時Podman secretへ渡し、候補には渡さない。課金設定や自動チャージを実験のために変更しない。

候補は新しい作業領域・ホーム・FreeCAD文書を持つ。ホストの設定、認証ファイル、AGENTS、他モデルの成果物、過去セッションをコピーしない。接続準備は生成時間に含めない。試行上限は30分。

API拒否、タイムアウト、FreeCAD実行エラーも原記録に残す。FreeCADのツール呼出は外側が成功でも本文にPython実行失敗が含まれる場合がある。モデルを途中で切り替えたり、親が形状を補修したりしない。

### 同梱カタログにないモデルを指定する

OpenCode 1.19.3の同梱カタログにモデルがない場合は、提供元の公式カタログから取得した情報をJSONファイルへ保存し、`prepare` に `--model-metadata "<FILE>"` を追加する。この機能を含むスキルからランタイムを再ビルドし、新しいイメージIDを記録する。既存イメージの内容は更新されない。

JSONの構造は次のとおり。`model` には公式カタログの該当モデル情報をそのまま入れる。例のSHA-256は、取得したカタログ原本のSHA-256へ置き換える。

```json
{
  "provider_id": "opencode",
  "provider_api": "https://opencode.ai/inference/openai/v1",
  "provider_npm": "@ai-sdk/openai-compatible",
  "model": {
    "id": "beam-free",
    "name": "Beam Free",
    "attachment": false,
    "modalities": {"input": ["text"], "output": ["text"]}
  },
  "source_url": "https://models.dev/api.json",
  "source_sha256": "<64桁の小文字16進数>"
}
```

`provider_id` は `--model` の前半、`model.id` は後半とAPIへ送るモデルIDの両方に一致させる。`--api-model` を併用する場合も、この一致が必要。`provider_api` は `--api-base-url` と一致させる。`provider_npm` は取得元の情報として保存するが、候補のSDK設定を上書きしない。

準備時にJSON全体を `runtime-input/model-metadata.json` へコピーし、そのファイルのSHA-256を `trial.json` の `file_hashes` に記録する。取得元URLと原本のSHA-256、同梱カタログへの追加という条件差も記録する。実行前にファイルのハッシュとモデルの識別情報を照合する。

候補の設定へ渡すのは、OpenCodeが扱うモデル属性だけ。添付対応や入出力形式を公式情報のまま保ち、プロバイダーの接続先や任意のオプションをJSONから上書きしない。候補のAPI接続先はローカルの中継先を維持する。

公式情報で画像入力が非対応なら、`attachment` を `true` に変えたり、`modalities.input` に `image` を追加したりしない。固定の参照画像とプロンプトは変更しない。画像非対応による拒否やエラーを原記録に残し、CADが生成されなければ未生成として記録して採点しない。

## 別コンテナで検査・描画する

```text
uv run --frozen python scripts/cad_artifacts.py inspect --trial "<TRIAL>"
uv run --frozen python scripts/cad_artifacts.py render --trial "<TRIAL>"
```

候補の停止を確認してから、同じイメージIDの別コンテナで保存CADを検査・描画する。後処理コンテナには外部通信もAPIソケットも与えない。ホストのFreeCADcmdやMCPへ接続する旧手順は使わない。

画像は `renders`、カメラ条件とハッシュは `evidence/render.json` に残る。グループの集約ShapeやSTEPの補助図形を二重計上しない。元CADのハッシュが変わった場合は成功としない。

追加画像は標準画像を残して別条件として記録する。標準画像のために形状を回転・移動しない。環境間でFreeCAD、Qt、GPUが違う場合、PNGのバイト一致までは保証しない。

## 比較を継続する

Podman/Linux版はプロトコルv2。Windowsホスト版の43点は歴史的な参考結果であり、隔離済みの基準試行ではない。厳密なモデル比較では、同じイメージIDと評価者設定で基準モデルも再実行・再評価する。

モデル推論を行わない実ランタイムの検査と、再ビルドの制約は [ランタイム検証](runtime.md) を参照する。
