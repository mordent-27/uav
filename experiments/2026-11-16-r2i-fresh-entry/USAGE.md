# R2iの実行と読み方

対象・上限・採用規則は[PLAN.md](PLAN.md)と[targets.json](targets.json)で求解前に固定した。
driver.pyはR2h/solve.pyのsolve_caseへ空の再利用エントリと今回の出力先を渡すだけで、数値解法を変更していない。
必要なPython/ライブラリ・実際のコマンドはlaunch-record.jsonとexecution.json、各子プロセスはlogs/に記録した。

既存の出力を上書きしないので、driver.pyを同じ場所へ再実行すると拒否される。
今回の1入力を再実行する場合は、NumPy/SciPy/CasADiと評価共有ライブラリを準備し、リポジトリuav/から未使用出力先を指定する。
この入力はR2hのcatalogに含まれないため、以下のコマンドもキャッシュなしでGから実行する。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-16-r2h-g-first/solve.py \
  --case tau3-seed3002 --out-root experiments/r2i-replay-example
```

評価共有ライブラリは`/tmp/uav-fidelity-{original,speed}.so`で、hashはpreflight.jsonにある。
Pythonの実行環境の具体的な指定はlaunch-record.jsonを参照する。
入力/出力の構造はR2hの[USAGE.md](../2026-11-16-r2h-g-first/USAGE.md)と同じである。

- inputs/：全精度の元初期点と問題データ。
- cases/G/、cases/fallback/：今回新たに実行したALと復元。G受理時にはfallbackを実行しない。
- initializations/：G未受理時の入力監査と、必要な場合だけ構成・原制約NLP。
- evaluations/：保存証明/物理点の再評価。再最適化を追加する処理ではない。
- runs/：経路、各指標、返却点。returned_point_smoothing_kkt_not_inferredを保つ。
- summary.json、comparison.md：固定8例すべての事後集計。
- reverification*：実行した全AL/初期化の保存状態を、求解なしで再評価する記録。
- output-verification.json、rust-validation.log：Rustによる保存値/原制約等の照合。
- provenance.json：固定版とのhash一致、再利用なしの根拠、実行版、human文書アーカイブのhash。
- local-inner-manifest.json：Gitから除外してローカルに保持した内側ログのhash。Git cloneにはログ本体を含まない。

原制約/固定分岐KKTを測る返却点と、平滑化KKTを測るAL終点は別の点である。
Gの追加物理KKT未達だけを理由に補助経路を実行せず、原制約復元の受理を保持する。
新規入力8例の小規模確認であり、論文の各100本・入力条件一致・大域最適性の再現を意味しない。

現行入口の入力検査はtau=1,3,5,7に限定されている。
各100本へ広げる次段階では、tau=1..9を受け付ける入口と900入力の事前固定・分割再開・費用計測を別に用意する必要がある。
