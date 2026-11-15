"""Describe failed G attempts from existing states; do not solve a new branch."""
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def main():
    cases = []
    for folder in sorted((HERE/'cases/G').glob('*')):
        result = read(folder/'result.json')
        restored = folder/'restored/result.json'
        if restored.exists() and read(restored)['accepted']:
            continue
        stage = result['stage']
        with gzip.open(folder/'stages'/f'stage{stage:02d}'/'outer.jsonl.gz', 'rt') as log:
            rows = [json.loads(line) for line in log]
        direct = read(HERE/'cases/direct'/folder.name/'result.json')
        initial = read(folder/'source.json')
        modes = lambda r: [m['winner'] for m in r['selection']['modes']]
        tail = [dict(outer=row['outer'], common_kkt=row['common_kkt'], rho=row['rho'],
                     lambda_inf=max(map(abs, row['lam']), default=0.),
                     mu_inf=max(map(abs, row['mu']), default=0.)) for row in rows[-20:]]
        cases.append(dict(case=folder.name, last_stage=stage, stop=result['stop'],
            common_kkt=result['common_kkt'], physical_kkt=result['paper_units_kkt'],
            initial_charges=initial['selection']['charging_segments'],
            G_charges=result['selection']['charging_segments'],
            direct_charges=direct['selection']['charging_segments'],
            G_preserved_initial_modes=modes(initial) == modes(result),
            direct_preserved_initial_modes=modes(initial) == modes(direct),
            same_original_y=initial['y'] == read(HERE/'cases/direct'/folder.name/'source.json')['y'],
            G_audit=result['selection']['audit'], direct_audit=direct['selection']['audit'],
            last_completed_outers=tail, fixed_G_branch_feasibility_not_tested=True))
    (HERE/'failure-diagnosis.json').write_text(json.dumps(cases, indent=2)+'\n')
    for case in cases:
        print(case['case'], case['last_stage'], case['stop'], 'charges',
              case['initial_charges'], case['G_charges'], case['direct_charges'], case['common_kkt'])


if __name__ == '__main__':
    main()
