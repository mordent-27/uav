| 固定AL | 内側法 | 内側勾配 | 反復 | 秒 | 停止理由 |
|---|---|---:|---:|---:|---|
| after-raise | newton | 1.371e-01 | 300 | 8.554 | max_iter |
| after-raise | rust | 2.461e-01 | 2000 | 0.269 | max_iter |
| after-raise | scipy-bfgs | 1.340e-01 | 1087 | 0.944 | Desired error not necessarily achieved due to precision loss. |
| after-raise | scipy-lbfgs | 1.735e-01 | 2000 | 0.459 | STOP: TOTAL NO. OF ITERATIONS REACHED LIMIT |
| after-raise | stable-bfgs | 1.514e-01 | 1273 | 1.083 | Desired error not necessarily achieved due to precision loss. |
| before-raise | newton | 6.649e-03 | 300 | 8.690 | max_iter |
| before-raise | rust | 1.281e-02 | 2000 | 0.216 | max_iter |
| before-raise | scipy-bfgs | 1.001e-03 | 484 | 0.456 | Desired error not necessarily achieved due to precision loss. |
| before-raise | scipy-lbfgs | 1.580e-02 | 2000 | 0.454 | STOP: TOTAL NO. OF ITERATIONS REACHED LIMIT |
| before-raise | stable-bfgs | 2.471e-06 | 481 | 0.570 | Desired error not necessarily achieved due to precision loss. |
| stalled | newton | 2.411e-06 | 300 | 8.099 | max_iter |
| stalled | newton-decomposed | 9.757e-07 | 17 | 0.554 | stuck |
| stalled | rust | 2.028e-05 | 3 | 0.011 | line_search |
| stalled | scipy-bfgs | 1.762e-05 | 1 | 0.008 | Desired error not necessarily achieved due to precision loss. |
| stalled | scipy-lbfgs | 1.950e-05 | 1 | 0.002 | CONVERGENCE: RELATIVE REDUCTION OF F <= FACTR*EPSMCH |
| stalled | stable-bfgs | 1.751e-05 | 1 | 0.010 | Desired error not necessarily achieved due to precision loss. |
