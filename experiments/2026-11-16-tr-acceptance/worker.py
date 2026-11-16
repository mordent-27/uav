"""Replay saved trials and audit decisions; never launch an optimizer."""
import json
import os
from pathlib import Path
import sys
import numpy as np
import helpers as h

sys.path.insert(0,str(h.ROOT/'scripts'))
from tr_acceptance import assess
from trust_region import tr_step

BASE=Path(__file__).resolve().parent


def main():
    case=os.environ['UAV_R2_CASE']
    target=next(t for t in json.loads((BASE/'targets.json').read_text())['contexts'] if t['case']==case)
    state=json.loads((h.ROOT/target['source']).read_text());f=h.stage4.Frozen(state)
    prior=h.ROOT/'experiments/2026-11-16-tr-boundary-fix/inner'/f'{case}-boundary-fixed'
    recorded=json.loads((prior/'result.json').read_text())
    accepted=[json.loads(s) for s in (prior/'trace.jsonl').read_text().splitlines()]
    steps=[json.loads(s) for s in (prior/'tr-steps.jsonl').read_text().splitlines()]
    out=BASE/'replays'/case;out.mkdir(exist_ok=False)
    y=np.array(state['y']);value,g=f.eval(y);g=g.copy();stable,sg=f.eval(y,stable=True)
    np.testing.assert_allclose(sg,g,atol=1e-10,rtol=1e-9)
    delta=1.;rebuild=True;accepted_count=0;rows=[]
    for index,saved in enumerate(steps):
        np.testing.assert_allclose(delta,saved['delta'],atol=1e-30,rtol=1e-12)
        if rebuild:
            H,_=h.decomposition.hessian_of_al(f,y,1e-7);w,V=np.linalg.eigh(H)
        step,boundary=tr_step(w,V,g,delta)
        np.testing.assert_allclose(step,saved['step'],atol=1e-25,rtol=1e-10)
        assert bool(boundary)==saved['boundary']
        candidate=y+step;trial_value,trial_g=f.eval(candidate);trial_g=trial_g.copy()
        trial_stable,trial_sg=f.eval(candidate,stable=True)
        np.testing.assert_allclose(trial_sg,trial_g,atol=1e-10,rtol=1e-9)
        prediction=-float(g@step+.5*step@H@step)
        ordinary_decrease=float(value-trial_value);stable_decrease=float(stable-trial_stable)
        args=dict(value=float(value),trial_value=float(trial_value),prediction=prediction,
            gradient_norm=float(np.linalg.norm(g)),trial_gradient_norm=float(np.linalg.norm(trial_g)),
            radius=float(delta),step_norm=float(np.linalg.norm(step)),boundary=bool(boundary))
        decision=assess(**args);stabilized=assess(**args,actual_decrease=stable_decrease)
        stable_ratio=stable_decrease/prediction if prediction>0 else None
        row=dict(index=index+1,accepted_before=accepted_count,y=y.tolist(),candidate_y=candidate.tolist(),
            **args,ordinary_decrease=ordinary_decrease,stable_decrease=stable_decrease,
            difference_of_decreases=stable_decrease-ordinary_decrease,
            accepted=decision.accepted,ratio=decision.ratio,gradient_fallback=decision.gradient_fallback,
            next_radius=decision.radius,stable_same_policy_accepted=stabilized.accepted,
            stable_same_policy_ratio=stabilized.ratio,stable_ratio_without_fallback=stable_ratio,
            stable_ratio_without_fallback_accepted=bool(stable_ratio is not None and stable_ratio>1e-4),
            gradient_inf=float(max(abs(g))),trial_gradient_inf=float(max(abs(trial_g))))
        rows.append(row);delta=decision.radius;rebuild=decision.accepted
        if decision.accepted:
            accepted_count+=1;expected=accepted[accepted_count]
            np.testing.assert_array_equal(candidate,expected['y'])
            np.testing.assert_allclose(decision.ratio,expected['ratio'],atol=1e-15,rtol=1e-12)
            assert decision.gradient_fallback==expected['gradient_fallback']
            np.testing.assert_allclose(delta,expected['delta'],atol=1e-30,rtol=1e-12)
            y,value,g,stable=candidate,trial_value,trial_g,trial_stable
    np.testing.assert_array_equal(y,recorded['y'])
    np.testing.assert_allclose(g,recorded['gradient'],atol=1e-10,rtol=1e-9)
    assert accepted_count==recorded['accepted']
    (out/'trials.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    result=dict(case=case,source=target['source'],source_sha256=target['sha256'],rho=state['rho'],
        trials=len(rows),accepted=accepted_count,rejected=len(rows)-accepted_count,
        fallback_trials=sum(r['gradient_fallback'] for r in rows),
        fallback_accepted=sum(r['gradient_fallback'] and r['accepted'] for r in rows),
        nonpositive_prediction=sum(r['prediction']<=0 for r in rows),
        stable_same_policy_decision_changes=sum(r['accepted']!=r['stable_same_policy_accepted'] for r in rows),
        stable_ratio_decision_changes=sum(r['accepted']!=r['stable_ratio_without_fallback_accepted'] for r in rows),
        stable_positive_legacy_rejected=[r['index'] for r in rows if r['stable_decrease']>0 and not r['accepted']],
        final_y=y.tolist(),final_gradient=g.tolist(),final_gradient_inf=float(max(abs(g))),
        saved_trajectory_reproduced=True,optimizer_launched=False)
    f.close();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['final_y','final_gradient']}),flush=True)


if __name__=='__main__':main()
