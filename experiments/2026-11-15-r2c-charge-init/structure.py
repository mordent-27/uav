"""Track loss/recovery of charging candidates in saved stages; no new solves."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent/'2026-11-15-r2b-coarse/cases/G'


def summarize(folder, initial_modes):
    records = []
    for path in [folder/'source.json']+sorted((folder/'stages').glob('stage*/result.json')):
        point = json.loads(path.read_text())
        selection = point['selection']
        candidates = []
        for k, region in enumerate(initial_modes):
            if region < 0:
                continue
            mode = selection['modes'][k]
            candidates.append(dict(segment=k, initial_region=region,
                current_winner=mode['winner'], initial_region_derivative_share=mode['derivative_share'][region+1],
                initial_region_dphi=mode['dphi_dz'][region+1], c=mode['c'], s=mode['s']))
        records.append(dict(stage=point['stage'], charging_segments=selection['charging_segments'],
            original_slots=candidates, max_original_charge_derivative_share=max(r['initial_region_derivative_share'] for r in candidates),
            pure_min_energy=selection['audit'].get('pure_mode_min_energy'),
            max_c_minus_s=max(r['c']-r['s'] for r in selection['modes'])))
    return records


def main():
    result = []
    for folder in sorted((HERE/'cases').glob('*')):
        if not (folder/'steps.json').exists():
            continue
        initial = json.loads((HERE/'initializations'/folder.name/'solution.json').read_text())
        result.append(dict(case=folder.name, baseline=summarize(BASE/folder.name, initial['modes']),
            changed=summarize(folder, initial['modes'])))
    (HERE/'structure.json').write_text(json.dumps(result, indent=2)+'\n')
    for row in result:
        if row['case'] == 'tau1-seed2':
            for kind in ['baseline', 'changed']:
                print(kind, [(p['stage'], p['charging_segments'], p['max_original_charge_derivative_share']) for p in row[kind]])


if __name__ == '__main__':
    main()
