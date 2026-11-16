# R3sの実行手順（固定900の残り876件）

R3と同じ900件・順序・予算で、G経路のstage13に外側停滞の打ち切り規則を入れた入口で解く。条件は[PLAN.md](PLAN.md)。
R3のバッチ000〜002（24件）は旧入口の結果を引き継ぐので解き直さない。次に解くのはバッチ003から。

## 実行

`uav/`から実行する。1バッチは最大8件・8並列で、R3では1バッチ数分〜13分ほどだった。876件は110バッチで、R3の見積もり（残り約16.5時間）から、
規則で約2割短くなる見込み（11状態の比較で18%短縮。全体でも同じだけ短くなるとは限らない）。

```bash
cd ~/robotech/3A/optimization/uav
# 1バッチだけ（解く→再評価→Rust照合→途中集計）
experiments/2026-11-16-r3s-cohort/run_batches.sh 1
# まとめて（例：10バッチ＝80件）。失敗した段階でその場で止まる
nohup experiments/2026-11-16-r3s-cohort/run_batches.sh 10 > experiments/2026-11-16-r3s-cohort/run.log 2>&1 &
# 残り全部
nohup experiments/2026-11-16-r3s-cohort/run_batches.sh 110 > experiments/2026-11-16-r3s-cohort/run.log 2>&1 &
```

- Pythonと環境は`UAV_PYTHON`・`UAV_PYTHONPATH`で替えられる（既定はR3と同じuvのPython 3.12）。
- 評価ライブラリ`/tmp/uav-fidelity-{original,speed}.so`が必要。`run_batches.sh`は各バッチの前に`restore_evaluators.py`を呼び、
  無ければこのフォルダの`runtime-evaluators.tar.gz`から取り出してprotocolのhashと照合してから置く。hashの違うファイルが既にあれば上書きせずに止まる。
  実行する環境の`/tmp`へ書き込めることが必要（2026-11-16の最初の起動は、実行した環境の`/tmp`にライブラリが無く、求解前の照合で止まった）。
- 他の数値計算と同時に走らせない（`driver.lock`で重複起動は拒否されるが、別の実験の計算は止められない）。8並列の時間予算なので、負荷が増えると時間切れの位置が変わる。

## 途中で止めたいとき

`nohup ... &`で起動した場合、Ctrl+Cは届かない。止め方は次の3通り（上ほど安全）。

1. **次のバッチの前で止める**：`touch experiments/2026-11-16-r3s-cohort/STOP`。実行中のバッチは解く→再評価→Rust照合→途中集計まで終え、次のバッチに入る前に止まる。
   再開は`rm experiments/2026-11-16-r3s-cohort/STOP`してから同じコマンド。（2026-11-16 23:15 UTCより前に起動したループは古い版で、STOPを見ない。2の方法を使う。）
2. **外側のループだけを止める**：`pgrep -af run_batches.sh`で番号を見て`kill <番号>`（bashだけ。pythonの`driver.py`は止めない）。
   実行中のバッチの`driver.py`は最後まで解いて終わる。その後の再評価・Rust照合は、次に`run_batches.sh`を起動したときに自動で追いつく。
   driverが終わったかは`pgrep -af r3s-cohort/driver.py`で確かめる。終わる前に再起動すると、実行中のバッチの部分出力が見えて起動を拒否される（driverが終われば解消）。
3. **driverごと止める**（Ctrl+C相当）：解きかけの入力に部分出力が残り、次の起動は全て拒否される。
   プロセスが残っていないことを確かめてから、`interruptions/<case>.json`に
   `{"confirmed_no_live_processes": true, "audited_utc": "...", "reason": "...", "evidence": "..."}`を書くと、その入力は「中断」のまま残して後続へ進める。
   部分出力の削除や同じ入力の解き直しはしない（R3と同じ規則）。

再開は、どの場合も同じ`run_batches.sh`を実行すればよい。同じバッチの起動記録とログは上書きされず、`-attempt01`などの番号が付く。
`driver.py`が終わった後の再評価・Rust照合が無いバッチは、起動時に自動で済ませる。

## 終わったら

- `aggregate.py`の途中集計は`summary.json`と`comparison.md`。旧入口の24件（`origin`が`2026-11-16-r3a-cohort`）と規則入りの件は合算されているので、分けて読む。
- 各バッチの来歴（文書のsnapshotとhash）は、文書を確定した後に`UAV_R3_BATCH=NNN python experiments/2026-11-16-r3s-cohort/capture_batch.py`で保存する。
- 900件そろう前の数は各100本の最終分布ではない。返却点を比べるときは復元の経過秒`metrics.seconds`を除く。
