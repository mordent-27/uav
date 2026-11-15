# UAV 論文再現

対象: *Nonlinear Trajectory Optimization Models for Uncrewed Aerial Vehicles with
Mobile Charging Support* (arXiv:2609.40201v1)。Rust 依存ライブラリなしで、
平滑化 NLP、ホモトピー、拡張ラグランジュ法、L-BFGS を実装している。

## 現状と読む順序

全体の達成状況・未達事項・次の検証順は **[ROADMAP.md](ROADMAP.md)** にまとめている。

- 原実行可能点の保持規則を実装し、受理済みの既見20出力を完全保持した。既知の失敗例1件は保存証明で原実行可能点を返せた。
- 負電池の新規4入力は対照・修復側とも両尺度KKTと最後の復元に合格。成功件数の改善や、未知入力での保持による失敗補完は示していない。
- 次はGの受理済みの解を保持し、G未受理時だけ修復経路へ進む入口を固定する。
- 平滑化KKTと返却点の原制約/固定分岐KKTは別の点の性質。本体Rustの900本・著者の実験再現は未達。

根拠と条件は[直近の実験レポート](experiments/2026-11-15-r2g-incumbent/REPORT.md)、
経過は[WORK_LOG.md](WORK_LOG.md)、課題2〜4の草稿は[human/report.md](../human/report.md)を参照。
過去の詳細はロードマップの各リンクからたどれる。
本体`src/`と診断用`experiments/`は区別し、過去の900本の測定を現行版の成功率へ読み替えない。

## 実行

```bash
cargo test
cargo build --release
mkdir -p out
target/release/uav solve --fig1 --verbose --out out/fig1.json
target/release/uav mc --tau-min 1 --tau-max 7 --runs 8 --threads 4 --out out/mc.csv
python3 scripts/summarize.py out/mc.csv
```

`uav help` で設定一覧を表示する。原問題の制約違反と KKT 収束は別々に確認する。
`out/` は Git 管理対象外。残す実験はコマンドとともに `experiments/` に保存する。

## 解の構造の診断

```bash
python3 scripts/diagnose_solution.py out/fig1.json \
  --out out/diagnosis.json --segments-dir out/segments --polish-dir out/fixed-modes
python3 scripts/verify_solutions.py out/fig1.json out/fixed-modes/*.json
uv run scripts/plot_solution.py out/fixed-modes/fig1-fixed-modes.json out/fixed-modes/fig1.png
```

診断と Rust 評価の照合には Python 標準ライブラリと `rustc` のみ必要。
図の生成には matplotlib が必要（`uv run` がスクリプトの依存指定を読む）。
後処理は区間の充電・放電を固定して電池残量を計算し直す。実行不能な場合には
解を出さず、その理由を診断 JSON に記録する。訪問順序や充電箇所の探索は行わない。
