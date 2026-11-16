# 打ち切り規則の端から端までの比較

| 入力 | G | 入口 | 経路 | stage13停止 | 外側 | g_case秒 | 総秒 | 返却点sha一致 | R3と一致 | 判定 |
|---|---|---|---|---|---:|---:|---:|---|---|---|
| tau1-seed1000002 | 不合格 | 対照 | fallback | outer_limit | 600 | 18.0 | 22.2 | False | False |  |
| tau1-seed1000002 | 不合格 | 規則 | fallback | stalled | 45 | 8.3 | 11.7 | False | False | result_changed |
| tau2-seed2000002 | 不合格 | 対照 | fallback | outer_limit | 600 | 60.3 | 65.8 | True | True |  |
| tau2-seed2000002 | 不合格 | 規則 | fallback | stalled | 45 | 33.3 | 39.2 | True | True | same_result_faster |
| tau3-seed3000000 | 不合格 | 対照 | fallback | outer_limit | 600 | 92.4 | 100.2 | False | False |  |
| tau3-seed3000000 | 不合格 | 規則 | fallback | stalled | 45 | 66.9 | 76.2 | False | False | result_changed |
| tau4-seed4000000 | 不合格 | 対照 | fallback | timeout | 494 | 316.6 | 324.2 | False | False |  |
| tau4-seed4000000 | 不合格 | 規則 | fallback | stalled | 45 | 190.5 | 197.2 | False | False | result_changed |
| tau4-seed4000001 | 不合格 | 対照 | fallback | outer_limit | 600 | 386.4 | 390.1 | False | False |  |
| tau4-seed4000001 | 不合格 | 規則 | fallback | stalled | 46 | 225.0 | 228.3 | False | False | result_changed |
| tau4-seed4000002 | 不合格 | 対照 | fallback | timeout | 497 | 297.6 | 308.6 | False | False |  |
| tau4-seed4000002 | 不合格 | 規則 | fallback | stalled | 45 | 148.1 | 155.8 | False | False | result_changed |
| tau5-seed5000001 | 不合格 | 対照 | fallback | timeout | 126 | 785.4 | 791.2 | False | False |  |
| tau5-seed5000001 | 不合格 | 規則 | fallback | stalled | 45 | 700.5 | 707.0 | False | False | result_changed |
| tau6-seed6000000 | 不合格 | 対照 | fallback | timeout | 88 | 551.7 | 568.0 | False | False |  |
| tau6-seed6000000 | 不合格 | 規則 | fallback | stalled | 45 | 496.8 | 510.2 | False | False | result_changed |
| tau6-seed6000002 | 不合格 | 対照 | fallback | timeout | 388 | 795.0 | 806.0 | False | False |  |
| tau6-seed6000002 | 不合格 | 規則 | fallback | stalled | 45 | 726.9 | 737.6 | False | False | result_changed |
| tau2-seed2000001 | 合格 | 対照 | G | kkt | 4 | 25.0 | 26.4 | False | False |  |
| tau2-seed2000001 | 合格 | 規則 | G | kkt | 4 | 23.8 | 25.1 | False | False | result_changed |
| tau6-seed6000001 | 合格 | 対照 | G | kkt | 159 | 541.6 | 542.5 | False | False |  |
| tau6-seed6000001 | 合格 | 規則 | G | kkt | 159 | 529.4 | 530.3 | False | False | result_changed |
