"""Account for stage/inner work from saved outputs, including failed attempts."""
from collections import Counter
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    phases = []
    for folder in sorted((HERE/'cases').glob('*/*')):
        stages = []
        for path in sorted((folder/'stages').glob('stage*/result.json')):
            result = json.loads(path.read_text())
            with gzip.open(path.parent/'outer.jsonl.gz', 'rt') as log:
                rows = [json.loads(line) for line in log]
            stages.append(dict(stage=result['stage'], seconds=result['seconds'], stop=result['stop'],
                common_pass=result['common_pass'], physical_pass=result['physical_pass'],
                outer=len(rows), inner_statuses=dict(Counter(r['inner']['status'] for r in rows)),
                accepted_inner=sum(r['inner']['accepted'] for r in rows),
                jacobian_calls=sum(r['inner']['jacobian_calls'] for r in rows),
                hessian_gradient_calls=sum(r['inner']['hessian_gradient_calls'] for r in rows)))
        phases.append(dict(phase=folder.parent.name, case=folder.name, stages=stages,
            coarse_seconds=sum(s['seconds'] for s in stages if s['stage'] < 13),
            final_seconds=sum(s['seconds'] for s in stages if s['stage'] == 13),
            interrupted_inner_excluded_from_inner_counts=True))
    (HERE/'stage-costs.json').write_text(json.dumps(phases, indent=2)+'\n')
    for phase in phases:
        print(phase['phase'], phase['case'], 'coarse', round(phase['coarse_seconds'], 2),
              'final', round(phase['final_seconds'], 2))


if __name__ == '__main__':
    main()
