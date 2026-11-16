# 外側ALの内側を替えたstage13

| 入力 | 方式 | 停止 | 外側 | 合格 | 共通KKT最大 | 物理KKT最大 | 目的値 | 最終rho | 秒 | 内側の停止 | Decimal評価 |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| tau6-seed6000000 | R3記録 | timeout | 115 | False | 3.344e+01 | 1.204e+03 | 2.680979625 | 1e+08 | 120.0 | — | — |
| tau6-seed6000000 | L | timeout | 115 | False | 3.344e+01 | 1.204e+03 | 2.680979625 | 1e+08 | 120.0 | {'converged': 3, 'stuck': 105, 'max_iter': 7} | 0 |
| tau6-seed6000000 | A0 | timeout | 132 | False | 3.324e+04 | 4.670e+05 | 2.914697668 | 1e+08 | 120.0 | {'converged': 3, 'stuck': 127, 'max_iter': 2} | 0 |
| tau6-seed6000000 | B1 | timeout | 62 | False | 1.646e+01 | 5.926e+02 | 2.640793859 | 1e+08 | 120.0 | {'converged': 4, 'converged_floor': 53, 'max_iter': 5} | 7183 |
| tau6-seed6000002 | R3記録 | timeout | 273 | False | 2.527e-01 | 9.097e+00 | 2.330322084 | 1e+08 | 120.0 | — | — |
| tau6-seed6000002 | L | timeout | 471 | False | 4.393e-01 | 1.582e+01 | 2.360889290 | 1e+08 | 120.0 | {'converged': 4, 'stuck': 467} | 0 |
| tau6-seed6000002 | A0 | timeout | 402 | False | 3.743e-01 | 1.347e+01 | 2.351842993 | 1e+08 | 120.0 | {'converged': 5, 'stuck': 397} | 0 |
| tau6-seed6000002 | B1 | timeout | 425 | False | 3.960e-01 | 1.425e+01 | 2.355013199 | 1e+08 | 120.0 | {'converged': 4, 'converged_floor': 420, 'max_iter': 1} | 8086 |

| 入力 | 規則（B1対A0） | TR修正（A0対L） |
|---|---|---|
| tau6-seed6000000 | better | worse |
| tau6-seed6000002 | mixed | mixed |
