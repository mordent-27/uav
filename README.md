# UAV 論文再現

対象: *Nonlinear Trajectory Optimization Models for Uncrewed Aerial Vehicles with
Mobile Charging Support* (arXiv:2609.40201v1)。Rust 依存ライブラリなしで、
平滑化 NLP、ホモトピー、拡張ラグランジュ法、L-BFGS を実装している。

## 現状

**論文の数値再現は未達成**。
独自入力による1〜9タスク各100本、計900本の基準実験を完了したが、KKT収束は0/900。
元の制約違反<=1e-3は438/900で、図3から読み取ったNLPの895/900との差が残る。
この閾値は独自の比較基準で、著者の明示した成功率ではない。
別の13例の診断では、実行可能集合を保つ速度制約の前処理とBFGSで最終KKTが3/13。
元表現でも残差を照合したが、図1相当と純モード電池の課題は未解決。
詳細は[再現再開レポート](experiments/2026-11-14-reproduction/REPORT.md)。本体srcは変更していない。

続く[固定ペナルティの診断](experiments/2026-11-14-conditioning/REPORT.md)では、
同じ900本の元違反<=1e-3が774件、KKTが1件だったが、追加物理監査は82件に減った。
[保存状態からの継続](experiments/2026-11-14-final-continuation/REPORT.md)では、
図1相当の最終KKTにも到達した。これは診断用ニュートン法・合計559外側による結果で、
目的値2.0987 hと電池不足が残り、論文の数値再現達成とはしない。

[原制約での復元](experiments/2026-11-14-restoration/REPORT.md)では電池不足を修復し、
同じ割当てで約2.098965 hの原実行可能解を得た。
その割当ての凸緩和の数値下界も約2.08325 hで、論文の読取値約1.8932 hより大きい。
手元の入力では、現在固定している訪問・モード・領域・Nの選択を変える必要がある。
これは後処理と下界評価であり、元の平滑化アルゴリズムの再現成功とは分ける。

2026-11-14 にタイムアウト後の作業を再開。変更前の実装・過去の出力は
コミット `a303bd1` に保存した。調査の詳細と再実行コマンドは
[診断レポート](experiments/2026-11-14-resume/REPORT.md)、経過は
[WORK_LOG.md](WORK_LOG.md) を参照。

過去の設定探索では、実行不能な解での飛行中の充電と、制約は満たすが余分に
充電する解を確認した。現在のデフォルト設定による図1相当の解は 1.958805 h。
経路・区間モードを保持する診断用の時間短縮で 1.857481 h の実行可能解を得た。
この後処理は論文のアルゴリズムに追加した実験であり、元ソルバーの KKT 収束や
100件ずつの成功率の再現は未達成。図の座標と基準時間は論文からの読み取り値。

追加の限定比較では、[モードの尺度統一](experiments/2026-11-14-scaling/REPORT.md)で
固定13例の原制約が全て許容値内になった。[ALの引継ぎの比較](experiments/2026-11-14-auglag/REPORT.md)
ではKKT収束に至らなかった。比較モデルと全出力は実験ディレクトリに保存している。

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
