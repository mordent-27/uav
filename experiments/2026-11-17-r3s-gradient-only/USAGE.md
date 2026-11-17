# 検算

NumPy環境でuav/から実行する。モデルや完全求解は起動しない。

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s experiments/2026-11-17-r3s-gradient-only -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-17-r3s-gradient-only/verify.py --check-only
```

全勾配・行列・キャッシュを保存NPZからbytes比較し、CSVの統計と表を別コードで検算する。入力/成果物hashも確認する。
初回生成順はrun.py --freeze → 計画/入力/コードをコミット → run.py → analyze.py → verify.py。
run.pyは既存cases/を上書きしない。完全再実行は別出力先で計画し、NumPy/SciPy/threadpoolctlと前回と同じ評価ライブラリ2本を使う。
BLAS/OMPは1スレッド。環境は各caseのenvironment.jsonへ記録。
source-index.jsonは78入力。artifact-index.jsonは今回の成果物のhash（index自身を除く）。
human6文書はtar、repo4文書はrepo-notes/に保存した。過去の成果物は変更していない。
