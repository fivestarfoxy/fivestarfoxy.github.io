"""Create a synthetic slice for a local, data-free CLI smoke test."""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(exist_ok=False)
    y, x = np.mgrid[:100, :160]
    trace = 48 - 6 * np.sin(np.pi * x / 159) + 0.10 * x
    img = 140 * np.exp(-0.5 * ((y-trace)/2)**2) + 45 * np.exp(-0.5 * ((y-trace-11)/4)**2)
    rng = np.random.default_rng(13)
    image = np.clip(30 + img + rng.normal(0, 5, img.shape), 0, 255).astype(np.uint8)
    Image.fromarray(image).save(args.destination / "slice.tif")
    clicks_x = np.array([20, 135])
    anchors = np.column_stack((clicks_x, trace[0, clicks_x]))
    np.savetxt(args.destination / "clicks.csv", anchors, fmt="%.6f", delimiter=",")


if __name__ == "__main__":
    main()
