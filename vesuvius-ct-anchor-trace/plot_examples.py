"""Regenerate before/after views locally using the original Vesuvius Challenge CT.

The figure shows one near-median case, one benefit and one regression. Selection
uses the nearest improvement (line error minus two-click optical error) to a
preset percentile (10, 50, 90), which avoids hand-picking extremes.
"""
import argparse
import csv
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from benchmark import cases


def make_figure(args):
    sys.path.insert(0, str(Path(args.tracer).resolve().parent))
    from anchor_trace import follow_trace
    with open(args.scores, newline='') as source:
        rows = [r for r in csv.DictReader(source) if r.get('mode', 'two') == 'two'
                and r.get('cohort', 'replication') == 'replication']
    if not rows:
        raise ValueError('need at least one two-click trial to plot')
    gain = np.array([float(r['straight'])-float(r['CT']) for r in rows])
    order = np.argsort(gain)
    fig,axes = plt.subplots(3,2,figsize=(10,8))
    for axis, q in zip(axes, (.10,.50,.90)):
        row = rows[order[round(q*(len(rows)-1))]]
        n,case_index = (int(row[k]) for k in ('sample','case_index'))
        for index, (z, gap, img, click, truth, start) in enumerate(cases(n, args.data)):
            if index==case_index:
                break
        else:
            raise ValueError('Could not locate scored trace')
        anchors = click[1:3]; xa,ya=anchors.T
        x = np.arange(int(xa[0]),int(xa[1])+1)
        y = truth[x-start]; pred = follow_trace(img,anchors)
        box=(int(x.min()-8),int(x.max()+9),max(0,int(y.min())-12),min(img.shape[0]-1,int(y.max())+13))
        lo,hi=np.percentile(img[box[2]:box[3]+1,max(0,box[0]):min(img.shape[1],box[1])+1],[1,99])
        for ax in axis:
            ax.imshow(img,cmap='gray',vmin=lo,vmax=hi,origin='upper')
            ax.set_xlim(box[0],box[1]);ax.set_ylim(box[3],box[2]);ax.set_xticks([]);ax.set_yticks([])
            ax.scatter(xa,ya,c='#ffcc52',s=15,zorder=7,edgecolors='black',linewidths=.4)
        axis[0].plot(x,y,'--',c='#a9ecff',lw=1.2,label='Reference')
        axis[1].plot(x,y,'--',c='#a9ecff',lw=1.1,label='Reference')
        axis[1].plot(pred[:,0],pred[:,1],c='#ff5e61',lw=1.0,label='CT trace')
        axis[1].plot(x,np.interp(x,xa,ya),c='white',lw=.8,label='Straight')
        axis[0].set_title(f'Sample {n}, z={z}; {int(100*q)}th percentile of gain',fontsize=10)
        axis[1].set_title(f'Mean error {float(row["straight"]):.2f} → {float(row["CT"]):.2f} pixels',fontsize=10)
    axes[-1,1].legend(fontsize=7,ncol=3,loc='lower center',bbox_to_anchor=(.5,-.4))
    fig.tight_layout();fig.savefig(args.output,dpi=160,bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tracer',required=True)
    p.add_argument('--data',default='.')
    p.add_argument('--scores',default='case_errors.csv')
    p.add_argument('--output',required=True)
    make_figure(p.parse_args())
