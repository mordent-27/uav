# R2eの保存物と実行

[REPORT.md](REPORT.md)が主な結果、[PLAN.md](PLAN.md)が最初に固定した条件。
`STATUS.md`と`summary.json`は最初の4例の結果を固定している。
`combined-summary.json`と`comparison.md`は別に計画した[R2e-2](../2026-11-15-r2e-feasible-start/REPORT.md)を明示した集計。

`initialize.py`は入力だけから既存の原制約NLPを解き、受理された場合だけ`phase.py`で同じ直接開始を行う。
`verify_init.py`が初期化のKKTと原制約/電池/全精度yを再計算する。
最終問題と復元/検証は以前のファイルを変更せず読み込む。`driver.py`は最大4独立プロセスで実行する。

この環境で使った求解コマンド：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/home/mordent/.cache/uv/archive-v0/IH8olt7ky0AxR5WV:/home/mordent/.cache/uv/environments-v2/sys-id-chirp-1714f8f5f4d59f0e/lib/python3.12/site-packages \
/home/mordent/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python \
experiments/2026-11-15-r2e-position-init/driver.py
```

同じ環境指定で、追加対照は`experiments/2026-11-15-r2e-feasible-start/driver.py`を実行した。
ドライバーは既存の`logs/`や各出力先への上書きを拒否する。再実行するなら版を保った別の実験先を用意する。
追加対照は`initialize.py`にx0の構成を加えた1行だけが差分で、`initializer.patch`に保存している。

集計とRust照合は求解をやり直さずに実行できる。

```bash
python3 experiments/2026-11-15-r2e-position-init/analyze.py
python3 experiments/2026-11-15-r2e-position-init/combine.py
python3 experiments/2026-11-15-r2e-position-init/audit_outputs.py
```

Rust照合には`rustc`が必要。図は`plot.py`（matplotlib）、環境/保存物記録は`capture.py`（求解と同じパッケージ環境）。
`cases/{original,repaired}/`に各直接開始の初期点・状態・最終出力・復元・検証、`initializations/`に原制約初期化を保存。
大きい内側ログはローカルに残し、各実験の`local-inner-manifest.json`にhashを記録する。
`provenance.json`に依存ソース/ライブラリ/再利用結果のhash、`human-notes.tar.gz`に外部文書、`artifact-index.json`に保存物を記録する。
