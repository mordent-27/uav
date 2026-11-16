"""Outer-stall stop rule replayed on saved outer rows. Pure functions; no solver."""


def first_trigger(rows,K,delta,tol=1e-6,cap=1e8):
    """1-based outer index where the rule first holds, or None. rows need 'rho' and 'violation'."""
    for k in range(2*K,len(rows)+1):
        window=rows[k-2*K:k]
        if not all(r['rho']>=cap for r in window):continue
        v=rows[k-1]['violation']
        if v<=tol:continue
        recent=min(r['violation'] for r in window[K:]);before=min(r['violation'] for r in window[:K])
        if recent>=(1-delta)*before:return k
    return None


def classify(rows,passed,K,delta,tol=1e-6,cap=1e8):
    """Return a dict describing the replay of one stage log."""
    k=first_trigger(rows,K,delta,tol,cap);n=len(rows)
    pass_row=next((r['outer'] for r in rows if r.get('stage_pass')),None) if passed else None
    out=dict(trigger=k,rows=n,passed=passed,pass_row=pass_row)
    if k is None:out.update(kind='no_trigger');return out
    if passed and pass_row is not None and k<pass_row:out.update(kind='false_stop');return out
    if passed:out.update(kind='after_pass');return out
    t=rows[k-1]['seconds'];last=rows[-1]['seconds']
    out.update(kind='stopped_failure',trigger_seconds=t,last_seconds=last,saved_seconds=last-t,
        violation_at_trigger=rows[k-1]['violation'],violation_last=rows[-1]['violation'],
        violation_ratio_last_over_trigger=rows[-1]['violation']/rows[k-1]['violation'])
    return out


def verdict(results):
    if any(r['kind']=='false_stop' for r in results):return 'unsafe'
    return 'safe_saves_time' if any(r['kind']=='stopped_failure' for r in results) else 'safe_no_effect'
