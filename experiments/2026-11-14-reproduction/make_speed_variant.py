"""Generate a smooth, strictly equivalent scaling of the squared speed inequality."""
from pathlib import Path
import difflib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
source=(ROOT/'src/model.rs').read_text()
old='''            let wt = w.ineq(k, d[0] * d[0] + d[1] * d[1] - v2 * s * s.abs());
            self.add_r(grad, k + 1, 2.0 * wt, d);
            self.add_r(grad, k, -2.0 * wt, d);
            grad[lay.s(k)] -= 2.0 * wt * v2 * s.abs();'''
new='''            // Positive smooth denominator: same feasible set at every x.
            // On the speed boundary the derivative has distance rather than distance^2 scale.
            let numerator = d[0]*d[0]+d[1]*d[1]-v2*s*s.abs();
            let rlen = (d[0]*d[0]+d[1]*d[1]+sm.delta*sm.delta).sqrt();
            let vlen = (v2*s*s+sm.delta*sm.delta).sqrt();
            let denominator = rlen+vlen;
            let wt = w.ineq(k, numerator/denominator);
            let wr = wt*(2.0/denominator-numerator/(denominator*denominator*rlen));
            self.add_r(grad, k+1, wr, d);
            self.add_r(grad, k, -wr, d);
            grad[lay.s(k)] += wt*(-2.0*v2*s.abs()/denominator
                -numerator*v2*s/(denominator*denominator*vlen));'''
assert source.count(old)==1
changed=source.replace(old,new)
(HERE/'speed-model.rs').write_text(changed)
(HERE/'speed.diff').write_text(''.join(difflib.unified_diff(source.splitlines(True),changed.splitlines(True),
                                                        fromfile='src/model.rs',tofile='speed-model.rs')))
bridge=(HERE/'bridge.rs').read_text()
assert bridge.count('#[path = "../../src/model.rs"] mod model;')==1
(HERE/'bridge-speed.rs').write_text(bridge.replace('#[path = "../../src/model.rs"] mod model;',
                                                  '#[path = "speed-model.rs"] mod model;'))
