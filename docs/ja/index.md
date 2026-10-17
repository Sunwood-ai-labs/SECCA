---
layout: home
hero:
  name: SECCA · 雪華
  text: 画像から、どこまでCADを構築できるか。
  tagline: Solid-model Evaluation of CAD Construction Agents。固定のレーシングカート課題を、保存した形状・描画画像・採点根拠から評価します。
  image:
    src: /secca-mark.svg
    alt: 雪の結晶とCAD立体を組み合わせたSECCAロゴ
  actions:
    - theme: brand
      text: 固定課題を実行する
      link: /ja/guide/getting-started
    - theme: alt
      text: 実験の根拠を見る
      link: /ja/guide/results
features:
  - title: 固定した課題
    details: 画像と依頼文を1つずつ使用。配点・描画条件・プロトコルのハッシュを記録します。
  - title: 保存した形状
    details: FCStdとSTEPを別の通信できないコンテナで開き、固定の白背景画像を描画します。
  - title: 根拠を残す採点
    details: 3件の評価を保存し、項目ごとの中央値を合計します。
---

<div class="experiment-card">
  <img src="/beam-preview.png" alt="白背景で描画したBeam Freeの生成カート" width="960" height="600" />
  <div>
    <p class="experiment-label">実験記録 · 2026-10-17</p>
    <h2>Beam Free</h2>
    <p class="experiment-score">25 <small>/ 100点</small></p>
    <p>採点した生成物は1件。CAD生成は成功しましたが、曲面の外装や機械部品の細部には大きな差が残りました。</p>
    <p><a href="./guide/results">結果と限界を読む →</a></p>
  </div>
</div>

## 比較の前に、根拠を確認する

候補へ渡した入力、ランタイム、保存CAD、目視採点の根拠を残します。CADとして成立することと、画像に似ていることは別の結果です。

<div class="evidence-flow">固定画像・依頼文 → 隔離して生成 → FCStd・STEPを保存 → 別コンテナで検査・白背景描画 → 3件の評価 → 項目別中央値を合計</div>

Beam FreeはPythonで画素を調べ、テキスト出力を使っていました。ネイティブな画像入力機能の実測ではありません。旧GLMのWindowsホスト版は歴史的な参考資料であり、今回のPodman実行との厳密な比較には使えません。

日本語名は**雪華（せっか）**。[固定プロトコル](./guide/protocol)から読むか、[英語版](../)へ切り替えられます。
