# この実行で使った既存環境

システムのPython 3.14にはSciPyがなかったため、既存キャッシュのPython 3.12と
site-packagesを読み取り専用で使った。依存パッケージは新規インストールしていない。
既存venvのpythonリンク先が不在だったので、基底の実行ファイルを直接指定した。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/home/mordent/.cache/uv/environments-v2/sys-id-chirp-1714f8f5f4d59f0e/lib/python3.12/site-packages \
/home/mordent/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python \
experiments/2026-11-14-reproduction/independent_al.py --backend scipy-bfgs \
--library /tmp/uav-reproduction-speed.so --out /tmp/uav-diagnostic.json
```

IPOPT参照の実行時だけ、PYTHONPATHの先頭に
`/home/mordent/.cache/uv/archive-v0/IH8olt7ky0AxR5WV:`を加えた。
グラフ生成では`MPLCONFIGDIR=/tmp/uav-reproduction-matplotlib`も指定する。
このパスは実行した環境の記録であり、他環境で同じキャッシュ配置を要求するものではない。
通常のPython環境に同じバージョンのパッケージが入っていれば、上記の環境指定は不要。
