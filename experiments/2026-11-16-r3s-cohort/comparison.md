# R3の途中集計

計画 900、着手 72、終端記録 72、未実行 828。各100本の最終分布ではない。

| tau | 計画 | 着手 | 未実行 | 共通KKT | 追加物理KKT | 最後の復元 | 原実行可能点 | 固定分岐KKT |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 100 | 8 | 92 | 8 | 8 | 8 | 8 | 8 |
| 2 | 100 | 8 | 92 | 8 | 8 | 6 | 8 | 6 |
| 3 | 100 | 8 | 92 | 8 | 8 | 8 | 8 | 8 |
| 4 | 100 | 8 | 92 | 7 | 7 | 7 | 8 | 7 |
| 5 | 100 | 8 | 92 | 8 | 8 | 8 | 8 | 8 |
| 6 | 100 | 8 | 92 | 8 | 8 | 8 | 8 | 8 |
| 7 | 100 | 8 | 92 | 7 | 7 | 7 | 8 | 7 |
| 8 | 100 | 8 | 92 | 8 | 8 | 6 | 8 | 7 |
| 9 | 100 | 8 | 92 | 6 | 2 | 3 | 8 | 4 |

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
| tau1-seed1000003 | finished | G | 0.378843581 | ○ | ○ |
| tau3-seed3000003 | finished | G | 0.764893250 | ○ | ○ |
| tau5-seed5000003 | finished | G | 0.967568638 | ○ | ○ |
| tau7-seed7000003 | finished | fallback | 2.772578401 | ○ | ○ |
| tau2-seed2000004 | finished | fallback | 1.821255266 | ○ | × |
| tau4-seed4000004 | finished | fallback | 1.305171855 | ○ | ○ |
| tau6-seed6000004 | finished | fallback | 3.104970547 | ○ | ○ |
| tau8-seed8000004 | finished | fallback | 2.710431529 | ○ | ○ |
| tau9-seed9000004 | finished | fallback | 6.248408906 | ○ | ○ |
| tau1-seed1000004 | finished | G | 0.325699316 | ○ | ○ |
| tau3-seed3000004 | finished | G | 1.378359272 | ○ | ○ |
| tau5-seed5000004 | finished | fallback | 2.338518873 | ○ | ○ |
| tau7-seed7000004 | finished | fallback | 3.466527248 | ○ | ○ |
| tau2-seed2000005 | finished | G | 0.904913563 | ○ | ○ |
| tau4-seed4000005 | finished | fallback | 2.216683588 | ○ | ○ |
| tau6-seed6000005 | finished | fallback | 3.655502444 | ○ | ○ |
| tau8-seed8000005 | finished | fallback | 3.980779560 | ○ | ○ |
| tau9-seed9000005 | finished | fallback | 3.991574851 | ○ | ○ |
| tau1-seed1000005 | finished | G | 0.295713276 | ○ | ○ |
| tau3-seed3000005 | finished | G | 1.162201558 | ○ | ○ |
| tau5-seed5000005 | finished | fallback | 2.510870651 | ○ | ○ |
| tau7-seed7000005 | finished | G | 2.531384777 | ○ | ○ |
| tau2-seed2000006 | finished | G | 0.722113929 | ○ | ○ |
| tau4-seed4000006 | finished | G | 1.096307788 | ○ | ○ |
| tau6-seed6000006 | finished | fallback | 3.567349759 | ○ | ○ |
| tau8-seed8000006 | finished | fallback | 2.637247266 | ○ | ○ |
| tau9-seed9000006 | finished | fallback | 3.717012503 | ○ | ○ |
| tau1-seed1000006 | finished | fallback | 0.436688359 | ○ | ○ |
| tau3-seed3000006 | finished | G | 1.386327482 | ○ | ○ |
| tau5-seed5000006 | finished | G | 1.137886802 | ○ | ○ |
| tau7-seed7000006 | finished | fallback | 3.558748552 | ○ | ○ |
| tau2-seed2000007 | finished | G | 1.347131535 | ○ | ○ |
| tau4-seed4000007 | finished | fallback | 1.143065664 | ○ | ○ |
| tau6-seed6000007 | finished | fallback | 2.853839781 | ○ | ○ |
| tau8-seed8000007 | finished | fallback | 3.588910092 | ○ | ○ |
| tau9-seed9000007 | finished | fallback | 5.567071804 | ○ | × |
| tau1-seed1000007 | finished | G | 0.361611002 | ○ | ○ |
| tau3-seed3000007 | finished | G | 0.548354743 | ○ | ○ |
| tau5-seed5000007 | finished | G | 1.400147429 | ○ | ○ |
| tau7-seed7000007 | finished | fallback | 4.066958728 | ○ | ○ |
