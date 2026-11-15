# UAV 論文再現

対象: *Nonlinear Trajectory Optimization Models for Uncrewed Aerial Vehicles with
Mobile Charging Support* (arXiv:2609.40201v1)。Rust 依存ライブラリなしで、
平滑化 NLP、ホモトピー、拡張ラグランジュ法、L-BFGS を実装している。

## 現状と読む順序

全体の達成状況・未達事項・次の検証順は **[ROADMAP.md](ROADMAP.md)** にまとめている。

- 診断用解法では、良い保存点から各段階の共通KKTを確認し、第13段階まで進めた。
- 最終平滑化点は約1.87913 h。原制約で別に再最適化した約1.88259 hの解は、原制約と電池に合格した。
- 保存済み良解・診断Newton・復元への依存が残る。著者のL-BFGSと100本ずつの数値再現は未達。
- 次は元の初期軌道から同じ診断経路を通し、良い初期解への依存を切り分ける。

根拠と条件は[直近の実験レポート](experiments/2026-11-15-decomposed-follow/REPORT.md)、
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
