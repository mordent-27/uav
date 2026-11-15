"""Read every accepted direct-final point and inspect the previously lost charging mode."""
import gzip
import json
import numpy as np
import helpers as h


def main():
    m=h.fidelity.Variant('R');m.stage(.0005,12.)
    folder=h.HERE/'stages/stage13'
    modes=[]
    for path in sorted(folder.glob('inner*.jsonl.gz')):
        with gzip.open(path,'rt') as handle:
            rows=[json.loads(line) for line in handle]
        for row in rows[1:]:
            description=h.tr.describe(m,np.array(row['y']),m.source,.0005,12.)['modes'][19]
            modes.append(dict(inner_log=path.name,iteration=row.get('iteration',0),winner=description['winner'],
                c_over_s=description['c_over_s'],region0_derivative_share=description['derivative_share'][1]))
    h.write(h.BASE/'charge19-check.json',dict(points=len(modes),all_region0=all(row['winner']==0 for row in modes),
        minimum_region0_derivative_share=min(row['region0_derivative_share'] for row in modes),rows=modes))
    print('points',len(modes),'all region0',all(row['winner']==0 for row in modes))
    m.close()


if __name__=='__main__':main()
