"""Recompute certificates for G or the fallback, without performing a numerical solve."""
import json
import os
import helpers as h


def main():
    retain=h.load_from(h.R2G,'retain')
    if h.PHASE=='G':
        source=h.ROOT/os.environ['UAV_R2H_G_SOURCE']
        assert json.loads((source/'source.json').read_text())['y']==json.loads((h.INPUT/'original-state.json').read_text())['y']
        retain.finalize(h.CASE,source,h.INPUT,h.OUT/'evaluations/G'/h.CASE,False)
    else:
        cached=os.environ.get('UAV_R2H_FALLBACK_EVALUATION')
        if cached:
            old_folder=h.ROOT/cached;old=json.loads((old_folder/'result.json').read_text())
            init=h.ROOT/old['initialization_source']
            assert json.loads((init/'original-state.json').read_text())['y']==json.loads((h.INPUT/'original-state.json').read_text())['y']
            source=None if old['solver_source'] is None else h.ROOT/old['solver_source']
        else:
            old_folder=None;init=h.INIT
            source=h.HERE if (h.HERE/'result.json').exists() else None
        destination=h.OUT/'evaluations/fallback'/h.CASE
        result=retain.finalize(h.CASE,source,init,destination,True)
        if old_folder and result['physical_point_available']:
            assert (destination/'selected.json').read_bytes()==(old_folder/'selected.json').read_bytes()


if __name__=='__main__':main()
