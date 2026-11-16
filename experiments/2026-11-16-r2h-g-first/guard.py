"""Only the fallback invokes R2f's unchanged input guard."""
import json
import helpers as h
if __name__=='__main__':
    h.load_from(h.R2F,'guard').main()
    assert json.loads((h.INIT/'original-state.json').read_text())['y']==json.loads((h.INPUT/'original-state.json').read_text())['y']
