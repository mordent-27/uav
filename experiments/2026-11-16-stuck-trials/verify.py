"""Separate-process recheck: replay again (80 and 100 digits) and compare every recorded trial field."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

BASE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def strip(rows):return [{k:v for k,v in r.items()} for r in rows]


def main():
    import driver
    with driver.guard.protocol_lock():
        targets=driver.guard.read(BASE/'targets.json');driver.check_inputs(targets);out=BASE/'reverification';out.mkdir(exist_ok=False)
        before={str(p.relative_to(BASE)):sha(p) for d in ['replays','replays-decimal'] for p in (BASE/d).iterdir()};report={}
        with tempfile.TemporaryDirectory() as tmp:
            for mode,full,digits in [('first',False,80),('decimal80',True,80),('decimal100',True,100)]:
                folder=Path(tmp)/mode;folder.mkdir()
                for t in targets['targets']:
                    env=dict(os.environ,UAV_R2_CASE=t['case'],UAV_STUCK_TARGET=t['name'],UAV_STUCK_OUT_DIR=str(folder),UAV_STUCK_DIGITS=str(digits),
                        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
                    if full:env['UAV_STUCK_FULL_TASKS']='1'
                    subprocess.run([sys.executable,str(BASE/'worker.py')],env=env,cwd=BASE.parents[1],check=True,stdout=subprocess.DEVNULL)
                    new=json.loads((folder/f"{t['name']}.json").read_text())
                    old=json.loads((BASE/('replays-decimal' if full else 'replays')/f"{t['name']}.json").read_text())
                    keys=['prediction','native_decrease','stable_decrease','legacy_accepted','legacy_ratio','fallback','step_norm','radius','trial_gradient_norm']
                    row=dict(trials=len(new['rows']),same_trials=len(new['rows'])==len(old['rows']) and all(a[k]==b[k] for a,b in zip(new['rows'],old['rows']) for k in keys),
                        verdict=new['verdict'],verdict_same=new['verdict']==old['verdict'])
                    if full:
                        gaps=[abs(a['decimal_decrease']-b['decimal_decrease'])/max(abs(b['decimal_decrease']),1e-300) for a,b in zip(new['rows'],old['rows'])]
                        row.update(max_relative_decimal_difference=max(gaps),decimal_value_gap=new['decimal_value_gap'])
                        if digits==80:row['decimal_identical']=max(gaps)==0.
                    assert row['same_trials'] and row['verdict_same'],(mode,t['name'])
                    if full:assert row['max_relative_decimal_difference']<=1e-6
                    report.setdefault(mode,{})[t['name']]=row
        after={str(p.relative_to(BASE)):sha(p) for d in ['replays','replays-decimal'] for p in (BASE/d).iterdir()};assert before==after
        driver.check_inputs(targets);(out/'replays.json').write_text(json.dumps(dict(report=report,outputs_unchanged=True,optimizer_launched=False),indent=2)+'\n')
        print(json.dumps(report))


if __name__=='__main__':main()
