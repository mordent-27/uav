"""Add exact revisit constraints to the unchanged common fixed-assignment model."""
import copy
import importlib.util
import json
import math
from pathlib import Path
from time import monotonic
import casadi as ca
import numpy as np
from verify_point import check, replay, carriers

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('frozen_carrier_branch',ROOT/'experiments/2026-11-18-carrier-nlp/solve.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
TARGETS=old.TARGETS
INDEX={p['case']:p for p in json.loads((ROOT/'experiments/2026-11-18-r3s-carrier/source-index.json').read_text())['points']}


def load(case):
    return json.loads((ROOT/INDEX[case]['path']).read_text())


class ReducedBranch(old.Branch):
    def __init__(self,d):
        super().__init__(d,False)
        p=self.p;duration=[self.v[self.nr+self.ns+k]/p['v_d'] for k in range(self.ns)]
        pairs=[];extra=[]
        for j in sorted({m for m in self.modes if m>=0}):
            seg=[k for k,m in enumerate(self.modes) if m==j]
            for a,b in zip(seg,seg[1:]):
                if b==a+1:
                    continue
                pairs.append((j,a,b))
                extra.append(old.dist_le(self.pos[b],self.pos[a+1],p['v_c']*sum(duration[a+1:b])))
        self.pairs=pairs;self.revisit=ca.vertcat(*extra) if extra else ca.SX.zeros(0,1)
        self.constraints=ca.vertcat(self.constraints,self.revisit);self.mi+=len(extra)
        self.evaluate=ca.Function('reduced_values',[self.v],[self.objective,self.constraints,
                            ca.gradient(self.objective,self.v),ca.jacobian(self.constraints,self.v)])
        self.eval_revisit=ca.Function('revisit',[self.v],[self.revisit])


def make_branch(d,method):
    clean=copy.deepcopy(d);clean.pop('carrier_positions',None)
    return ReducedBranch(clean) if method=='R' else old.Branch(clean,True)


def solve(branch,method,reference):
    start=monotonic();d,result,raw=branch.solve();total=monotonic()-start
    if method=='R':
        d['carrier_positions']=carriers(d)
    audit=check(d,reference)
    result.update(accepted=audit['accepted'],method=method,independent=audit,total_call_seconds=total)
    d['diagnostic']['method']='fixed-assignment exact NLP: '+('eliminate q with R' if method=='R' else 'explicit q')
    d['diagnostic']['paper_algorithm']=False
    return d,result,raw


def construct_fixed_positions(reference):
    """Sufficient construction, not optimization and not an infeasibility test."""
    d=copy.deepcopy(reference);d.pop('carrier_positions',None)
    p=d['phys'];r=d['solution']['r'];m=d['modes'];tr=d['solution']
    s=[p['s_max'] if mode>=0 else max(p['s_min'],math.dist(r[k+1],r[k])/p['v_d']+2e-12) for k,mode in enumerate(m)]
    for j in sorted({mode for mode in m if mode>=0}):
        segments=[k for k,mode in enumerate(m) if mode==j]
        for a,b in zip(segments,segments[1:]):
            if b==a+1:
                continue
            missing=math.dist(r[b],r[a+1])/p['v_c']+2e-12-sum(s[a+1:b])
            if missing>0:
                s[a+1]+=missing
    tr['s']=s;tr['c']=[s[k] if mode>=0 else 0. for k,mode in enumerate(m)];tr['e']=replay(d)
    d['carrier_positions']=carriers(d);d['stages']=[]
    d['diagnostic']=dict(method='fixed positions; maximum charging; extend discharge for R',paper_algorithm=False,global_optimality=False)
    return d,check(d,reference)
