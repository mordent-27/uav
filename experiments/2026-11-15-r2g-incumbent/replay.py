"""Evaluate one R2f regression case without re-solving it."""
import json
import helpers as h
import retain

if __name__=='__main__':
    old=json.loads((h.R2F/'summary.json').read_text())
    row=next(r for r in old['cases'] if r['case']==h.CASE)
    retain.finalize(h.CASE,h.ROOT/row['candidate']['path'],h.R2F/'initializations'/h.CASE,
        h.BASE/'regression'/h.CASE,True)
