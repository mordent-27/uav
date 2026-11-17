"""Independent order-statistic and ECDF-integral readback of generated tables."""
import csv
import json
import math
from pathlib import Path
import statistics
import sys
from analyze import ROOT,BASE,COHORT,read,verify_sources


def quantile(a,q):
    a=sorted(a);index=(len(a)-1)*q;i=math.floor(index);j=math.ceil(index)
    return a[i]+(a[j]-a[i])*(index-i)


def check_distribution(values,reported):
    assert reported['n']==len(values)
    if not values:assert reported['median'] is None;return
    for key,q in [('min',0),('q10',.1),('q25',.25),('median',.5),('q75',.75),('q90',.9),('q95',.95),('max',1)]:
        assert math.isclose(quantile(values,q),reported[key],abs_tol=1e-12,rel_tol=1e-12),key
    assert math.isclose(math.fsum(values)/len(values),reported['mean'],abs_tol=1e-12,rel_tol=1e-12)


def main():
    verify_sources();summary=read(BASE/'summary.json');original=read(COHORT/'summary.json')
    with (BASE/'cases.csv').open() as f:cases=list(csv.DictReader(f))
    with (ROOT/'data/paper_fig3.csv').open() as f:paper=list(csv.DictReader(f))
    originals={r['case']:r for r in original['cases']};assert len(cases)==len(originals)==900
    assert set(r['case'] for r in cases)==set(originals)
    for row in cases:
        source=originals[row['case']];present=row['physical_point_available']=='True'
        assert present==source['physical_point_available']
        assert row['origin']==source['origin'] and row['route']==source['route']
        assert (row['selected'] or None)==source['selected']
        assert (row['fixed_branch_kkt']=='True')==source['selected_same_final_branch_kkt']
        if present:assert float(row['objective_h'])==source['selected_hours']
        else:assert row['objective_h']==''
    assert sum(r['objective_h']!='' for r in cases)==894
    for group in summary['groups']:
        tau=group['tau'];own=[r for r in cases if int(r['tau'])==tau];assert len(own)==100
        a=[float(r['objective_h']) for r in own if r['objective_h']]
        b=[float(r['value']) for r in paper if int(r['tau'])==tau and r['quantity']=='objective_h' and r['method']=='NLP']
        cert=[float(r['objective_h']) for r in own if r['objective_h'] and r['fixed_branch_kkt']=='True']
        assert group['total']==len(own) and group['returned']==len(a) and group['missing']==100-len(a) and group['certified']==len(cert)
        check_distribution(a,group['selected']);check_distribution(cert,group['certified_objective'])
        for section,field in [('by_origin','origin'),('by_route','route'),('by_selected','selected')]:
            for category,reported in group[section].items():
                values=[float(r['objective_h']) for r in own if r['objective_h'] and r[field]==category]
                check_distribution(values,reported)
        assert math.isclose(statistics.median(a)/statistics.median(b),group['median_ratio'],abs_tol=1e-12)
        missing=100-len(a)
        assert statistics.median([*a,*([0.]*missing)])==group['missing_median_lower_h']
        assert statistics.median([*a,*([math.inf]*missing)])==group['missing_median_upper_h']
        grid=sorted(set(a+b));cdf_a=[sum(v<=x for v in a)/len(a) for x in grid];cdf_b=[sum(v<=x for v in b)/len(b) for x in grid]
        distance=math.fsum((grid[i+1]-grid[i])*abs(cdf_a[i]-cdf_b[i]) for i in range(len(grid)-1))
        assert math.isclose(distance,group['wasserstein_h'],abs_tol=1e-12)
        assert math.isclose(max(abs(x-y) for x,y in zip(cdf_a,cdf_b)),group['ecdf_max_difference_conditional'],abs_tol=1e-12)
        for method in ['NLP','SCIP','Juniper']:
            values=[float(r['value']) for r in paper if int(r['tau'])==tau and r['quantity']=='objective_h' and r['method']==method]
            check_distribution(values,group['paper'][method])
    verify_sources()
    result=dict(cases=900,available=894,missing=6,tau_groups=9,quantiles='independent linear order statistics',
        distances='independent ECDF step functions and integral',all_checks_passed=True,optimizer_launched=False)
    if '--check-only' not in sys.argv:
        out=BASE/'verification.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
