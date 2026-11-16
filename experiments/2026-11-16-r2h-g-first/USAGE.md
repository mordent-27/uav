# R2hの入口と保存先

リポジトリ`uav/`から、NumPy/SciPy/CasADiを利用できるPythonで実行する。
今回の実際のPython・依存版・PYTHONPATH・起動環境は`execution.json`と`launch-record.json`、
各子プロセスの実コマンドは`logs/*/*-launch.json`にある。
元制約の評価用共有ライブラリは過去の診断と同じ`/tmp/uav-fidelity-{original,speed}.so`を使う。
生成方法と依存ソースは過去の実験記録・今回の`provenance.json`を参照する。

単一の既存入力を再検証する例（出力先は未作成のものを指定）：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-16-r2h-g-first/solve.py \
  --case fig1 --out-root experiments/r2h-replay-example
```

既定の`catalog.json`に同じ入力があれば、保存されたGと、必要時だけ保存された補助経路を再検証する。
catalogにない入力（例：未使用seed）では元初期点を生成し、Gを新規に一度解く。
Gが未受理なら元入力の監査・必要な構成/初期化・直接開始・点保持を新規に実行する。
この新規補助経路の一続きの呼出しは、R2hの25入力では未実行である。
個々の数値処理はR2f/R2gで検証した処理をそのまま呼び出すが、新規入力の結果は保証しない。

出力先はリポジトリ内に限定し、同じcaseの出力の上書き・再試行を拒否する。
25入力の`driver.py`も同じ入口を8 workerで呼ぶ。今回は出力が既にあり、その場所への再実行は拒否される。
求解上限や対象を変えて実行する場合は別のPLANと出力先を用意し、今回の数値と混ぜない。

- `inputs/<case>/`：元入力と全精度の初期状態。
- `cases/G/<case>/`：今回新たに解いたGだけ。既存17例の参照先はcatalog。
- `evaluations/G/<case>/`：Gの保存証明の再評価。
- `evaluations/fallback/<case>/`：G未受理の場合だけ作られる再評価。
- `runs/<case>/result.json`：経路、異なる点で測った各指標、費用、エラー、選択先hash。
- `runs/<case>/selected.json`：返却可能な点がある場合の出力。その点の平滑化KKTを推定しない。
- `reverification*`：求解をせず、今回の全内側/外側点を既存G検査器で再評価した記録。
- `local-inner-manifest.json`：Gitから除外した内側ログのhash。ログ本体はこの作業ディレクトリだけに残る。

原制約検査/固定分岐KKTの返却点と、平滑化KKTを測るAL終点は通常別の点である。
Gの原制約復元が受理済みならGを保持する。追加の物理変数KKTを未達でも別経路へ切り替えず、その未達を記録する。
経路選択で目的値を比較しない。全25入力は既見の設計/回帰確認であり、論文の数値再現や独立成功率の測定ではない。
