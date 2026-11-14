# 追加の批判的検討の検証

本体の文書はワークスペースの `human/critical_review.md`。
更新した `human/report.md`, `human/question2_notes.md`, `human/critical_review.md` を
`human-notes.tar.gz` に保存する。アーカイブ内のパスはワークスペースルート基準。

## 再実行

`uav/` を作業ディレクトリとする。Python標準ライブラリとrustcのみ必要。

```bash
python3 experiments/2026-11-14-critical/critical_checks.py
python3 scripts/verify_solutions.py \
  experiments/2026-11-14-critical/duration-example.json \
  > experiments/2026-11-14-critical/rust-original-validation.log
```

`critical_checks.py` は入力JSON、集計JSON、Rustでの平滑化制約評価ログを生成する。
全モデルの制約評価には既存の `src/model.rs` をそのまま使い、一時ソースを作成して
コンパイルする。ソルバーのオプションやコードは変更していない。

## 確認事項

- `duration-example.json`: eps=.2, p=2, delta=.001の平滑化NLPで、
  30秒の区間に50.911581秒の充電を割り当てる例。全ての平滑化制約を評価し、
  等式残差最大3.997e-16、不等式違反0。電池上下限も満たす。
  原問題では実行不能で、原制約違反は0.282843。両方の評価を保存した。
- `checks.json`: 単位変更、重複候補、有限pでの厳密訪問排除、最小時間の下界、
  半群性を満たさない電池写像、零点集合を保つ関数、安定化LSEの数値を記録。
- 電池写像の例は一般条件(5)の不足についての例であり、数値例のCC–CVへの批判ではない。
- 初期段階の平滑化での反例は、著者の最終出力に同じ違反があることを意味しない。
- Nの下界の例は充電が利用できない場合。充電で補える場合に同じ不可能性は主張しない。

## 参照した追加文献

Blanchard, Higham & Higham, *Accurately Computing the Log-Sum-Exp and Softmax Functions*,
2020-01-31版の著者原稿、特に式(1.3),(1.4)とシフト計算の誤差解析。
[大学リポジトリの原稿](https://eprints.maths.manchester.ac.uk/2744/1/paper.pdf)。
この文献は安定化LSEの根拠にのみ使用し、今回のUAVモデルでLSEの方がよいと
実験的に示したものではない。

## 文書の保存コマンド

ワークスペースのルートで実行する。

```bash
tar -czf uav/experiments/2026-11-14-critical/human-notes.tar.gz \
  human/report.md human/question2_notes.md human/critical_review.md
```
