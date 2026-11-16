# R3の途中集計

計画 900、着手 32、終端記録 32、未実行 868。各100本の最終分布ではない。

| tau | 計画 | 着手 | 未実行 | 共通KKT | 追加物理KKT | 最後の復元 | 原実行可能点 | 固定分岐KKT |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 100 | 3 | 97 | 3 | 3 | 3 | 3 | 3 |
| 2 | 100 | 4 | 96 | 4 | 4 | 3 | 4 | 3 |
| 3 | 100 | 3 | 97 | 3 | 3 | 3 | 3 | 3 |
| 4 | 100 | 4 | 96 | 3 | 3 | 3 | 4 | 3 |
| 5 | 100 | 3 | 97 | 3 | 3 | 3 | 3 | 3 |
| 6 | 100 | 4 | 96 | 4 | 4 | 4 | 4 | 4 |
| 7 | 100 | 3 | 97 | 2 | 2 | 2 | 3 | 2 |
| 8 | 100 | 4 | 96 | 4 | 4 | 3 | 4 | 3 |
| 9 | 100 | 4 | 96 | 2 | 1 | 1 | 4 | 1 |

共通/追加物理KKTはAL終点、原実行可能点/固定分岐KKTは別の返却点。未実行を成功/失敗へ数えない。

| 入力 | 状態 | 採用 | 返却時間 h | 原実行可能点 | 固定分岐KKT |
|---|---|---|---:|---|---|
| tau2-seed2000000 | finished | G | 0.823026052 | ○ | ○ |
| tau4-seed4000000 | finished | fallback | 2.241423704 | ○ | ○ |
| tau6-seed6000000 | finished | fallback | 2.837853030 | ○ | ○ |
| tau8-seed8000000 | finished | fallback | 4.813967875 | ○ | × |
| tau9-seed9000000 | finished | fallback | 5.367104544 | ○ | × |
| tau1-seed1000000 | finished | G | 1.011244979 | ○ | ○ |
| tau3-seed3000000 | finished | fallback | 0.784121621 | ○ | ○ |
| tau5-seed5000000 | finished | G | 2.099442706 | ○ | ○ |
| tau7-seed7000000 | finished | fallback | 2.873110603 | ○ | ○ |
| tau2-seed2000001 | finished | G | 0.381546623 | ○ | ○ |
| tau4-seed4000001 | finished | fallback | 4.085548214 | ○ | × |
| tau6-seed6000001 | finished | G | 1.660048498 | ○ | ○ |
| tau8-seed8000001 | finished | fallback | 3.069872738 | ○ | ○ |
| tau9-seed9000001 | finished | fallback | 6.209341221 | ○ | × |
| tau1-seed1000001 | finished | fallback | 0.590666658 | ○ | ○ |
| tau3-seed3000001 | finished | G | 1.470305508 | ○ | ○ |
| tau5-seed5000001 | finished | fallback | 2.027682659 | ○ | ○ |
| tau7-seed7000001 | finished | fallback | 3.579344816 | ○ | ○ |
| tau2-seed2000002 | finished | fallback | 1.484762701 | ○ | × |
| tau4-seed4000002 | finished | fallback | 1.292384376 | ○ | ○ |
| tau6-seed6000002 | finished | fallback | 2.564306965 | ○ | ○ |
| tau8-seed8000002 | finished | fallback | 2.323579596 | ○ | ○ |
| tau9-seed9000002 | finished | fallback | 4.401428633 | ○ | ○ |
| tau1-seed1000002 | finished | fallback | 0.471146548 | ○ | ○ |
| tau3-seed3000002 | finished | fallback | 1.295272140 | ○ | ○ |
| tau5-seed5000002 | finished | fallback | 1.683170588 | ○ | ○ |
| tau7-seed7000002 | finished | fallback | 6.092679239 | ○ | × |
| tau2-seed2000003 | finished | G | 1.096868701 | ○ | ○ |
| tau4-seed4000003 | finished | G | 1.215446525 | ○ | ○ |
| tau6-seed6000003 | finished | fallback | 3.467359655 | ○ | ○ |
| tau8-seed8000003 | finished | fallback | 3.949821886 | ○ | ○ |
| tau9-seed9000003 | finished | fallback | 9.211305681 | ○ | × |
