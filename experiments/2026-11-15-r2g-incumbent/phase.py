"""Keep R2f's solve/restoration/verification, then evaluate the new output-retention rule."""
import helpers as h
import retain

if __name__=='__main__':
    h.load_from(h.R2F,'phase').main()
    retain.finalize(h.CASE,h.HERE,h.INIT,h.BASE/'evaluations'/h.KIND/h.CASE,h.KIND=='repaired')
