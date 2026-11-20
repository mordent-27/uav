"""Independent physical checks; no CasADi or existing optimization/certificate code."""
import math


def charge(p, e, duration):
    sigma = (p['e_max'] - p['e_th']) / p['kappa']
    if e < p['e_th']:
        transition = (p['e_th'] - e) / p['kappa']
        if duration <= transition:
            return e + p['kappa'] * duration
        return p['e_max'] - (p['e_max'] - p['e_th']) * math.exp(-(duration-transition)/sigma)
    return p['e_max'] - (p['e_max'] - e) * math.exp(-duration/sigma)


def replay(d):
    p = d['phys']; e = [p['e_max']]
    for mode, duration in zip(d['modes'], d['solution']['s']):
        e.append(charge(p, e[-1], duration) if mode >= 0 else e[-1]-p['zeta']*duration)
    return e


def carriers(d):
    """Construct q by interpolation through all contact anchors, including unused disks."""
    r, s, modes = d['solution']['r'], d['solution']['s'], d['modes']
    time = [0.]
    for duration in s:
        time.append(time[-1]+duration)
    result = {}
    for j, region in enumerate(d['instance']['regions']):
        anchors = {k0: r[k0] for k, mode in enumerate(modes) if mode == j for k0 in (k, k+1)}
        if not anchors:
            result[str(j)] = [list(region['o']) for _ in r]
            continue
        stamps = sorted(anchors); q = [list(anchors[stamps[0]]) for _ in r]
        for a, b in zip(stamps, stamps[1:]):
            for k in range(a, b+1):
                t = (time[k]-time[a])/(time[b]-time[a])
                q[k] = [(1-t)*x+t*y for x, y in zip(anchors[a], anchors[b])]
        for k in range(stamps[-1], len(r)):
            q[k] = list(anchors[stamps[-1]])
        result[str(j)] = q
    return result


def check(d, reference=None):
    p, tr, inst = d['phys'], d['solution'], d['instance']
    r, s, modes = tr['r'], tr['s'], d['modes']
    assert len(r) == len(s)+1 == len(tr['e']) and len(modes) == len(s) == len(tr['c'])
    assert all(math.isfinite(v) for a in r for v in a)
    assert all(math.isfinite(v) for a in (s, tr['e'], tr['c']) for v in a) and min(s) > 0
    if reference is not None:
        assert modes == reference['modes'] and d['task_stamp'] == reference['task_stamp']
        assert inst == reference['instance'] and p == reference['phys']
    e = replay(d)
    out = dict(energy_gap=max(abs(a-b) for a,b in zip(e,tr['e'])), min_energy=min(e), max_energy=max(e),
        tasks=max(math.dist(r[k],a) for a,k in zip(inst['tasks'],d['task_stamp'])),
        endpoints=max(math.dist(r[0],inst['r0']),math.dist(r[-1],inst['rf'])),
        uav_speed=max([0.]+[math.dist(r[k+1],r[k])-(p['v_c'] if m>=0 else p['v_d'])*s[k] for k,m in enumerate(modes)]),
        s_bounds=max([0.]+[p['s_min']-x for x in s]+[x-p['s_max'] for x in s]),
        contact_disk=max([0.]+[math.dist(r[k0],inst['regions'][m]['o'])-inst['regions'][m]['rho'] for k,m in enumerate(modes) if m>=0 for k0 in (k,k+1)]),
        c_exact=max(abs(c-(s[k] if modes[k]>=0 else 0.)) for k,c in enumerate(tr['c'])))
    late = 0.
    for j in range(len(inst['regions'])):
        segments = [k for k,m in enumerate(modes) if m == j]
        for a,b in zip(segments,segments[1:]):
            late=max(late,math.dist(r[b],r[a+1])-p['v_c']*sum(s[a+1:b]))
    out['R_excess_km'] = late
    q = d.get('carrier_positions', carriers(d))
    speed = disk = contact = 0.
    used = {m for m in modes if m>=0}
    assert used <= {int(j) for j in q}
    for key, points in q.items():
        j=int(key);reg=inst['regions'][j];assert len(points)==len(r)
        speed=max([speed]+[math.dist(points[k+1],points[k])-p['v_c']*s[k] for k in range(len(s))])
        disk=max([disk]+[math.dist(point,reg['o'])-reg['rho'] for point in points])
        contact=max([contact]+[math.dist(points[k0],r[k0]) for k,m in enumerate(modes) if m==j for k0 in (k,k+1)])
    out.update(carrier_speed=speed,carrier_disk=disk,carrier_contact=contact)
    original=max(out[k] for k in ('energy_gap','tasks','endpoints','uav_speed','s_bounds','contact_disk','c_exact'))
    out['original_residual']=original
    out['accepted']=bool(original<1e-10 and min(e)>=p['e_min'] and max(e)<=p['e_max'] and
                         max(late,speed,disk,contact)<=1e-9)
    return out
