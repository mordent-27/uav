"""Audit original input, preserve it or construct a witness, without solving any NLP."""
import copy
import json
import os
import sys
from time import monotonic
import numpy as np
import helpers as h

sys.path.insert(0,str(h.ROOT/'scripts'))
import repair_initialization as repair


def main():
    h.INIT.mkdir(parents=True,exist_ok=False)
    start=monotonic();m=h.fidelity.Variant('R');y=m.native.y.copy()
    data=copy.deepcopy(m.source);trajectory=h.tr.decode(m,y,m.source)
    data['init']=copy.deepcopy(trajectory);data['solution']=copy.deepcopy(trajectory)
    full=[trajectory['r'][stamp] for stamp in data['task_stamp']]
    assert max(np.linalg.norm(np.array(a)-b) for a,b in zip(full,data['instance']['tasks']))<=1e-9
    data['instance']['tasks']=full
    h.write(h.INIT/'input.json',data)
    m.stage(.0005,12.)
    class Wrap:pass
    w=Wrap();w.m=m
    source=dict(h.state(y,np.zeros(m.me),np.zeros(m.mi),1e4,0),eps=.0005,p=12.,
        **h.assess(w,y,np.zeros(m.me),np.zeros(m.mi)))
    h.write(h.INIT/'original-state.json',source)
    baseline=os.environ.get('UAV_R2F_BASELINE')
    if baseline:
        old=json.loads((h.ROOT/baseline/'source.json').read_text())
        np.testing.assert_array_equal(old['y'],y)
    output,report=repair.repair(data)
    if report['accepted'] and report['action']=='keep_original':
        assert output==data
        report['same_original_y']=True
    elif report['accepted']:
        assert output['modes']==data['modes'] and output['task_stamp']==data['task_stamp']
        fb=h.load_from(h.ROOT/'experiments/2026-11-14-restoration','fixed_branch');fb.build_history(output)
        assert min(output['history']['e'])>=0. and max(output['history']['e'])<=1.
        output['metrics']=dict(objective=sum(output['solution']['s']),init_objective=sum(trajectory['s']),
            converged=False,stamps=m.stamps,seconds=monotonic()-start,**report['final_audit']['original_residuals'])
        output['diagnostic']=dict(method='general input-only geometric and battery construction',paper_algorithm=False)
        output['stages']=[]
        h.write(h.INIT/'witness.json',output)
    report.update(case=h.CASE,seconds=monotonic()-start,baseline_y_verified=bool(baseline),
        native_stamps=m.stamps,native_variables=m.n)
    h.write(h.INIT/'guard.json',report)
    m.close();print(json.dumps(report),flush=True)


if __name__=='__main__':main()
