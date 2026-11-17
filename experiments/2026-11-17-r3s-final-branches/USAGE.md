# 保存点の検算

uav/で実行。Python標準ライブラリのみ。新しい求解もモデル呼出も行わない。

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s experiments/2026-11-17-r3s-final-branches -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-17-r3s-final-branches/verify.py --check-only
```

初回はrun.py --freeze → 計画/コード/入力をコミット → run.py → inspect_energy.py → verify.pyの順。
生成済み結果の再作成は別ディレクトリで計画する。図だけMatplotlibを使う。
独立検算は全区間の被覆・タスク順・可動端点の領域・距離下界を元の入力から組み直して照合する。
返却点はタスク座標の1e-9 km以内の表現差を確認し、その点自身の保存座標で照合する。
source-index.jsonは38入力、artifact-index.jsonは今回の成果物のhash（index自身を除く）。
human6文書とrepo4文書をsnapshotに保存した。

native_check.pyはNumPy/SciPy環境と保存評価ライブラリで最終672行を照合した。native-model-check.jsonに結果とライブラリhashを保存。
verify.pyはこの記録も確認するが、新たなnative評価や停留性の再計算は行わない。
