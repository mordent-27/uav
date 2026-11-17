# 結果の検算

uav/で実行。Python標準ライブラリだけを使い、新しい求解は起動しない。

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s experiments/2026-11-17-r3s-gradient-e2e -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python experiments/2026-11-17-r3s-gradient-e2e/verify.py --check-only
```

run.pyは既存出力があると再起動を拒否する。初回は--freezeで入力を固定・コミット後、同じ数値環境でrun.pyを実行した。
NumPy/SciPy/CasADiは元入口と同じ環境。各子プロセスの起動記録にPythonパス/スレッド設定/コマンドを残した。
analyze.py --statusで進捗を読める。生成済みsummary.jsonへは上書きしない。
完全再実行は別出力先で計画する。原G検証/復元/補助経路の検証は各求解内で新規実行している。

source-index.jsonは既存92入力のhash。inner-source-index.jsonは作業領域に残す内側ログのhash/サイズ。
artifact-index.jsonはGitへ保存する今回の成果物（index自身と内側ログを除く）のhash。
human6文書をtar、repo4文書をrepo-notes/に保存した。
