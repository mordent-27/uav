# R2e-2の追加対照

条件は[PLAN.md](PLAN.md)、結果は[REPORT.md](REPORT.md)。
`construct.py`は1点の移動と時間/電池の再計算で実行可能な初期値を構成する。
`initializer.patch`のとおり、R2e-1からの数値コードの差分はNLPのx0設定だけである。
`phase.py`と`verify_init.py`はR2e-1の処理をそのまま読み込む。
`charge19-check.json`は最終直接開始の全内側点で必要な充電を保持したかの再評価。

実行環境とコマンド、全体の集計/Rust照合/保存物は[R2eのREADME](../2026-11-15-r2e-position-init/README.md)を参照。
この実験のドライバーは1プロセス、各BLAS/OpenMP/MKL1スレッド。
不受理だった最初の試行は別実験へ保存したままで、ここでは書き換えていない。
