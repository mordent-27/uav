# 保存結果の検算

uav/から実行。検算・単体テストはPython標準ライブラリのみで動く。

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s experiments/2026-11-17-r3s-stage-objectives -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-17-r3s-stage-objectives/verify.py --check-only
```

`--check-only` は成果物を変更しない。`verification.json`は202件の探索的補足まで含む最終検算結果。
`verification-before-initialization-inspection.json`は、その補足を追加する前に実行した検算の記録を改名して保持したもの。

初回生成時は `analyze.py --freeze` → 計画/コード/入力hashをコミット → `analyze.py` → `inspect_initialization.py` → `verify.py` の順。
初回生成済みなので、同じディレクトリで再集計すると既存出力のassertで停止する。
`plot.py`はMatplotlibを使う。検算用に図を作り直す場合も、保存版を書き換えず別の出力先で実施する。

`source-index.json`は消費した10,748入力のhash。`analysis-dependencies.json`は物理監査の依存2モジュール、
`artifact-index.json`は今回のコード/表/図/レポート/検算/文書snapshotのhash（index自身を除く）。
repo外のhuman文書6本は`human-notes.tar.gz`と`human-source-index.json`に記録し、repo内の4文書は`repo-notes/`に保存した。
原求解成果物と前回の分布比較成果物は変更していない。新規求解とKKT再計算はいずれも0。
