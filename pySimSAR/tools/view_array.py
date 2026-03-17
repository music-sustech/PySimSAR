"""CLI tool for visualizing binary array files (.npy, .npz, .csv).

Usage:
    python -m pySimSAR.tools.view_array <file_path> [options]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def load_array(filepath: str, key: str | None = None) -> np.ndarray:
    """Load an array from .npy, .npz, or .csv file.

    Parameters
    ----------
    filepath : str
        Path to the array file.
    key : str | None
        Key for .npz files. If None and file is .npz, lists available keys.

    Returns
    -------
    np.ndarray
        The loaded array.
    """
    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == ".npy":
        return np.load(str(path), allow_pickle=False)
    elif suffix == ".npz":
        npz = np.load(str(path), allow_pickle=False)
        if key is not None:
            if key not in npz:
                available = ", ".join(npz.keys())
                raise KeyError(f"Key '{key}' not found. Available: {available}")
            return npz[key]
        keys = list(npz.keys())
        if len(keys) == 1:
            return npz[keys[0]]
        raise ValueError(
            f".npz file contains multiple arrays: {', '.join(keys)}. "
            f"Use --key to select one."
        )
    elif suffix == ".csv":
        return np.loadtxt(str(path), delimiter=",")
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def describe_array(arr: np.ndarray) -> str:
    """Return a text description of an array."""
    lines = [
        f"Shape: {arr.shape}",
        f"Dtype: {arr.dtype}",
    ]
    if np.issubdtype(arr.dtype, np.complexfloating):
        lines.append(f"Magnitude range: [{np.abs(arr).min():.6g}, {np.abs(arr).max():.6g}]")
        lines.append(f"Phase range: [{np.angle(arr).min():.4f}, {np.angle(arr).max():.4f}] rad")
    elif np.issubdtype(arr.dtype, np.number):
        lines.append(f"Range: [{arr.min():.6g}, {arr.max():.6g}]")
        lines.append(f"Mean: {arr.mean():.6g}")
        lines.append(f"Std: {arr.std():.6g}")
    return "\n".join(lines)


def plot_array(
    arr: np.ndarray,
    *,
    title: str = "",
    cmap: str = "viridis",
    save: str | None = None,
    no_show: bool = False,
    is_positions: bool = False,
) -> None:
    """Plot an array based on its shape and dtype.

    Parameters
    ----------
    arr : np.ndarray
        Array to visualize.
    title : str
        Plot title.
    cmap : str
        Matplotlib colormap name.
    save : str | None
        If provided, save figure to this path.
    no_show : bool
        If True, don't call plt.show().
    is_positions : bool
        If True, treat as (N, 3) position data and use 3D scatter.
    """
    import matplotlib
    if no_show and save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if is_positions and arr.ndim == 2 and arr.shape[1] == 3:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.scatter(arr[:, 0], arr[:, 1], arr[:, 2], s=10)
        ax.set_xlabel("East (m)")
        ax.set_ylabel("North (m)")
        ax.set_zlabel("Up (m)")
        if title:
            ax.set_title(title)
    elif arr.ndim == 1:
        fig, ax = plt.subplots()
        ax.plot(arr)
        ax.set_xlabel("Index")
        ax.set_ylabel("Value")
        if title:
            ax.set_title(title)
        ax.grid(True)
    elif arr.ndim == 2 and np.issubdtype(arr.dtype, np.complexfloating):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        im1 = ax1.imshow(np.abs(arr), cmap=cmap, aspect="auto")
        ax1.set_title("Magnitude" + (f" - {title}" if title else ""))
        plt.colorbar(im1, ax=ax1)
        im2 = ax2.imshow(np.angle(arr), cmap="twilight", aspect="auto")
        ax2.set_title("Phase (rad)")
        plt.colorbar(im2, ax=ax2)
    elif arr.ndim == 2:
        fig, ax = plt.subplots()
        im = ax.imshow(arr, cmap=cmap, aspect="auto")
        plt.colorbar(im, ax=ax)
        if title:
            ax.set_title(title)
    else:
        print(f"Cannot plot {arr.ndim}D array. Use --slice to select a 2D plane.")
        return

    plt.tight_layout()
    if save:
        plt.savefig(save, dpi=150, bbox_inches="tight")
        print(f"Saved to {save}")
    if not no_show:
        plt.show()


def parse_slice(slice_spec: str, ndim: int) -> tuple:
    """Parse a slice specification string like '0,:,:' into a tuple of slices."""
    parts = slice_spec.split(",")
    if len(parts) != ndim:
        raise ValueError(f"Slice spec has {len(parts)} dimensions, array has {ndim}")

    result = []
    for p in parts:
        p = p.strip()
        if p == ":":
            result.append(slice(None))
        elif ":" in p:
            bounds = p.split(":")
            start = int(bounds[0]) if bounds[0] else None
            stop = int(bounds[1]) if bounds[1] else None
            result.append(slice(start, stop))
        else:
            result.append(int(p))
    return tuple(result)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the view_array CLI tool."""
    parser = argparse.ArgumentParser(
        description="Visualize binary array files (.npy, .npz, .csv)"
    )
    parser.add_argument("file", help="Path to array file")
    parser.add_argument("--key", help="Key for .npz files")
    parser.add_argument("--slice", dest="slice_spec", help="Slice spec for 3D+ arrays (e.g., '0,:,:')")
    parser.add_argument("--cmap", default="viridis", help="Matplotlib colormap")
    parser.add_argument("--title", default="", help="Plot title")
    parser.add_argument("--save", help="Save figure to file")
    parser.add_argument("--no-show", action="store_true", help="Don't show interactive plot")

    args = parser.parse_args(argv)

    try:
        arr = load_array(args.file, key=args.key)
    except Exception as e:
        print(f"Error loading file: {e}", file=sys.stderr)
        return 1

    print(describe_array(arr))

    # Apply slice if specified
    if args.slice_spec:
        try:
            idx = parse_slice(args.slice_spec, arr.ndim)
            arr = arr[idx]
            print(f"\nAfter slicing: shape={arr.shape}")
        except Exception as e:
            print(f"Error applying slice: {e}", file=sys.stderr)
            return 1

    # Detect positions data
    is_positions = "positions" in Path(args.file).stem.lower()

    plot_array(
        arr,
        title=args.title or Path(args.file).stem,
        cmap=args.cmap,
        save=args.save,
        no_show=args.no_show,
        is_positions=is_positions,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
