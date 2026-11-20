# 再確認・再実行

`uav/`をカレントディレクトリとする。CasADi、NumPyが必要。標準ライブラリのみで保存結果の独立検算が可能。

```bash
python experiments/2026-11-20-carrier-followup/verify_results.py
python experiments/2026-11-20-carrier-followup/make_witnesses.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python experiments/2026-11-20-carrier-followup/test_model.py
```

今回の求解・単体検査では、既存のuv環境を以下の指定で使った。新規パッケージをインストールせず、既存の共有モデルや実験は変更していない。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/home/mordent/.cache/uv/archive-v0/IH8olt7ky0AxR5WV:/home/mordent/.cache/uv/environments-v2/sys-id-chirp-1714f8f5f4d59f0e/lib/python3.12/site-packages
/home/mordent/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python experiments/2026-11-20-carrier-followup/run.py
/home/mordent/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python experiments/2026-11-20-carrier-followup/from_reduced.py
```

run.pyとfrom_reduced.pyは既存の出力を上書きせず停止する。再求解は別の保存先へ移植し、今回の入力ハッシュを保持して行う。求解時間の比較は直列で行う。verify_results.pyは決定的なsummary.jsonとverification.jsonを再生成するが、入力点・求解記録は変更しない。

TeX/PDFはhuman/を編集対象とし、uav/のGit外なのでrevised/へ同内容を保存する。ビルドは旧レビューのbuild_report.py（uplatex×2→dvipdfmx、A4・8ページ・TeX警告を検査）を使用。図は今回は変更しない。
