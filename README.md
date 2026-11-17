# UAV 論文再現

対象: *Nonlinear Trajectory Optimization Models for Uncrewed Aerial Vehicles with
Mobile Charging Support* (arXiv:2609.40201v1)。Rust 依存ライブラリなしで、
平滑化 NLP、ホモトピー、拡張ラグランジュ法、L-BFGS を実装している。

## 現状と読む順序

現在地と検証順は[ROADMAP.md](ROADMAP.md)、実行記録は[WORK_LOG.md](WORK_LOG.md)、単体検査は[TESTING.md](TESTING.md)。

- 診断用の入口で固定900件を完了。原実行可能な返却点894、返却点の固定分岐KKT830。AL終点の共通KKT863・追加物理KKT779は別の点の指標。
- 24件は旧入口、876件は外側停滞の打切り規則入り。著者MATLAB/L-BFGSと同じ実装ではない。
- 図3との目的値分布比較では、中央値比は1タスク1.067倍、7/8/9タスク2.230/2.387/2.553倍。証明付き返却点だけでも差が残り、著者の数値再現は未達。
- 同じ900入力の段階別診断を完了。両端が原実行可能な857組で591短縮・266件は差1秒以内。修復後の初期化受理202件は全て返却までの短縮が1秒未満で、多タスク側は前処理への依存が強い。
- G stage01時間切れ219件を診断。全件が外側4〜9回で120秒に達し、内側stuckは0。9タスクは規則入り97件全てがこの型。内側計算の費用と段階予算の組合せがGの進行を止めている。
- 次は保存3状態の1反復を分解計測し、Hessian構築・固有分解・探索の費用を区別してから少数例の対照を計画する。修正効果は未検証。

[初段時間切れの診断](experiments/2026-11-17-r3s-stage01/REPORT.md)・[図](experiments/2026-11-17-r3s-stage01/stage01-diagnosis.png)、
[段階別診断](experiments/2026-11-17-r3s-stage-objectives/REPORT.md)・[図](experiments/2026-11-17-r3s-stage-objectives/stage-objectives.png)、
[図3との比較](experiments/2026-11-17-r3s-paper-comparison/REPORT.md)・[分布図](experiments/2026-11-17-r3s-paper-comparison/objective-distributions.png)、
[900件の求解レポート](experiments/2026-11-16-r3s-cohort/REPORT.md)・[実行手順](experiments/2026-11-16-r3s-cohort/USAGE.md)。
課題2〜4の草稿は[human/report.md](../human/report.md)。本体`src/`と診断用`experiments/`の成果は区別する。

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
