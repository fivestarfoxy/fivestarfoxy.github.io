"""Trace one sheet in a stack with ordered user clicks and save a new 2D mask."""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from anchor_trace import follow_trace


def load_slice(path, index, level):
    if path.is_dir():
        try:
            import zarr
        except ImportError as exc:
            raise ValueError("install zarr to read a Zarr directory") from exc
        array = zarr.open(str(path), mode="r")
        if not hasattr(array, "shape"):
            array = array[level]
    elif path.suffix.lower() == ".npy":
        array = np.load(path, mmap_mode="r", allow_pickle=False)
    else:
        with Image.open(path) as src:
            if not 0 <= index < getattr(src, "n_frames", 1):
                raise ValueError("slice index outside TIFF stack")
            src.seek(index)
            return np.asarray(src.copy())
    if array.ndim == 2 and index == 0:
        return np.asarray(array[:])
    if array.ndim == 3 and 0 <= index < array.shape[0]:
        return np.asarray(array[index])
    raise ValueError("expected a grayscale YX image or ZYX stack and valid slice index")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="grayscale TIFF, NumPy array or local Zarr level/group")
    parser.add_argument("anchors", type=Path, help="ordered x,y CSV, pixel coordinates at chosen level, no header")
    parser.add_argument("output", type=Path, help="new 2D TIFF mask (0 background, 1 traced sheet)")
    parser.add_argument("--z", default=0, type=int, help="zero-based plane index")
    parser.add_argument("--level", default="0", help="array key when opening a multiscale Zarr group")
    args = parser.parse_args()
    if args.output.suffix.lower() not in (".tif", ".tiff"):
        parser.error("the output is a TIFF mask; specify a .tif or .tiff filename")
    if args.output.exists():
        parser.error("output already exists")
    try:
        data = load_slice(args.source, args.z, args.level)
        anchors = np.loadtxt(args.anchors, delimiter=",", ndmin=2)
        path = follow_trace(data, anchors)
    except (KeyError, ValueError, OSError) as exc:
        parser.error(str(exc))
    mask = Image.new("L", (data.shape[1], data.shape[0]))
    ImageDraw.Draw(mask).line([tuple(p) for p in np.rint(path).astype(int)], fill=1, width=1)
    with args.output.open("xb") as output:
        mask.save(output, format="TIFF", compression="tiff_lzw")


if __name__ == "__main__":
    main()
