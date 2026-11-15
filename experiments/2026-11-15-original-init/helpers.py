"""Same helpers as ../2026-11-15-decomposed-follow, with this folder as the output location."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLLOW = HERE.parent/'2026-11-15-decomposed-follow'
_spec = importlib.util.spec_from_file_location('follow_helpers', FOLLOW/'helpers.py')
_follow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_follow)

ROOT, PRIOR = _follow.ROOT, _follow.PRIOR
stage4, decomposition, write, tr = _follow.stage4, _follow.decomposition, _follow.write, _follow.tr
state, assess, export = _follow.state, _follow.assess, _follow.export
FOLLOW_SOURCE = _follow.SOURCE
SOURCE = HERE/'source.json'  # the original initial trajectory, written by preflight.py


def load(name):
    """Load a script of the previous experiment unchanged; its `import helpers` resolves to this file."""
    spec = importlib.util.spec_from_file_location('follow_'+name, FOLLOW/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
