"""One prespecified extra Newton control, no outer AL continuation."""
import json
import support as s
from run import solve

if __name__ == '__main__':
    state = json.loads((s.HERE/'inputs.json').read_text())['stalled']
    solve('stalled', 'newton-decomposed', state)
