"""Score sparse anchor interpolation in real masked Vesuvius scroll CT slices.

The dataset is the organizer's HF bucket. Use fetch_ct.py plus this script.
No CT intensities enter the eligibility rule. Masks supervise only measurement
and placement of sparse clicks, not model selection on held-out samples.
"""
import argparse, csv, math, sys
from pathlib import Path
from time import perf_counter
import numpy as np
from PIL import Image
from scipy.interpolate import CubicSpline, PchipInterpolator


def centers_at_column(col):
    """Centroids of isolated narrow runs of labeled surface pixels."""
    padded = np.r_[False, col == 1, False].astype(np.int8)
    start = np.flatnonzero(np.diff(padded) == 1)
    end = np.flatnonzero(np.diff(padded) == -1)
    widths = end - start
    return (start + end - 1) / 2, widths


def paths_in_window(labels, x0, width):
    centers, widths = zip(*(centers_at_column(labels[:, x]) for x in range(x0, x0 + width + 1)))
    for first, thickness in zip(centers[0], widths[0]):
        if thickness > 8:
            continue
        p = [first]
        for current_centers, current_widths in zip(centers[1:], widths[1:]):
            indices = np.flatnonzero(np.abs(current_centers - p[-1]) <= 3.0)
            if len(indices) != 1 or current_widths[indices[0]] > 8:
                break
            p.append(current_centers[indices[0]])
        if len(p) == len(centers):
            yield np.asarray(p)


def load_slice_pair(sample, z, root='.'):
    name = f'sample_{sample:05}.tif'
    slices = []
    for folder in ('images', 'labels'):
        with Image.open(Path(root) / folder / name) as stack:
            stack.seek(z)
            slices.append(np.asarray(stack.copy()))
    return slices


def cases(sample, root='.'):
    with Image.open(Path(root) / 'labels' / f'sample_{sample:05}.tif') as stack:
        depth = stack.n_frames
    for zi, z in enumerate([int(depth*q) for q in (.1,.3,.5,.7,.9)]):
        img, lab = load_slice_pair(sample, z, root)
        for j, x0 in enumerate([6, int(img.shape[1]*.33), int(img.shape[1]*.615)]):
            gap = [32, 48, 64][(zi+j)%3]
            near = gap//3
            xanchor = np.array([x0,x0+near,x0+near+gap,x0+2*near+gap])
            if xanchor[-1] >= img.shape[1]:
                continue
            for y in paths_in_window(lab, x0, xanchor[-1] - x0):
                anchor_xy = np.column_stack((xanchor, y[xanchor - x0]))
                yield z, gap, img, anchor_xy, y, x0


def inner_prediction(points, anchor_xy, x):
    # Select the actual path between fixed middle clicks; a curved path may
    # wiggle in x. Use nearest linear interpolation for subpixel positions.
    ix = [np.argmin(((points - p)**2).sum(axis=1)) for p in anchor_xy[1:3]]
    sub = points[ix[0]:ix[1]+1]
    if len(sub)<2: raise ValueError("Missing middle pair of supplied anchors")
    # The test applies to graph-shaped labels only. With a steep path, multiple
    # predicted y's can cross a column. Treat the full crossing range honestly
    # by taking the median crossing, and a monotone fast path when possible.
    if np.all(np.diff(sub[:,0]) > 0):
        return np.interp(x, sub[:,0], sub[:,1])
    out=[]
    for col in x:
        a,b=sub[:-1],sub[1:]
        valid = (a[:,0] != b[:,0]) & (np.minimum(a[:,0], b[:,0]) <= col) & (np.maximum(a[:,0], b[:,0]) >= col)
        ypos=a[valid,1]+(col-a[valid,0])*(b[valid,1]-a[valid,1])/(b[valid,0]-a[valid,0])
        if not len(ypos): raise ValueError("Predicted path failed to cover an intermediate column")
        out.append(np.median(ypos))
    return np.array(out)


def evaluate(args):
    sys.path.insert(0, str(Path(args.tracer).resolve().parent))
    from anchor_trace import follow_trace
    allrows=[]
    for sample in args.samples:
        count=0
        for z, gap, image, anchors, truth, x0 in cases(sample, args.data):
            xa, ya = anchors.T
            x = np.arange(xa[1]+3, xa[2]-2).astype(int)
            label = truth[x-x0]
            start=perf_counter()
            predtrace=follow_trace(image, anchors[1:3] if args.two else anchors)
            elapsed=perf_counter()-start
            estimates = {
                'straight': np.interp(x, xa, ya),
                'CT': inner_prediction(np.asarray(predtrace), anchors, x),
            }
            if not args.two:
                arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(anchors, axis=0), axis=1))]
                curve = CubicSpline(arc, anchors, axis=0, bc_type='natural')
                samples = np.unique(np.r_[arc, np.linspace(0, arc[-1], math.ceil(arc[-1]*4) + 1)])
                estimates.update(
                    parametric=inner_prediction(curve(samples), anchors, x),
                    cubic=CubicSpline(xa, ya, bc_type='natural')(x),
                    pchip=PchipInterpolator(xa, ya)(x),
                )
            row={'sample':sample,'case_index':count,'gap':gap,'wall_s':elapsed}
            for method, y in estimates.items():
                err=np.abs(y-label)
                row[method]=np.mean(err)
                row[method+'_95']=np.percentile(err,95)
            allrows.append(row);count+=1
        print(f'{sample}: {count} paths',flush=True)
    if not allrows: raise RuntimeError("No eligible paths")
    with open(args.out,'w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=allrows[0]); w.writeheader();w.writerows(allrows)
    for sample in [*args.samples, 'ALL']:
        subset=[r for r in allrows if r['sample']==sample or sample=='ALL']
        if not subset:continue
        methods = ('straight', 'CT') if args.two else ('straight', 'cubic', 'pchip', 'parametric', 'CT')
        summary = {m: round(float(np.mean([r[m] for r in subset])), 3) for m in methods}
        comparator = 'straight' if args.two else 'parametric'
        summary['improved'] = sum(int(r['CT'] < r[comparator]) for r in subset)
        print(sample,len(subset),summary)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--tracer',required=True);ap.add_argument('--data',default='.')
    ap.add_argument('--two', action='store_true', help='supply only the central click pair; compare to straight line')
    ap.add_argument('--out',default='evaluation.csv');ap.add_argument('samples',nargs='+',type=int)
    evaluate(ap.parse_args())
