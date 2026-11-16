# 自作数値コードの検査

Rustは`cargo test`、Pythonは標準の`unittest`を使う。C++のgtestと同じく、
小さく再実行できる回帰テストを先に通してから、実際の最適化を比較する。
Pythonの数値テストにはNumPyが必要。NumPyの入ったPython環境でリポジトリ直下から実行する。

```bash
cargo test -j8
python -m unittest discover -s scripts -p 'test_*.py' -v
```

2026-11-16時点でRust11件（前回）、Python34件が通過。
使用したPython環境と実行記録は[直近の受理判定診断](experiments/2026-11-16-tr-acceptance/REPORT.md)に保存している。
通常の単体テストは900入力の求解を起動しない。

## 今回追加したTRの契約

[テスト](scripts/test_trust_region.py)は[修正版](scripts/trust_region.py)に対し、次を調べる。

- 指定半径を超えず、境界解は境界上にある。
- 正定値の内点/境界、負曲率、hard caseで既知解と一致する。
- 特異行列・重複/近零固有値・ゼロ勾配/半径を扱える。
- モデル値がゼロステップより悪くならず、TR部分問題の大域最適性の証明条件を満たす。
  具体的には非負のシフト、シフト後行列の半正定値性、停留性、相補性を検査する。
- 座標を直交回転しても解が対応する。
- 固定seedの2次元32例を、境界16384方向の独立な探索とも比較する。
  最適性条件と併用し、境界サンプルだけで内点最適性を保証しない。

旧実装の境界ミスは、同じ回帰テストを旧関数へ適用すると失敗することを確認済み。
失敗すること自体を確認するコマンドは次のとおり。

```bash
UAV_TEST_TR_IMPL=legacy python scripts/test_trust_region.py TestTrustRegion.test_regression_nonzero_lowest_component -v
```

期待される終了コードは1。通常テストではこの環境変数を設定しない。
修正版は過去実験のコードを変更せず、新しい診断から利用する。

## 単体テストから実験へ進む順序

1. バグを最小例にし、旧実装で落ちるテストを作る。解を再実装しただけの期待値ではなく、解析解・物理条件・最適性条件を使う。
2. 修正後に単体テストを通す。今回のRust/他Pythonテストも合わせて確認する。
3. 点・乗数・ペナルティを固定した少数例で、修正した一因子だけを比較する。
4. 全入力/受理点を元カーネルで再評価し、判定を独立に照合してから広い評価を行う。

今回の実問題比較では12点とTRの全52試行を再検査した。
単体テスト通過は、有限差分Hessianの正確さ、全条件数での保証、外側ALの収束、論文の数値再現とは別である。

## 次に補強する場所

| 対象 | 現状 | 次の検査 |
|---|---|---|
| TR部分問題 | 新規11テストと2状態の半径監査 | 発見例を回帰ケースへ追加 |
| 受理判定・半径更新 | 新規11テストと保存52試行で既存の採否/半径を再現 | 値差・方向微分・Hessianモデルの尺度を照合。定数への依存と非単調な勾配fallbackも既存仕様として明記 |
| AL/PHRと微分 | Rustの小問題・勾配照合、別実験の固定状態診断 | 活性切替の両側/境界と大小rhoを明示した数理契約 |
| 物理モデル・返却方針 | Rustの電池/モデル、Pythonの修復・解保持・G優先の既存テスト | 新しい失敗が見つかった箇所に最小反例を追加 |

テスト項目を増やすこと自体を目的にせず、収束診断で疑わしくなった計算と、結果の解釈を左右する契約を優先する。

受理判定は[scripts/tr_acceptance.py](scripts/tr_acceptance.py)、テストは[scripts/test_tr_acceptance.py](scripts/test_tr_acceptance.py)。
既存規則が目的値増加を許す場合や、定数加算で分岐が変わる場合も、隠さずテストで可視化している。
これらの通過は、その仕様が望ましいことの証明ではない。変更時は独立の改善比較を行う。

## AL値差の内訳計算

[固定点精度診断](experiments/2026-11-16-directional-precision/REPORT.md)の内訳計算には、
解析的な二次問題・PHR切替・ゼロ変化・線形制約の丸め増幅の5テストを追加した。
通常のscriptsの34件とは別に、NumPy環境で次を実行する。

```bash
python experiments/2026-11-16-directional-precision/test_ledger.py -v
```

これらは内訳計算の契約を調べるテストで、元カーネルの倍精度評価が微小幅まで正確という保証ではない。
次は線形上下限の差と電池写像の差を、解析例/高精度参照と照合して補強する。

## 電池・線形上下限のDecimal参照

[独立参照](experiments/2026-11-16-component-reference/REPORT.md)の充電恒等性、CC直線、CV指数、符号付き逆写像、
PHR差分、制約配置/上下限の既知値、指数上限の7テストが通過した。標準ライブラリだけで実行できる。

```bash
python experiments/2026-11-16-component-reference/test_reference.py -v
```

実データ14点では80/100桁の成分値差も照合した。他の制約や勾配まで高精度化したという保証ではない。
今後、タスクを含む参照を作る場合は、9桁に丸められたJSON座標を全精度入力として使わず、元seedから全桁で再構成する。

## 全制約のDecimal参照と微小摂動の回帰検査

[全制約参照](experiments/2026-11-16-full-reference/REPORT.md)は、電池の7検査を再利用し、
psiの境界、負冪minの解析解/同次性、全制約の既知値、速度符号、AL差分、Decimal摂動保持の計14検査を通した。

```bash
python -m unittest discover -s experiments/2026-11-16-full-reference -p 'test_*.py' -v
```

微小摂動が途中のfloat変換で消えるミスを実データ評価前に検出した。失敗ログと修正後のログを保持している。
参照入力のタスク座標は元のRust生成器から全桁で書き出して保存し、AL値差/方向微分を80/100桁と別プロセスで照合した。
方向微分3本の一致は、全勾配や求解性能の保証とは区別する。

## 全勾配と共通の内側求解ループ

[評価精度の内側比較](experiments/2026-11-16-precise-inner/REPORT.md)には、参照14件に加え、
全勾配の二次式、大定数と微小勾配、期限、共通TRの二次問題を追加した。NumPy環境で計19件が通過。

```bash
python -m unittest discover -s experiments/2026-11-16-precise-inner -p 'test_*.py' -v
```

実問題では206成分を80/100桁と2幅で照合してから4内側求解を実施し、全入力/受理8点を100桁で再検査した。
高精度にしても大きい例は未収束。テストと到達精度、2ノルムと∞ノルム、時間切れを分けて記録している。

## 低曲率方向と点の丸めの診断

[低曲率方向/点の丸め](experiments/2026-11-16-curvature-rounding/REPORT.md)には、Decimal点の素通し、binary64へ丸めない摂動、
2階差分と二次式のHessian作用の既知解、pinvの打切りと射影、二次式でのNewton 1回到達、最近点への丸め（偶数丸め）、
丸め下限の手計算、step長のulp換算、分類規則の10件がある。計測前に通過した。

```bash
python -m unittest discover -s experiments/2026-11-16-curvature-rounding -p 'test_*.py' -v
```

`precise-inner`の参照モジュールは、他の実験フォルダの同名ファイルと取り違えないよう、ファイルの場所を指定して読む。
初回の読込みで別実験の`curvature.py`を拾ったため、モジュール名を`lowcurv.py`へ変えて計測前に直した。
実データでは判定に使う勾配と曲率を別プロセスで100桁再計算した。`posthoc.py`は計画外の事後診断で、単体検査の対象外。

## 折れ目の片側問題と格子探索

[折れ目の両側/丸め下限](experiments/2026-11-16-kink-sides/REPORT.md)には、片側ALの各側での一致とs=0での値/勾配の連続、
共有評価の勾配と`precise-inner`の一致、一次元の区分二次での側の選択、格子の座標走査、二進の桁上がりをまたぐ格子移動、判定規則の7件がある。

```bash
python -m unittest discover -s experiments/2026-11-16-kink-sides -p 'test_*.py' -v
```

格子の検査は当初、2のべき乗の点では下向きの間隔が半分になることを見落として失敗した。走査後に実際の移動量でモデル残差を再計算するよう、計測前に直した。
`posthoc_battery.py`は計画外の事後診断で、単体検査の対象外。

## 切替をまたぐ座標の規則と行列の置き換え

[切替をまたがないHessian](experiments/2026-11-16-switch-hessian/REPORT.md)には、CC/CV切替までの余裕の手計算と対象外の区間、
切替をまたぐ座標の規則の境界、行と列の置き換えと対称化・置き換えない成分の不変、曲率のゲートの5件がある。

```bash
python -m unittest discover -s experiments/2026-11-16-switch-hessian -p 'test_*.py' -v
```

書き始めの検査には矛盾した行が残っており、期待値を既定の28桁で計算していたため1件失敗した。計測前に書き直して80桁で計算した。
実データでは作り直した2列を別プロセスで再計算してビット単位で一致させ、判定に使う4点の勾配を100桁で再計算した。

## 片側差分Hessianの一因子比較

[片側差分Hessianの内側比較](experiments/2026-11-16-switch-onesided/REPORT.md)には、合成の区分二次関数で中央差分が両側の平均・片側差分が点の側の値になること、
該当なしでHがビット単位で一致すること、向きの選び方の4件がある。

```bash
python -m unittest discover -s experiments/2026-11-16-switch-onesided -p 'test_*.py' -v
```

書き始めの検査は差し替えない成分を1と厳密比較して失敗したので、旧方式の値と比べるよう計測前に直した。
初回の検証は対照の軌道をtraceの文字列で比べ、各行の経過秒の違いで失敗した（`verification-attempt01.log`）。経過秒を除いた受理点で比べて再実行した。

## 止まったTR反復の再生

[止まった試行の再生](experiments/2026-11-16-stuck-trials/REPORT.md)には、合成の二次問題で再生ループが`inner.py`の`solve`と同じ試行順・判定になること、
半径が潰れるまで拒否が続く例、比と判定、相対差の4件がある。

```bash
python -m unittest discover -s experiments/2026-11-16-stuck-trials -p 'test_*.py' -v
```

Decimalの参照は、nativeと同じ問題（全桁のタスク座標）で作り、現在点の値の相対差1e-12で事前に照合する。9桁のJSONタスクでは照合に落ちる。
再検証は第1回、Decimal 80桁、Decimal 100桁の3通りで再生をやり直し、全試行の記録と一致させた。

## 受理規則と停止基準を切り替える内側ループ

[受理規則と停止基準の2×2](experiments/2026-11-16-accept-stop/REPORT.md)には、旧方式のときに`inner.py`の`solve`と試行列・結果まで一致すること、
正確な実減少の受理規則の境界、大きな定数を含む値でも収束すること、丸め下限の停止基準の式と停止の5件がある。

```bash
python -m unittest discover -s experiments/2026-11-16-accept-stop -p 'test_*.py' -v
```

実データでは旧方式の受理点が前回の記録と完全に一致することも確かめた。

## 外側ALの段階ループ

[外側ALでの比較](experiments/2026-11-16-outer-b1/REPORT.md)には、`r2b-coarse/run.py`の段階ループを写した`stage.py`について、
合成のAL問題での乗数更新と合格判定、rhoの増加規則、内側の時間切れで乗数を更新しないことの3件がある。

```bash
python -m unittest discover -s experiments/2026-11-16-outer-b1 -p 'test_*.py' -v
```

実データでは全外側行の乗数更新・指標・rhoの規則を前の行の文脈から別プロセスで再計算し、ビット単位で一致させた。内側ログは大きいので管理外にし、hashを残した。

## 外側停滞の打ち切り規則

[外側停滞の停止基準](experiments/2026-11-16-outer-stall/REPORT.md)には、違反一定で2K行目に成立、速く下がると不成立、許容以下で不成立、
rhoが上限でない行を含むと不成立、合格前の成立を誤停止と数えることの5件がある（標準ライブラリのみ）。

```bash
python3 -m unittest discover -s experiments/2026-11-16-outer-stall -p 'test_*.py' -v
```

実データは保存済みの外側ログ38本の再生だけで、別プロセスで再計算して一致させた。
