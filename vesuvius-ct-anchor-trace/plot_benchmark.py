"""Plot aggregate errors without redistributing scans or source label geometry."""
import argparse,csv
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

def plot(source, destination):
    with open(source,newline='') as f:
        rows=list(csv.DictReader(f))
    fig,axes=plt.subplots(1,2,figsize=(10,4.4),sharey=True)
    for ax,mode,title,baseline in zip(axes,('two','four'),('Two clicks vs. straight line','Four clicks vs. parametric cubic'),('straight','parametric')):
        data=sorted((r for r in rows if r['mode']==mode),key=lambda r:int(r['scope'].split('=')[1]))
        labels=[];gains=[]
        for r in data:
            labels.append(f"{int(r['scope'].split('=')[1]):03d}   ({int(r['n'])})")
            gains.append(100*(1-float(r['CT'])/float(r[baseline])))
        y=np.arange(len(data))
        color=['#147770' if v>=0 else '#b65439' for v in gains]
        ax.barh(y,gains,.55,color=color);ax.axvline(0,color='#333',lw=.9)
        ax.set_yticks(y,labels);ax.set_title(title,fontsize=11);ax.set_xlabel('Mean error reduction (%)')
        ax.tick_params(axis='y',length=0)
        ax.spines[['top','right','left']].set_visible(False);ax.grid(axis='x',alpha=.2)
    axes[0].set_ylabel('Sample ID (trace count)')
    axes[0].invert_yaxis()
    fig.tight_layout();fig.savefig(destination,dpi=170,bbox_inches='tight')
    plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('by_sample',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args();plot(args.by_sample,args.output)
