"""Show the deterministic geometry change and its battery feasibility, without claiming KKT."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

HERE=Path(__file__).resolve().parent
FOLLOW=HERE.parent/'2026-11-15-r2e-feasible-start/initializations/tau7-seed3'
before=json.loads((FOLLOW/'input.json').read_text())
after=json.loads((FOLLOW/'witness.json').read_text())
old=np.array(before['solution']['r']);new=np.array(after['solution']['r'])
fig,(ax,bx)=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
for j in [0,2]:
    region=before['instance']['regions'][j]
    ax.add_patch(Circle(region['o'],region['rho'],fill=False,color='#555555'))
    ax.text(*region['o'],f'Region {j}',ha='center',fontsize=9)
ax.plot(old[20:22,0],old[20:22,1],'--',color='#a84b42',label='Original flight: 15.793 km')
ax.plot(new[19:21,0],new[19:21,1],color='#d08d36',lw=3,label='Charging segment 19 (moving)')
ax.plot(new[20:22,0],new[20:22,1],color='#297da7',label='Repaired flight: 13.066 km')
ax.scatter([old[18,0],old[21,0]],[old[18,1],old[21,1]],marker='*',s=80,color='black')
ax.scatter([old[20,0],new[20,0]],[old[20,1],new[20,1]],s=40,color=['#a84b42','#297da7'])
ax.annotate('r20 before',old[20],xytext=(-5.8,2),arrowprops=dict(arrowstyle='->'),fontsize=9)
ax.annotate('r20 after',new[20],xytext=(-1.5,4.7),arrowprops=dict(arrowstyle='->'),fontsize=9)
ax.set_aspect('equal');ax.set_xlim(-6.5,10.5);ax.set_ylim(-7.5,6)
ax.set_xlabel('x (km)');ax.set_ylabel('y (km)');ax.set_title('One position changes; all modes and tasks retained')
ax.legend(fontsize=8,loc='lower left')
bx.plot(before['solution']['e'],color='#a84b42',label='Original input')
bx.plot(after['solution']['e'],color='#297da7',label='Constructed feasible start')
bx.axhline(0,color='black',lw=.8);bx.axhline(1,color='black',lw=.8,linestyle=':')
bx.axvspan(20,21,color='#aaaaaa',alpha=.2)
bx.set_xlabel('Stamp index');bx.set_ylabel('Battery energy');bx.set_title('Battery replay before any NLP solve')
bx.legend(fontsize=9)
fig.savefig(HERE/'geometry-repair.png',dpi=160)
