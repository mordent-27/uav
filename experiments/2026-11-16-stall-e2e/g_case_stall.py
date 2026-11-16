"""Copy of r2h g_case.py; only the G stage loop is loaded from run_stall.py (stall-e2e PLAN.md)."""
import json
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'2026-11-16-r2h-g-first'))
import helpers as h
HERE_STALL=Path(__file__).resolve().parent


def main():
    h.load_from(h.R2B,'case').start()
    assert json.loads(h.SOURCE.read_text())['y']==json.loads((h.INPUT/'original-state.json').read_text())['y']
    steps={}
    try:
        for name,action in [('run',lambda:h.load_from(HERE_STALL,'run_stall').main()),
                            ('restore',lambda:h.load_from(h.R2A,'restore').main()),
                            ('verify',lambda:h.load_from(h.R2B,'verify').main())]:
            try:action();steps[name]='ok'
            except Exception:steps[name]=traceback.format_exc();raise
    finally:h.write(h.HERE/'steps.json',steps)


if __name__=='__main__':main()
