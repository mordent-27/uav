import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def main():
    results=[]
    for folder in sorted((BASE/'replays').glob('*/')):
        r=json.loads((folder/'result.json').read_text())
        r.pop('final_y');r.pop('final_gradient')
        rows=[json.loads(s) for s in (folder/'trials.jsonl').read_text().splitlines()]
        changed=[x for x in rows if x['accepted']!=x['stable_ratio_without_fallback_accepted']]
        r.update(accepted_with_stable_al_increase=[x['index'] for x in rows if x['accepted'] and x['stable_decrease']<0],
            positive_prediction_without_fallback_accept_changes=len(changed),
            max_difference_of_decreases=max(abs(x['difference_of_decreases']) for x in rows),
            changed_witnesses=[{k:x[k] for k in ['index','prediction','ordinary_decrease','stable_decrease','gradient_norm',
                'trial_gradient_norm','gradient_fallback','accepted','stable_ratio_without_fallback_accepted']} for x in changed],
            last_four_trials=[{k:x[k] for k in ['index','prediction','ordinary_decrease','stable_decrease','radius','accepted',
                'gradient_norm','trial_gradient_norm']} for x in rows[-4:]])
        results.append(r)
    summary=dict(cases=2,trials=sum(r['trials'] for r in results),python_tests=34,new_tests=11,
        optimizer_launched=False,counterfactual_is_on_recorded_trajectory_only=True,
        seconds=json.loads((BASE/'execution.json').read_text())['seconds'],rows=results)
    (BASE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'}))


if __name__=='__main__':main()
