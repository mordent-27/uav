# UAV 論文再現

対象: *Nonlinear Trajectory Optimization Models for Uncrewed Aerial Vehicles with
Mobile Charging Support* (arXiv:2609.40201v1)。Rust 依存ライブラリなしで、
平滑化 NLP、ホモトピー、拡張ラグランジュ法、L-BFGS を実装している。

## 現状と読む順序

全体の達成状況・未達事項・次の検証順は **[ROADMAP.md](ROADMAP.md)** にまとめている。

- 入力からの初期修復を共通スクリプト化した。元の実行可能な18初期点は完全保持し、必要な3例だけ修復した。
- 回帰17例の両尺度KKTは16→17件、原制約復元は16→16件（救済1/転落1）。新規4例は合格したが、全て修復不要だった。
- 転落した1例にも、同じ最終分岐で検査を通る原実行可能点が前処理で既に得られていた。次はその点/証明を保持する手順を固定する。
- 本体L-BFGSの900本・著者の実装/性能分布の再現は未達。今回の診断手法は本体Rustには採用していない。

根拠と条件は[直近の実験レポート](experiments/2026-11-15-r2f-general-init/REPORT.md)、
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
