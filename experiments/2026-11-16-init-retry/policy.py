"""Lazy conditional retry. An accepted default solution is always preserved."""


def choose(baseline,retry_supplier):
    if baseline['accepted']:
        return dict(selected='baseline',retried=False,result=baseline)
    retry=retry_supplier()
    return dict(selected='small_push' if retry['accepted'] else None,retried=True,result=retry)
