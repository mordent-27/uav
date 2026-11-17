"""Distribution summaries and explicit treatment of unreturned instances."""
import math
import statistics
import numpy as np


def distribution(values):
    a=np.array(values,dtype=float)
    if not np.all(np.isfinite(a)) or np.any(a<0):raise ValueError('finite nonnegative objectives required')
    if not len(a):return dict(n=0,min=None,q10=None,q25=None,median=None,q75=None,q90=None,q95=None,max=None,mean=None)
    return dict(n=len(a),min=float(min(a)),**{key:float(np.quantile(a,q,method='linear')) for key,q in
        [('q10',.1),('q25',.25),('median',.5),('q75',.75),('q90',.9),('q95',.95)]},max=float(max(a)),mean=float(np.mean(a)))


def missing_median_bounds(values,total):
    if total<=0 or total<len(values):raise ValueError('invalid population size')
    distribution(values)
    missing=total-len(values)
    return float(statistics.median([*values,*([0.]*missing)])),float(statistics.median([*values,*([math.inf]*missing)]))


def failure_aware_cdf(values,total,threshold):
    if total<=0 or total<len(values):raise ValueError('invalid population size')
    return sum(x<=threshold for x in values)/total


def objective_from_point(point,declared):
    hours=float(declared);durations=point['solution']['s']
    if not math.isfinite(hours) or hours<0 or not durations:raise ValueError('invalid mission duration')
    # Original Rust JSON used 9 decimals; later Python outputs retain full precision.
    allowance=len(durations)*.51e-9+1e-12
    if abs(math.fsum(durations)-hours)>allowance:raise ValueError('duration sum disagrees with selected objective')
    if abs(float(point['metrics']['objective'])-hours)>allowance:raise ValueError('metrics objective disagrees')
    return hours
