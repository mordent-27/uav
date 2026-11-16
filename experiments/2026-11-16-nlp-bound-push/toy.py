"""API preflight only, not one of the four diagnostic cases."""
import json
from pathlib import Path
import casadi as ca
from observe import FirstPoint

BASE=Path(__file__).resolve().parent
assert not (BASE/'toy.json').exists()
x=ca.SX.sym('x');rows=[]
for arm,push in [('baseline',None),('small_push',1e-8)]:
    observer=FirstPoint('toy_'+arm,1,1)
    opts=dict(print_time=False,iteration_callback=observer,ipopt=dict(print_level=0,sb='yes',max_iter=40))
    if push is not None:opts['ipopt']['bound_push']=push
    solver=ca.nlpsol('toy_solver_'+arm,'ipopt',dict(x=x,f=x*x,g=x),opts)
    answer=solver(x0=0.,lbx=0.,ubx=1.,lbg=0.,ubg=0.)
    assert observer.point is not None
    rows.append(dict(arm=arm,provided=0.,observed=float(observer.point[0]),status=solver.stats()['return_status']))
assert rows[0]['observed']>rows[1]['observed']
(BASE/'toy.json').write_text(json.dumps(dict(interface_only=True,rows=rows),indent=2)+'\n')
print(json.dumps(rows))
