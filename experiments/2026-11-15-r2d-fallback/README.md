# R2dの実行と保存物

求解前の条件は[PLAN.md](PLAN.md)。既存Gの8受理を保ち、未受理の場合だけ元初期点から直接開始を一度追加する。
目的値による選択や、未受理例を除く集計はしない。

`helpers.py`は過去の条件Gのヘルパーを読み、出力先だけを変える。
`phase.py`は初期点とAL勾配を確認してから、過去のGまたは直接開始のランナー・復元・検証器をファイルごと読み込む。
数値ランナーのコピーやオプション変更はない。
`driver.py`は未確認の既存1例と、先に指定したseed=3の4サイズを最大5並列で処理する。
この4サイズはタスク列の先頭を共有するので相互に独立ではない。

この環境で実行したコマンド：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/home/mordent/.cache/uv/archive-v0/IH8olt7ky0AxR5WV:/home/mordent/.cache/uv/environments-v2/sys-id-chirp-1714f8f5f4d59f0e/lib/python3.12/site-packages \
/home/mordent/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python \
experiments/2026-11-15-r2d-fallback/driver.py
```

`driver.py`は既存の`logs/`や各phaseの出力への上書きを拒否する。
再実行は過去の結果を変更せず、ヘルパーを含む版を保った別の実験先を用意する。
共有ライブラリ・依存ソース・パッケージの版とhashは`provenance.json`に残す。
求解前の`precheck.py`は過去の依存ソース/共有ライブラリのhashと、再利用する13初期点の完全一致を確認する。

求解後の集計はPython標準ライブラリで再実行できる（数値求解はしない）。

```bash
python3 experiments/2026-11-15-r2d-fallback/analyze.py
python3 experiments/2026-11-15-r2d-fallback/costs.py
python3 experiments/2026-11-15-r2d-fallback/diagnose.py
python3 experiments/2026-11-15-r2d-fallback/initial_audit.py
python3 experiments/2026-11-15-r2d-fallback/branch_bound.py
python3 experiments/2026-11-15-r2d-fallback/audit_outputs.py
```

`audit_outputs.py`はRustの元評価器で新しい段階/最終/復元出力と採用先を照合する。`rustc`が必要。
原制約の厳しい検査1e-10は規則の受理条件1e-6と分け、失敗した場合はログを残して終了する。
`plot.py`にはmatplotlib、`capture.py`の環境記録には求解時と同じパッケージ環境が必要。

各`cases/{G,direct}/入力/`に初期点・外側状態・最終出力・復元・検証を保存する。
内側ログはローカルに残し、`local-inner-manifest.json`へhashを記録する。
`summary.json`と`comparison.md`は採用先と費用、`stage-costs.json`は段階別費用、
`failure-diagnosis.json`は止まったGの観測値、`input-relations.json`は入力間の共有関係を記録する。
`human-notes.tar.gz`はリポジトリ外のhuman文書のスナップショット、`artifact-index.json`は保存物のhashである。
