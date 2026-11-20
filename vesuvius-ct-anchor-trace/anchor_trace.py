"""Trace a papyrus sheet between ordered user clicks in a 2D CT slice."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.ndimage import gaussian_filter, gaussian_filter1d, map_coordinates


def _unit_profiles(profiles):
    centered = profiles - profiles.mean(axis=-1, keepdims=True)
    return centered / np.maximum(np.linalg.norm(centered, axis=-1, keepdims=True), 1e-10)


def _trace_segment(image, baseline, band, radius):
    count = len(baseline)
    if count < 6:
        return baseline.copy()
    tangent = baseline[-1] - baseline[0]
    tangent /= np.linalg.norm(tangent)
    normal = np.array([-tangent[1], tangent[0]])
    half_lag = 3
    limit = 3
    search = np.arange(-limit, limit + 1)
    extent = np.arange(-radius - limit, radius + limit + 1)
    xy = baseline[:, None, :] + extent[None, :, None] * normal
    strip = map_coordinates(image, [xy[..., 1], xy[..., 0]], order=1, mode='nearest')
    strip = gaussian_filter1d(strip, 8.0, axis=0, mode='nearest')
    profiles = np.lib.stride_tricks.sliding_window_view(strip, 2 * radius + 1, axis=1)
    profiles = _unit_profiles(profiles)
    samples = np.arange(count)
    lo = np.maximum(samples - half_lag, 0)
    hi = np.minimum(samples + half_lag, count - 1)
    # Estimate the local drift twice, exchanging reference and target so
    # variations of brightness and normal direction do not introduce a bias.
    def match(source, destination):
        corr = np.einsum('ij,ikj->ik', profiles[source, limit], profiles[destination])
        peak = corr.argmax(axis=1)
        rows = np.arange(len(peak))
        peak_value = corr[rows, peak]
        below = corr[rows, np.maximum(0, peak - 1)]
        above = corr[rows, np.minimum(len(search) - 1, peak + 1)]
        curvature = 2 * peak_value - below - above
        fine = np.divide(.5 * (above - below), curvature,
                         out=np.zeros_like(curvature), where=curvature > 1e-8)
        offset = search[peak] + np.clip(fine, -0.5, 0.5)
        reliability = np.clip((peak_value - 0.45) / 0.45, 0, 1)
        reliability[(peak == 0) | (peak == len(search) - 1)] = 0
        return offset, reliability
    forward, quality_f = match(lo, hi)
    backward, quality_b = match(hi, lo)
    consistency = np.exp(-.5 * (forward + backward) ** 2)
    slope = .5 * (forward - backward) * quality_f * quality_b * consistency / (hi - lo)
    offset = np.r_[0., np.cumsum(.5 * (slope[:-1] + slope[1:]))]
    offset -= np.linspace(0, offset[-1], count)
    offset = np.clip(0.20 * offset, -band, band)
    return np.clip(baseline + offset[:, None] * normal, 0, np.array(image.shape[::-1]) - 1)


def follow_trace(image, anchors_xy, band=10, radius=6):
    """Return a pixel-spaced XY path, passing through each ordered anchor exactly.

    Coordinates refer to pixel centers. The radius and search band are in pixels.
    Process separate sheets and separate slices independently.
    """
    image = np.asarray(image)
    anchors = np.asarray(anchors_xy, dtype=float)
    if image.ndim != 2 or not np.issubdtype(image.dtype, np.number) or not np.all(np.isfinite(image)):
        raise ValueError('image must be a finite, two-dimensional numeric array')
    if anchors.ndim != 2 or anchors.shape[1] != 2 or len(anchors) < 2 or not np.all(np.isfinite(anchors)):
        raise ValueError('provide at least two finite x,y anchor coordinates')
    if (anchors < 0).any() or (anchors > np.array(image.shape[::-1]) - 1).any():
        raise ValueError('anchor outside image')
    if np.any(np.linalg.norm(np.diff(anchors, axis=0), axis=1) < 1e-9):
        raise ValueError('adjacent anchors must be distinct')
    if not (isinstance(band, int) and 1 <= band <= 250 and isinstance(radius, int) and 1 <= radius <= 50):
        raise ValueError('band must be an integer from 1 to 250 and radius from 1 to 50')
    smoothed = gaussian_filter(image.astype(np.float64, copy=False), 0.7)
    knots = np.r_[0., np.cumsum(np.linalg.norm(np.diff(anchors, axis=0), axis=1))]
    spline = CubicSpline(knots, anchors, axis=0, bc_type='natural')
    segments = []
    for i, (left, right) in enumerate(zip(knots, knots[1:])):
        samples = np.linspace(left, right, int(np.ceil(right - left)) + 1)
        baseline = np.clip(spline(samples), 0, np.array(image.shape[::-1]) - 1)
        baseline[0], baseline[-1] = anchors[i], anchors[i + 1]
        segments.append(_trace_segment(smoothed, baseline, band, radius))
    return np.concatenate([segments[0]] + [part[1:] for part in segments[1:]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('slice', type=Path, help='2D grayscale TIFF/PNG or NumPy .npy array')
    parser.add_argument('anchors', type=Path, help='CSV without a header, x,y in pixel coordinates')
    parser.add_argument('output', type=Path, help='new CSV containing the traced x,y coordinates')
    parser.add_argument('--band', type=int, default=10, help='maximum distance from each chord in pixels')
    parser.add_argument('--radius', type=int, default=6, help='radius of the reference intensity profile in pixels')
    args = parser.parse_args()
    if args.slice.suffix == '.npy':
        image = np.load(args.slice, allow_pickle=False)
    else:
        from PIL import Image
        with Image.open(args.slice) as source:
            if getattr(source, 'n_frames', 1) != 1:
                parser.error('select one slice first; the input contains multiple images')
            image = np.asarray(source)
    path = follow_trace(image, np.loadtxt(args.anchors, delimiter=',', ndmin=2), args.band, args.radius)
    with args.output.open('x') as destination:
        np.savetxt(destination, path, fmt='%.5f', delimiter=',')


if __name__ == '__main__':
    main()
