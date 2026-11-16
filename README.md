# UAV 論文再現

対象: *Nonlinear Trajectory Optimization Models for Uncrewed Aerial Vehicles with
Mobile Charging Support* (arXiv:2609.40201v1)。Rust 依存ライブラリなしで、
平滑化 NLP、ホモトピー、拡張ラグランジュ法、L-BFGS を実装している。

## 現状と読む順序

全体の達成状況・未達事項・次の検証順は **[ROADMAP.md](ROADMAP.md)** にまとめている。

- 固定900入力は24件実行・876件未実行で保持。AL共通KKT22・追加物理KKT21、復元/固定分岐証明19、原実行可能点24。
- ユーザー選択により900追加より診断を優先。条件付き再試行の別4例は既定で全件受理し、追加を呼ばず保持。新規例の救済効果は未観測。
- 高rho/大乗数の4状態でも方向曲率評価は精度基準を通過した。ただし固定ALの2状態ではCG版が両方300反復で未達、旧方式より約7〜8倍遅く、精度も劣った。本体/固定900へは未採用。
- 全206勾配を照合した後、評価精度だけを変える4内側求解を比較したが、高精度でも大きい例は未達。続く診断で旧Hessianの負固有値は見かけと分かった。弱活性の不等式の両側に分けても勾配∞6.0e-8で止まり、折れ目は原因でなかった。旧Hは電池のCC/CV切替をまたぐ差分でNewton方向の曲率を半分に見ており、その2列を作り直すと高精度点はNewton 1回で勾配∞3.5e-12に届いた。binary64へ丸めた点では3.5e-7/局所格子1.2e-7で届かない（rho=1e8の丸め下限）。本体と同じ内側求解で片側差分にしても改善しなかった（3状態、混在2・同じ1）。止まった試行を再生すると、拒否された24試行は正確に測れば予測どおりALを減らしており、AL値が大きいため全てfallbackに入って拒否されていた。
- 平滑化KKTと返却点の原制約/固定分岐KKTは別の点の性質。本体Rustの900本・著者の実験再現は未達。

根拠と条件は[直近の実験レポート](experiments/2026-11-16-stuck-trials/REPORT.md)、
経過は[WORK_LOG.md](WORK_LOG.md)、課題2〜4の草稿は[human/report.md](../human/report.md)を参照。
過去の詳細はロードマップの各リンクからたどれる。
本体`src/`と診断用`experiments/`は区別し、過去の900本の測定を現行版の成功率へ読み替えない。

単体テストの実行方法と数理的な検査範囲は[TESTING.md](TESTING.md)を参照。

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
