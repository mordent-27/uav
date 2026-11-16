"""Replay one TR iteration of precise-inner's loop at a fixed point without moving it. No optimizer is run."""
import importlib.util
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'scripts'))
from trust_region import tr_step  # noqa: E402  unchanged scripts used by inner.py
from tr_acceptance import assess  # noqa: E402


def _load(name,path):
    if name in sys.modules:
        assert Path(sys.modules[name].__file__).resolve()==path.resolve(),name
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


onesided=_load('onesided',HERE.parent/'2026-11-16-switch-onesided/onesided.py')


def replay(evaluate,H,y,f,g,delta,extra=lambda point:{},max_trials=60):
    """Same trial order as inner.solve for one iteration: tr_step, prediction, evaluate, assess, radius update."""
    w,V=np.linalg.eigh(H);rows=[]
    for trial in range(max_trials):
        step,boundary=tr_step(w,V,g,delta)
        prediction=-float(g@step+.5*step@H@step)
        fn,gn=evaluate(y+step)
        d=assess(f,fn,prediction,float(np.linalg.norm(g)),float(np.linalg.norm(gn)),delta,float(np.linalg.norm(step)),bool(boundary))
        rows.append(dict(trial=trial,radius=float(delta),step_norm=float(np.linalg.norm(step)),boundary=bool(boundary),prediction=prediction,
            fallback_threshold=1e-13*max(1.,abs(f)),fallback=d.gradient_fallback,legacy_ratio=d.ratio,legacy_accepted=d.accepted,
            gradient_norm=float(np.linalg.norm(g)),trial_gradient_norm=float(np.linalg.norm(gn)),native_decrease=f-fn,
            next_radius=d.radius,**extra(y+step)))
        delta=d.radius
        if d.accepted or delta<1e-14:break
    return rows


def precise_ratio(decrease,prediction):
    return None if prediction<=0 else decrease/prediction


def verdict(rows,key='precise_ratio',threshold=1e-4):
    if any(r['legacy_accepted'] for r in rows):return 'replay_disagrees'
    if any(r[key] is not None and r[key]>threshold for r in rows):return 'acceptance_rule'
    return 'model'


def relative_gap(a,b):return abs(a-b)/max(1.,abs(b))
