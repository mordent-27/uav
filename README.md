# UAV 論文再現

対象: *Nonlinear Trajectory Optimization Models for Uncrewed Aerial Vehicles with
Mobile Charging Support* (arXiv:2609.40201v1)。Rust 依存ライブラリなしで、
平滑化 NLP、ホモトピー、拡張ラグランジュ法、L-BFGS を実装している。

## 現状と読む順序

全体の達成状況・未達事項・次の検証順は **[ROADMAP.md](ROADMAP.md)** にまとめている。

- G受理時に出力を保持し、未受理時だけ修復経路へ進む単一入口を実装。既存25入力でG12例・補助13例を採用し、全返却点の原制約/固定分岐KKTを確認した。
- AL終点の共通KKTは25例、追加物理KKTは23例、最後の復元受理は24例。設計例1件は保存証明で返す。全25入力は既見の設計/回帰確認である。
- 次は固定した入口を未使用の別seedでキャッシュなしに通し、Gを含む総費用と解の質を確認する。
- 平滑化KKTと返却点の原制約/固定分岐KKTは別の点の性質。本体Rustの900本・著者の実験再現は未達。

根拠と条件は[直近の実験レポート](experiments/2026-11-16-r2h-g-first/REPORT.md)、
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
