# 実験結果

## 保存された4生成物の参考比較

保存された各1生成物を、画像・得点・CAD検査で見比べられます。

| モデル・採点根拠 | 点数 | 実行条件 |
| --- | ---: | --- |
| [GLM 5.3 Flash Free](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/baseline/likeness-score.json) | **43/100点** | Windows・非隔離 |
| [Beam Free](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/trial-02/score.json) | **25/100点** | Podman B・Python画素解析 |
| [Nemotron 3.5 Super VL Free](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/nemotron/trial-01/score.json) | **28.75/100点** | 独立したPodman A・画像添付 |
| [DeepSeek V4.1 Flash Free](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/deepseek/trial-01/score.json) | **50/100点** | 独立したPodman A・画像添付 |

入力した参照画像。

![入力したレーシングカートの参照画像](/reference-input.jpg)

| GLM 5.3 Flash Free · 43/100点 | Beam Free · 25/100点 |
| --- | --- |
| ![GLM 5.3 Flash Free](/glm-reference-view.png) | ![Beam Free](/beam-reference-view.png) |
| **Nemotron 3.5 Super VL Free · 28.75/100点** | **DeepSeek V4.1 Flash Free · 50/100点** |
| ![Nemotron 3.5 Super VL Free](/nemotron-reference-view.png) | ![DeepSeek V4.1 Flash Free](/deepseek-reference-view.png) |

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

[追加描画・カメラ設定の記録](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/reference-view-20261018/README.md) · 元の採点斜視画像: [GLM](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/baseline/evidence/kart-front-isometric-white.png) · [Beam](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/trial-02/renders/isometric.png) · [Nemotron](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/nemotron/trial-01/renders/isometric.png) · [DeepSeek](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/deepseek/trial-01/renders/isometric.png)

## Nemotron・DeepSeek · 2026-10-18

固定の画像と日本語依頼文で、各モデルを1回ずつ実行しました。別々のコンテナ、FreeCAD文書、作業領域、ホーム、通信用ボリュームを用意し、実行状態を共有していません。他の生成物や採点資料は候補へ渡していません。両方ともFreeCAD 1.0.0とOpenCode 1.19.3を含む、同じイメージを使用しました。

```text
sha256:b9e296032f921c96de5843b19e1a182ce5067d6cdca25a5d3ab7e7da23fe89cb
```

モデルIDは `opencode/nemotron-3.5-super-vl-free` と `opencode/deepseek-v4.1-flash-free`、ソースのリビジョンは `dc7b1273fcdd1534b903185e2d7921cb7e7784f5` です。管理側による形状の修復や、再生成の指示は行っていません。

### 2生成物の採点根拠

Nemotronは直線のフレーム材、平たい車輪、箱状の座席や外装を作りましたが、部品が離れており、参照のつながった輪郭とは異なります。DeepSeekは四輪、フレーム、シート、ハンドル、外装、エンジンを車体としてまとめています。ただし前部の大きな箱、角張った座席、単純なリム、エンジンや駆動部には参照との差が残ります。

各生成物について、モデル名を知るコーディネータが先に採点を保存し、その後、新しいコンテキストでモデル名を伏せた独立評価者2人が別々の資料を確認しました。全評価者が参照画像と、固定の斜視・上面・右面画像を見ています。コーディネータと独立評価2件の総点は、Nemotronが33.75・23.75・28.75点、DeepSeekが50・48.75・45点でした。最終点は**項目別中央値の合計**です。DeepSeekの総点の中央値48.75点は、規定の集計結果ではありません。評価者の実モデルIDは取得できず、不明として記録しています。

### CAD検査と計測の限界

候補の終了後、別の通信できないコンテナで保存CADを開き直しました。NemotronのFCStdには30有効ソリッドがありますが、1,640バイトのSTEPには読み込める形状がなく、CAD出力一式の検査は不合格です。DeepSeekは両形式とも26有効ソリッドで、外形も0.01mmの許容差内で一致しました。検査・描画前後で元CADのハッシュは変わっていません。形式の成立、時間、費用、ソリッド数は見た目の点数に加えていません。

生成時間は生成開始からOpenCode終了までで、モデル待ち、自律的な再試行、MCP処理を含みます。準備や後からの検査・描画は含めません。並行実行した各1回の記録から、速度の優劣や反復時のばらつきは示せません。OpenCodeの記録費用は両方0ドルですが、請求明細は独立監査していません。API要求はNemotronが8件、DeepSeekが26件で、すべてHTTP 200でした。レート上限を探る負荷試験ではありません。イベント監査ではNemotronにシェル呼出の失敗1件、DeepSeekにツール失敗4件があり、完了扱いの応答本文に含まれるエラーも数えています。

CAD本試行の推論リクエスト本文は保存していません。固定入力のハッシュ、添付コマンド、画像対応のモデル情報は記録していますが、本試行で画像ペイロードが実際に送られたかを通信記録と照合することはできません。別途実施した画像入力検証は別の証拠であり、この不足を埋めるものではありません。点数は各モデルの1生成物に対する評価で、寸法精度、機械としての動作、製造適性、モデル全体の性能は示しません。過去のBeamとWindows版GLMはランタイムが異なり、今回の対照群としては扱っていません。

[実験ファイルと来歴](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/README.md) · [構造化した結果](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/RESULT.json) · [Nemotronの採点](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/nemotron/trial-01/score.json) · [DeepSeekの採点](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/dual-free-20261018/deepseek/trial-01/score.json)

## Beam Free · 2026-10-17

| 項目 | 記録値 |
| --- | --- |
| OpenCodeのモデル | `opencode/beam-free` |
| APIモデル | `beam-free` |
| 試行数 | 2、採点した生成物は1件 |
| 再現度 | **25/100点** |
| 生成時間 | 152.219秒 |
| 費用 | OpenCodeの記録値は0ドル |
| 保存形式 | FCStd、STEP |
| 再オープンした形状 | 各33ソリッド、無効形状0 |

初回は無料枠の接続確認でHTTP 403となり、CADを生成していません。生成性能の点数は付けていません。成功した2回目のAPI要求54件はすべてHTTP 200でした。429はありませんでしたが、レート上限を探る負荷試験ではなく、数値上の処理上限は示せません。

初回の中継はクライアントの識別ヘッダーを落としていました。公式ソースに基づき、観測した4ヘッダーを値を変えず転送するよう修正し、別試行を実行しました。提供元の現在の無料枠判定に、どのヘッダーが必須かまでは確定していません。

## 採点の根拠

| 項目 | 中央値 | 見える部位の根拠 |
| --- | ---: | --- |
| 輪郭・比率 | 9/25 | 低い四輪車の形はあるが、長い露出した長方形の骨格が、参照の外装でまとまった輪郭と異なる |
| 部品の配置 | 9/20 | シート、ハンドル、エンジン相当部はあるが、エンジンの位置が異なり、サイドポッドがない |
| 特徴的な形状 | 4/30 | 円筒と直方体が主体で、曲面のシート、先細りのノーズ、外装、タイヤ・リムの形状が乏しい |
| 機械的な細部 | 2/20 | 車軸と単純な排気管はあるが、冷却フィン、チェーン、スプロケット、操舵リンクやジョイントが乏しい |
| 配色 | 1/5 | 黒いタイヤは対応するが、灰色の骨格、青紫のシート、赤い外装が異なる |

コーディネータの先行評価は33点、新しいコンテキストでモデル名を伏せた独立評価は24点と25点です。最終25点は総点の平均ではなく、**項目別中央値の合計**です。評価者の実モデルIDは取得できず、不明として記録しています。全評価者が参照画像と生成3方向画像を確認しました。

## 記録値の意味

生成時間は生成開始からOpenCode終了までです。モデル待ち、内部の修正、MCP処理を含み、イメージ構築、準備、後からの検査・描画は含めません。起動準備は7.281秒、準備・回収・終了処理を含む実行全体は180.516秒でした。

0ドルはOpenCodeの記録値で、請求明細を監査した値ではありません。ログ監査では16件のツール呼出にエラーの兆候がありました。単純な実行集計は1件だけを数えたため、監査を併記しています。最終ファイルの成立と途中のエラーは別の根拠として残します。

別の通信できないコンテナでFCStdの再オープンとSTEPの再インポートに成功しました。両方とも33ソリッド、無効形状0、外形差の記録値は0mmでした。検査・描画前後で元ファイルのハッシュは変わっていません。これは保存形式の往復検査であり、寸法が不明な参照画像に対する精度を示すものではありません。

## 入力形式と比較の限界

Beam Freeの公開モデル情報は、ネイティブな画像入力を非対応としています。候補自身がPythonとPILで画素を調べ、ASCII表示、色集計、領域抽出、主軸解析のテキストを得ていました。コーディネータが画像説明を生成して渡したわけではありません。画像ファイルをツールで調べた結果であり、ネイティブな画像入力機能の実測ではありません。推論APIの生リクエスト本文と添付警告の実例は保存されていません。

旧GLMの43点はWindowsホスト版です。来歴と再検査のために残していますが、25対43の厳密なモデル比較には使えません。反復実行によるばらつきや、モデル全体の順位は示していません。

## 公開ファイルを確認する

[実験レポート](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/REPORT.md) · [構造化した結果](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/RESULT.json) · [採点と評価](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/trial-02/score.json) · [CAD検査](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/trial-02/evidence/validation.json) · [公開ファイルのハッシュ](https://github.com/Sunwood-ai-labs/SECCA/blob/main/experiments/beam-free-20261017/export-manifest.json)

## GLM 5.3 Flash Free · 2026-10-17、旧基準例

`opencode/glm-5.3-flash-free` の1生成物は**43/100点**でした。WindowsホストでOpenCode 1.19.3とFreeCAD 1.1.3を使い、生成時間は509.969秒です。保存したFCStdとSTEPは別プロセスで読み直し、双方77有効ソリッド、外形一致を確認しました。作動や干渉は検査していません。

平板のシート、簡略化されたノーズと前バンパー、ハンドルの向き、タイヤとリム、操舵部やエンジンの細部に差がありました。先行評価45点と、新しいコンテキストでモデル名を伏せた独立評価42・42点の、項目別中央値を合計した結果が43点です。42〜45点は統計的な信頼区間ではありません。評価者は同じアシスタントモデル系統で、人の専門家による評価ではありません。

この試行はOS隔離のないホスト実行で、配点は生成後、数値採点前に作成しました。採点した白背景の斜視と、向きを数値確認した上面・右面画像は保存されていますが、カメラ設定は後の固定クォータニオンによる標準描画と異なります。当時の条件差を残して参照し、後のPodman試行との条件をそろえた比較には使いません。初期の形状集計を直した前後の検査も残しており、CAD自体は修正していません。

[基準例の記録](https://github.com/Sunwood-ai-labs/SECCA/blob/main/references/baseline.md) · [採点と根拠](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/baseline/likeness-score.json) · [CAD検査](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/baseline/evidence/geometry-validation.json) · [FCStd](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/baseline/workspace/racing-kart.FCStd) · [STEP](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/baseline/workspace/racing-kart.step) · [採点した斜視画像](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/baseline/evidence/kart-front-isometric-white.png) · [上面画像](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/baseline/evidence/score-top-white.png) · [右面画像](https://github.com/Sunwood-ai-labs/SECCA/blob/main/assets/baseline/evidence/score-right-white.png)
