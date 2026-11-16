"""Recompute recorded points/acceptance and compare all fixed arms; no optimization."""
import json
from pathlib import Path
import numpy as np
import helpers as h
from observe import violation
import driver

BASE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text())


def main():
    with driver.guard.protocol_lock():
        rest=h.load_from(h.R2A,'restore');targets=read(BASE/'targets.json');rows=[]
        for case,entry in targets['cases'].items():
            source=h.ROOT/entry['source']
            for path,digest in entry['hashes'].items():assert driver.guard.sha(h.ROOT/path)==digest
            model=rest.fb.FixedBranch(read(source/'input.json'),moving=True)
            pair=[]
            for arm in targets['arms']:
                out=BASE/'cases'/arm/case;r=read(out/'result.json');saved=read(out/'solver.json');first=read(out/'first-point.json')
                x0=np.array(read(source/'starting-point.json')['point']);np.testing.assert_array_equal(first['provided'],x0)
                np.testing.assert_allclose(violation(model,np.array(first['observed'])),r['first_iterate_violation'],atol=1e-12,rtol=1e-10)
                point,lam,lam_x=(np.array(saved[k]) for k in ['point','lam','lam_x'])
                measured=model.kkt(point,lam,lam_x)
                np.testing.assert_allclose(list(measured.values()),list(r['raw_kkt'].values()),atol=1e-10,rtol=1e-8)
                options=read(source/'solver.json')['options']
                if arm=='small_push':options['ipopt']['bound_push']=1e-8
                assert saved['options']==options
                accepted=False
                if r['solver_success'] and max(measured.values())<=1e-6:
                    accepted,checks,document=rest.accept(model,read(source/'input.json'),point,lam,lam_x)
                    if accepted:
                        output=read(out/'solution.json')
                        for key in ['r','e','s','c']:np.testing.assert_array_equal(output['solution'][key],document['solution'][key])
                assert bool(accepted)==r['accepted']
                pair.append(r);rows.append(r)
            assert pair[0]['accepted']==read(source/'result.json')['accepted'],'historical baseline acceptance changed'
        summary=dict(optimizer_launched_by_verification=False,cases=4,solves=8,all_points_rechecked=True,
            source_files_unchanged=True,only_option_change='ipopt.bound_push: default 0.01 -> 1e-8',
            arms={a:dict(accepted=sum(r['accepted'] for r in rows if r['arm']==a),
                failure_cases_accepted=sum(r['accepted'] for r in rows if r['arm']==a and r['stratum']=='failure'),
                controls_accepted=sum(r['accepted'] for r in rows if r['arm']==a and r['stratum']=='control')) for a in targets['arms']},
            execution_seconds=read(BASE/'execution.json')['seconds'],rows=rows,
            conclusion='Input bound adjustment changes the starting point and convergence path. Two failures recover but one successful control regresses; do not adopt globally or change the frozen 900 protocol.',
            paper_reproduction=False)
        driver.guard.write(BASE/'summary.json',summary)
        lines=['# 開始点境界補正の4例対照','',
            '| 入力 | 条件 | 初回の元制約違反 | 時間変化最大 秒 | 反復 | 受理 |','|---|---|---:|---:|---:|---|']
        for r in rows:lines.append(f"| {r['case']} | {r['arm']} | {r['first_iterate_violation']:.3e} | {r['first_duration_delta_seconds_inf']:.3e} | {r['iterations']} | {'○' if r['accepted'] else '×'} |")
        (BASE/'comparison.md').write_text('\n'.join(lines)+'\n')
        print(json.dumps(dict(arms=summary['arms'],execution_seconds=summary['execution_seconds'],rechecked=8)))


if __name__=='__main__':main()
