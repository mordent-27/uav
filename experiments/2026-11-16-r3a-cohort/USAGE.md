# 固定900入力の分割実行

targets.jsonはtau=1..9各100入力、900 IDと順序を事前に固定した集合である。
driver.pyは1回につき固定バッチ1つ・最大8入力だけを実行する。
全900件を自動で連続実行するコマンドではない。

uav/から、NumPy/SciPy/CasADiを使えるPythonと1スレッドの数値環境で次のように起動する。
具体的なPython/PYTHONPATHはbatches/000/launch-record.jsonとattempt000.jsonを参照する。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-16-r3a-cohort/driver.py
```

次の未着手バッチを選ぶ。バッチ000が完了した状態では001を開始する。
`--batch 1`でも指定でき、`--limit 1`から8で一度の起動件数を減らせる。
既に完了した入力は失敗でも解き直さず、同じIDの出力を上書きしない。
数値コード・targets・driverのhashがprotocolと変わった場合は起動を拒否する。
過去のR2h/R2iコードは変更せず、今回のsolve.pyは許容tauと出力先だけを広げている（entry-diff.txt）。

resultが無い部分出力があれば、残存プロセスの監査まで全新規起動を拒否する。
プロセスが無いことを確認した後、interruptions/<case>.jsonへ
`confirmed_no_live_processes: true`、監査日時、理由と根拠を記録すれば、そのIDは中断のまま残して後続へ進める。
部分出力の削除、同じIDの再試行、途中反復の再開による時間予算のリセットはしない。
driver.lockによって同時driver/全ログ検証の重複実行を拒否する。

```bash
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-16-r3a-cohort/aggregate.py
```

途中集計は計画/着手/終端/未実行を分ける。未実行を失敗や成功へ数えない。
全完走前の目的値中央値は少数の観測値であり、各100本の最終分布ではない。
共通/追加物理KKTはAL終点、原実行可能性/固定分岐KKTは別の返却点の指標である。

バッチごとの実行・検証・来歴はbatches/000等へ保存する。検証対象はUAV_R3_BATCH=000で指定する。
reverify.pyはそのバッチで実行したG/直接開始/初期化を、求解なしで再評価する。
audit_outputs.pyは同じバッチの出力だけをRustで照合する。
diagnose_restoration.pyは不受理復元の保存点/乗数を再評価し、新しいNLPは解かない。
capture.pyは文書が確定した後に一度使い、バッチ内へ進捗・ROADMAP等・human6文書のsnapshot/hashを保存する。
rootのsummary/comparison/REPORTは更新する途中集計で、バッチごとの確定記録とは区別する。

再開に必要な共有ライブラリは/tmp/uav-fidelity-{original,speed}.so。
runtime-evaluators.tar.gzに今回の2バイナリを保存しているため、消失時はhashを確認して同じパスへ戻せる。
Linux x86_64の保存バイナリであり、他の環境での互換性を保証しない。
内側ログ本体はローカルに保持し、Gitには各バッチのlocal-inner-manifest.jsonを残す。
Git cloneだけでは内側ログ本体は得られない。
