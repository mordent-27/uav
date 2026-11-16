"""Pure extraction of the diagnostic Newton's existing acceptance policy."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Decision:
    accepted: bool
    radius: float
    ratio: float
    gradient_fallback: bool


def assess(value,trial_value,prediction,gradient_norm,trial_gradient_norm,
           radius,step_norm,boundary,*,actual_decrease=None):
    """Preserve legacy behavior, including its nonmonotone gradient fallback.

    actual_decrease allows auditing a more stable evaluation of the same value
    difference. The branch threshold still uses the original absolute value.
    """
    numbers=(value,trial_value,prediction,gradient_norm,trial_gradient_norm,radius,step_norm)
    if not all(math.isfinite(x) for x in numbers):
        raise ValueError('finite decision inputs are required')
    if min(gradient_norm,trial_gradient_norm,step_norm)<0 or radius<=0:
        raise ValueError('norms must be nonnegative and the radius positive')
    if step_norm>radius*(1+1e-12)+1e-30:
        raise ValueError('the step must respect the trust radius')
    if actual_decrease is not None and not math.isfinite(actual_decrease):
        raise ValueError('actual_decrease must be finite')
    fallback=prediction<=1e-13*max(1.,abs(value))
    if fallback:
        ratio=1. if trial_gradient_norm<gradient_norm else 0.
    else:
        reduction=value-trial_value if actual_decrease is None else actual_decrease
        ratio=reduction/prediction
    updated=radius
    if ratio<.25:updated=.25*step_norm
    elif ratio>.75 and boundary:updated=min(2*radius,1e3)
    return Decision(ratio>1e-4,updated,ratio,fallback)
