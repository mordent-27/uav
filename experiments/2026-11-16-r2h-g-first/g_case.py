"""Original condition-G start/run/restore/verify with a fully checked input and new outputs."""
import json
import traceback
import helpers as h


def main():
    h.load_from(h.R2B,'case').start()
    assert json.loads(h.SOURCE.read_text())['y']==json.loads((h.INPUT/'original-state.json').read_text())['y']
    steps={}
    try:
        for name,action in [('run',lambda:h.load_from(h.R2B,'run').main()),
                            ('restore',lambda:h.load_from(h.R2A,'restore').main()),
                            ('verify',lambda:h.load_from(h.R2B,'verify').main())]:
            try:action();steps[name]='ok'
            except Exception:steps[name]=traceback.format_exc();raise
    finally:h.write(h.HERE/'steps.json',steps)


if __name__=='__main__':main()
