# 検算

uav/で実行。単体検査は標準ライブラリのみ、独立検算はNumPyが必要。

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s experiments/2026-11-17-r3s-step-profile -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-17-r3s-step-profile/verify.py --check-only
```

`--check-only`は成果物を変更せず、モデルも呼ばない。入力hash・保存点/行列・全63行の時間・BLAS環境の記録を検算する。
完全な再実行は別の出力先で計画する。profile_step.pyは既存cases/の上書きを拒否する。

初回生成順はfreeze.py → 計画/コード/入力indexをコミット → profile_step.py → analyze.py → verify.py → plot.py。
profile_step.pyはNumPy/SciPy/threadpoolctl、既存の評価ライブラリ2本を使う。plot.pyのみMatplotlibが必要。
各ケースのenvironment.jsonにPython/NumPy/SciPy/BLASの実行情報を保存した。BLAS/OMPは各1スレッド。
`library-index.json`の/tmpライブラリが無い場合は、R3sのrestore_evaluators.pyと保存アーカイブでhash照合して復元できる。

source-index.jsonは73入力、artifact-index.jsonは今回の成果物（index自身を除く）のhash。
human6文書はhuman-notes.tar.gz、repo4文書はrepo-notes/にsnapshotを保存した。
