# R2fの実行と保存物

[PLAN.md](PLAN.md)は求解前の条件、[REPORT.md](REPORT.md)は結果と限界。
共通の構成は[scripts/repair_initialization.py](../../scripts/repair_initialization.py)の`repair(data)`。
標準ライブラリのみで、(軌道辞書またはNone, 判定辞書)を返す。入力を変更せず、既に原実行可能なら完全保持する。
入力は`phys`、`instance`、`solution`、`modes`、`task_stamp`を含む全精度の辞書を使う。
原制約NLPや最終平滑化NLPを解く関数ではなく、物理的な初期点の構成と監査である。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_repair_initialization.py
```

実験の`guard.py`は監査/構成だけ、`initialize.py`は必要な場合の一度の原制約NLP、`phase.py`は元の直接開始を使う。
数値ランナー/復元/検証は過去のファイルをそのまま読み込む。担当点の原入力チェックの差分はpatchへ保存。

この環境で実行したコマンド：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/home/mordent/.cache/uv/archive-v0/IH8olt7ky0AxR5WV:/home/mordent/.cache/uv/environments-v2/sys-id-chirp-1714f8f5f4d59f0e/lib/python3.12/site-packages \
/home/mordent/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python \
experiments/2026-11-15-r2f-general-init/driver.py
```

最大8独立プロセス、各1スレッド。既存のlogs/や初期化/求解出力への上書き・再試行を拒否する。
再実行するなら版を保存した別の実験先を用意する。環境と依存/ライブラリhashはprovenance.jsonに残す。

```bash
python3 experiments/2026-11-15-r2f-general-init/analyze.py
python3 experiments/2026-11-15-r2f-general-init/audit_outputs.py
```

上記は求解を繰り返さない。Rust照合にはrustcが必要。
`recheck_incumbent.py`も保存点の再評価だけで、追加のNLPを解かない。求解時と同じ環境指定に加え、
`UAV_R2_CASE=tau5-seed3 UAV_R2F_KIND=repaired`を設定して実行する。
その証拠出力は既存のdiagnostics/への上書きを拒否する。

`initializations/`に監査・構成点・原制約NLP、`cases/`に新規直接開始の全状態・最終出力・復元・検証を保存。
`summary.json`/comparison.mdが対比較、`restore-certificate-recheck.json`は不受理とは別の有効点の証明、
`input-relations.json`は新規4入力がすべて修復不要だったことも記録する。
内側ログはローカルに残しlocal-inner-manifest.jsonへhash、外部human文書はhuman-notes.tar.gz、保存物はartifact-index.jsonへ記録する。
実行後の公開関数のメタデータ修正はrun-source/とmetadata-compatibility.jsonで区別する。
