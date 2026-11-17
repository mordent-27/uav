# 保存結果の検算

uav/から実行。Python標準ライブラリのみで検算できる。

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s experiments/2026-11-17-r3s-stage01 -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-17-r3s-stage01/verify.py --check-only
```

900件と6,982内側記録を生ログから再読し、原集計のID/対象判定、外側回数、rho更新、KKT成分、中断点の不採用、差分カウンタ、サイズ別集計、REPORTの件数表を検算する。
代表3例の最初/最後の内側トレース6本も、保存したコピーから生点を照合する。
`verification-before-representatives.json`は代表例を追加する前の検算を改名して保持したもの。`verification.json`は代表例も含む。

初回の生成順はanalyze.py --freeze → 計画/コード/indexをコミット → analyze.py → inspect_representatives.py --freeze → inspect_representatives.py → verify.py。
生成済み出力があるため、同じ場所での再集計はassertで停止する。図を作り直す場合も別出力先で行う（Matplotlibが必要）。
`source-index.json`は2,933入力のhash。追加の6トレースは`representative-source-index.json`に保存コピーのhashを固定し、元のパスは`representative-selection.json`に記録した。
`artifact-index.json`は今回の成果物のhash（index自身を除く）。human6文書をtarへ、repo4文書をrepo-notes/へ保存。
原求解結果と過去の実験は変更していない。新規求解/KKT再計算は0。
