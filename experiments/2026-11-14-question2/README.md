# 課題2の検討：単一ステーションの再訪の反例

詳しい検討の本体は、ワークスペースの `human/report.md` と
`human/question2_notes.md`。同じ内容を `human-notes.tar.gz` に保存した。
ワークスペースのルートを基準とするパスで収録している。

## 主張の範囲

半径2kmの円形充電領域内で、同じ一台の充電車両がA=(-1,0), B=(1,0)kmの
二地点を順に担当する運用を考える。
UAVが「Aで30秒充電、200秒でBへ飛行、Bで30秒充電」という行程を取ると、
論文の原制約(11),(12),(24)は満たすが、車両は200秒ではAからBへ移動できない。
速度上限10.8km/hでは666.7秒必要になる。

車両の次回の充電地点への移動を明示的にモデル化しなければ、単一車両での
実施可能性まで保証できないことを示す。平滑化や求解誤差による反例ではない。
複数の車両の待機など、領域内でのサービスを外部で保証する運用は対象外。

## 再実行

`uav/` を作業ディレクトリとする。

```bash
python3 experiments/2026-11-14-question2/station_counterexample.py \
  > experiments/2026-11-14-question2/station-counterexample.log
python3 scripts/verify_solutions.py \
  experiments/2026-11-14-question2/station-counterexample.json \
  >> experiments/2026-11-14-question2/station-counterexample.log
```

原制約違反: Pythonでは5.55e-17、Rustでは0（浮動小数点精度内）。
移動距離不足: `2 - 10.8*(200/3600) = 1.4 km`。

## 文書の保存

`human-notes.tar.gz` は、ワークスペースのルートで次のように作成した。

```bash
tar -czf uav/experiments/2026-11-14-question2/human-notes.tar.gz \
  human/report.md human/question2_notes.md
```

文書を参照するだけなら `tar -xOzf human-notes.tar.gz human/question2_notes.md`
で抽出せずに読める。
