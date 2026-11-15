# R2gの記録と再評価

[PLAN.md](PLAN.md)は求解前の規則、[REPORT.md](REPORT.md)は確定した結果、[REPORT_DRAFT.md](REPORT_DRAFT.md)は中断時の下書き。
数値求解は2026-11-15に完了した。再開後は保存済み結果を検証・記録し、解き直していない。

`screening.json`は負電池を条件に対象を選ぶまでの8入力と分母、`screened-inputs/`は選択4入力の全精度状態。
起動コマンドは会話の実際のツール呼出しから[launch-record.json](launch-record.json)へ事後記録した。
求解当日のバージョン文字列は未保存で、`provenance.json`の検証時のバージョンとは区別する。

`regression/`はR2fの21既存結果の再評価。受理済み20点をそのまま保持し、設計例1件は証明で点を返す。
`cases/`は新規4入力の対照/修復側、`evaluations/`は保持規則による各採用結果。
`selected.json`の物理点が、最終ALの平滑化KKT点でもあるとは主張しない。

以下は求解を繰り返さない集計・照合。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/2026-11-15-r2g-incumbent/analyze.py
PYTHONDONTWRITEBYTECODE=1 python3 experiments/2026-11-15-r2g-incumbent/audit_outputs.py
```

Rust照合には`rustc`が必要。ALと保持規則の再評価は、既存のNumPy/CasADiと評価ライブラリを使う。
コマンドと確認範囲はREPORTとprovenanceの`verification_commands`に記録する。
数値状態の再計算は`reverify.py`、保持規則を一時出力先で再計算するのは`recheck_retention.py`。
どちらも新しいNLPを解かず、元の求解出力を上書きしない。

`driver.py`は既存のlogs/への上書きを拒否する。再実行する場合は、版を保存した別の実験先を用意する。
`summary.json`と`comparison.md`は、既見20件・設計例1件・新規4入力の対比較を分けている。
`reverification.json`、`retention-recheck.json`、`output-verification.json`が検証結果。
最後に`capture.py`が依存のhash、外部human文書のスナップショット、保存物の索引を更新する。
大きい内側ログはローカル保存し、`local-inner-manifest.json`にhashを記録する。
