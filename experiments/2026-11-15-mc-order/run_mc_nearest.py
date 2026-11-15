"""Paired cohort: the 900 instances of ../2026-11-14-conditioning/mc-rho1e4 with the nearest-order warm start.

Every attempted case remains in the denominator. Raw JSON/log and a per-case status
are written immediately; summary is refreshed after each completion.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
from time import monotonic

HERE=Path(__file__).resolve().parent
EXTRA=['--rho0','1e4','--rho-mult','1','--order','nearest']  # --order nearest is the only difference from mc-rho1e4
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('audit',ROOT/'experiments/2026-11-14-validation/audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--timeout',type=float,default=90.)
    parser.add_argument('--tau-max',type=int,default=9)
    parser.add_argument('--runs',type=int,default=100)
    parser.add_argument('--output-dir',type=Path,default=HERE/'mc-nearest')
    args=parser.parse_args()
    base=args.output_dir;base.mkdir(parents=True,exist_ok=True)
    binary=ROOT/'target/release/uav'
    manifest=dict(backend='original Rust AL/L-BFGS; '+' '.join(EXTRA),
        input_distribution='uniform [-9,9]^2, reject distance to all charging disks >6 km',
        seed_rule='tau*10000+run; base seed=0',tasks=list(range(1,args.tau_max+1)),runs=args.runs,
        timeout_seconds=args.timeout,workers=args.workers,
        status='independent distribution; author seeds/distribution/tolerances unavailable',
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').glob('*.rs'))})
    manifest_path=base/'manifest.json'
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text())==manifest,'resume requires identical configuration'
    else:
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    archive=base/'cases.tar.gz'
    if not (base/'cases').exists() and archive.exists():
        # A fresh checkout keeps raw files in the archive, not thousands of Git entries.
        with tarfile.open(archive) as saved:
            assert all(Path(item.name).parts[0]=='cases' and '..' not in Path(item.name).parts
                       for item in saved.getmembers())
            saved.extractall(base,filter='data')
        print('restored stored cases from archive; completed cases will not be solved again',flush=True)

    def execute_case(tau,run):
        directory=base/'cases'/f'tau{tau}'/f'run{run:03d}'
        directory.mkdir(parents=True,exist_ok=True)
        status_path=directory/'status.json'
        if status_path.exists():return json.loads(status_path.read_text())
        seed=tau*10000+run
        command=[str(binary),'solve','--tau',str(tau),'--seed',str(seed),'--out',str(directory/'raw.json')]+EXTRA
        row=dict(tau=tau,run=run,seed=seed,completed=False,timed_out=False,kkt_converged=False,
                 original_violation_le_1e_3=False,physical_audit_pass=False,objective=None,
                 stat=None,feas=None,comp=None,elapsed=None,exit_code=None)
        start=monotonic()
        with (directory/'solver.log').open('w') as log:
            try:
                result=subprocess.run(command,stdout=log,stderr=log,timeout=args.timeout)
                row['exit_code']=result.returncode
                if result.returncode==0:
                    d=json.loads((directory/'raw.json').read_text())
                    checked=audit.inspect(d)
                    kkt=d['stages'][-1]
                    row.update(completed=True,kkt_converged=d['metrics']['converged'],
                        original_violation_le_1e_3=d['metrics']['viol']<=1e-3,
                        physical_audit_pass=checked['original_pass'] and checked['exact_mode_battery_pass'],
                        objective=d['metrics']['objective'],original_violation=d['metrics']['viol'],
                        solver_seconds=d['metrics']['seconds'],stat=kkt['stat'],feas=kkt['feas'],comp=kkt['comp'])
                    (directory/'audit.json').write_text(json.dumps(checked,indent=2,allow_nan=False)+'\n')
            except subprocess.TimeoutExpired:
                row['timed_out']=True
            except Exception as exc:
                row['error']=str(exc)
        row['elapsed']=monotonic()-start
        status_path.write_text(json.dumps(dict(row,command=command),indent=2,allow_nan=False)+'\n')
        return row

    rows=[]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        jobs=[executor.submit(execute_case,tau,index) for tau in range(1,args.tau_max+1) for index in range(args.runs)]
        for job in as_completed(jobs):
            rows.append(job.result())
            summary=[]
            for tau in range(1,args.tau_max+1):
                subset=[v for v in rows if v['tau']==tau]
                summary.append(dict(tau=tau,planned=args.runs,finished=len(subset),
                    completed=sum(v['completed'] for v in subset),timed_out=sum(v['timed_out'] for v in subset),
                    kkt_converged=sum(v['kkt_converged'] for v in subset),
                    original_violation_le_1e_3=sum(v['original_violation_le_1e_3'] for v in subset),
                    physical_audit_pass=sum(v['physical_audit_pass'] for v in subset)))
            temp=base/'summary.tmp';temp.write_text(json.dumps(summary,indent=2)+'\n');temp.replace(base/'summary.json')
            if len(rows)%25==0:
                print(json.dumps(dict(finished=len(rows),total=len(jobs),summary=summary)),flush=True)
    fields=['tau','run','seed','completed','timed_out','kkt_converged','original_violation_le_1e_3',
            'physical_audit_pass','objective','stat','feas','comp','elapsed','exit_code','original_violation','solver_seconds']
    with (base/'results.csv').open('w',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=fields,extrasaction='ignore',lineterminator='\n');writer.writeheader()
        writer.writerows(sorted(rows,key=lambda r:(r['tau'],r['run'])))


if __name__=='__main__':main()
