"""Recompute every executed NLP and the lazy policy; never optimize."""
import json
from pathlib import Path
import numpy as np
import helpers as h
import driver
import policy
from observe import violation

BASE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text())


def main():
    with driver.guard.protocol_lock():
        rest=h.load_from(h.R2A,'restore');targets=read(BASE/'targets.json');rows=[]
        for case,entry in targets['cases'].items():
            source=h.ROOT/entry['source']
            for p,digest in entry['hashes'].items():assert driver.guard.sha(h.ROOT/p)==digest
            model=rest.fb.FixedBranch(read(source/'input.json'),moving=True)
            selection=read(BASE/'selected'/case/'result.json')
            for arm in ['baseline','small_push']:
                out=BASE/'cases'/arm/case
                if not out.exists():continue
                r=read(out/'result.json');saved=read(out/'solver.json');first=read(out/'first-point.json')
                x0=np.array(read(source/'starting-point.json')['point']);np.testing.assert_array_equal(first['provided'],x0)
                np.testing.assert_allclose(violation(model,np.array(first['observed'])),r['first_iterate_violation'],atol=1e-12,rtol=1e-10)
                point,lam,lam_x=(np.array(saved[k]) for k in ['point','lam','lam_x'])
                measured=model.kkt(point,lam,lam_x)
                np.testing.assert_allclose(list(measured.values()),list(r['raw_kkt'].values()),atol=1e-10,rtol=1e-8)
                accepted=False
                if r['solver_success'] and max(measured.values())<=1e-6:
                    accepted,checks,document=rest.accept(model,read(source/'input.json'),point,lam,lam_x)
                    if accepted:
                        output=read(out/'solution.json')
                        for k in ['r','e','s','c']:np.testing.assert_array_equal(output['solution'][k],document['solution'][k])
                assert bool(accepted)==r['accepted']
            baseline=read(BASE/'cases/baseline'/case/'result.json')
            if baseline['accepted']:
                assert not selection['retried'] and selection['selected']=='baseline'
                assert not (BASE/'cases/small_push'/case).exists()
            selected=BASE/'selected'/case/'solution.json'
            assert driver.guard.sha(selected)==selection['selected_sha256']
            assert selected.read_bytes()==(h.ROOT/selection['source']).read_bytes()
            rows.append(selection)
        old=BASE.parent/'2026-11-16-nlp-bound-push';retro=[]
        for case in read(old/'targets.json')['cases']:
            baseline=read(old/'cases/baseline'/case/'result.json');calls=[]
            def retry():calls.append(1);return read(old/'cases/small_push'/case/'result.json')
            chosen=policy.choose(baseline,retry);assert len(calls)==int(not baseline['accepted'])
            assert chosen['result']['accepted']
            source=old/'cases'/chosen['selected']/case/'solution.json'
            out=BASE/'retrospective'/case;out.mkdir(parents=True,exist_ok=False)
            (out/'selected.json').write_bytes(source.read_bytes())
            if baseline['accepted']:assert (out/'selected.json').read_bytes()==(old/'cases/baseline'/case/'solution.json').read_bytes()
            retro.append(dict(case=case,selected=chosen['selected'],retried=chosen['retried'],
                selected_sha256=driver.guard.sha(source),design_regression_only=True))
        summary=dict(new_conditional_inputs=4,cohort='first two original-negative seeds in each prespecified range',
            screening_audited=len(read(BASE/'screening.json')['rows']),
            nlp_solves=sum(len(r['calls']) for r in rows),baseline_accepted=sum(r['selected']=='baseline' for r in rows),
            retries=sum(r['retried'] for r in rows),retry_accepted=sum(r['selected']=='small_push' for r in rows),
            certified_outputs=sum(r['branch_kkt_pass'] for r in rows),
            physical_points=sum(r['physical_point_available'] for r in rows),
            successful_default_outputs_preserved=sum(r['selected']=='baseline' for r in rows),
            new_retry_rescue_observed=any(r['selected']=='small_push' for r in rows),
            all_executed_points_rechecked=True,optimizer_launched_by_verification=False,
            execution_seconds=read(BASE/'execution.json')['seconds'],rows=rows,retrospective=retro,
            design_regression_not_in_new_denominator=True,paper_reproduction=False)
        driver.guard.write(BASE/'summary.json',summary)
        print(json.dumps({k:summary[k] for k in ['screening_audited','baseline_accepted','retries','certified_outputs','new_retry_rescue_observed','execution_seconds']}))


if __name__=='__main__':main()
