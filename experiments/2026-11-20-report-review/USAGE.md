# 再確認と再生成

`uav/`をカレントディレクトリとする。数値検算はNumPyが必要。新規の最適化は実行しない。

```bash
python experiments/2026-11-20-report-review/check_numbers.py --check-only
python experiments/2026-11-20-report-review/build_report.py
```

ビルドはuplatexとdvipdfmxを使用し、参照を確定するため2回コンパイルする。A4・8ページ以内とTeXの警告を検査してからhuman/report.pdfを更新する。図は作成済みPDFを使う。図を再生成する場合はmatplotlibと日本語フォントNoto Sans CJK JPを利用し、`python ../human/fig/make_figs.py`を実行する。

今回の環境ではNumPy/matplotlibのある既存uvキャッシュをPYTHONPATHへ追加した。検算や作図の条件ではなく実行環境の指定であり、新規パッケージのインストールはしていない。最終PDFのコンパイルは既存の標準PythonとTeXで行った。

baseline/は採点対象の原版、revised/は最終human/成果物のコピー。作図コードのパス解決はhuman/fig/で実行する配置が前提なので、保存コピーを使う場合は元の配置へ戻す。report.tex.diffとmake_figs.py.diffで変更を追える。qa/には最終コンパイル記録と全8ページのレンダリングを保存した。

source-index.jsonとnumeric-input-index.jsonは入力の固定用。artifact-index.jsonは自分自身を除くこのディレクトリの最終成果物のSHA256。human/の提出稿はuav/のGitの外にあるため、コミットにはrevised/を含めて同じ内容を保管する。
