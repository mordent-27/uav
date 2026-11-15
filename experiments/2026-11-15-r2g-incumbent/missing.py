"""Preserve physical points even when construction/initialization stops the final solve."""
import helpers as h
import retain
if __name__=='__main__':retain.finalize(h.CASE,None,h.INIT,h.BASE/'evaluations/repaired'/h.CASE,True)
