"""R2f's guard unchanged, plus a check against the prespecified screened input."""
import json
import numpy as np
import helpers as h

if __name__=='__main__':
    h.load_from(h.R2F,'guard').main()
    original=json.loads((h.INIT/'original-state.json').read_text())
    screened=json.loads((h.BASE/'screened-inputs'/h.CASE/'state.json').read_text())
    np.testing.assert_array_equal(original['y'],screened['y'])
