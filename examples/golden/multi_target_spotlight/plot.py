"""Generate diagnostic plots for Golden Case 2: Multi-Target Spotlight.

Usage:
    python examples/golden/multi_target_spotlight/plot.py [--show]

Saves PNG files to the same directory. Pass --show to display interactively.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pySimSAR.algorithms.image_formation import image_formation_registry
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.types import RawData
from pySimSAR.io.parameter_set import build_simulation, load_parameter_set
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.simulation.engine import SimulationEngine

CASE_DIR = Path(__file__).resolve().parent
SHOW = "--show" in sys.argv


def main():
    print("Loading parameter set...")
    params = load_parameter_set(CASE_DIR)
    sim = build_simulation(params)

    radar = sim["radar"]
    print(f"Running simulation (512 pulses, {radar.mode.value} mode)...")
    engine = SimulationEngine(
        scene=sim["scene"], radar=radar,
        platform=sim["platform"], **sim["engine_kwargs"],
    )
    result = engine.run()
    echo = result.echo["single"]
    print(f"Echo shape: {echo.shape}")

    targets = sim["scene"].point_targets
    target_info = [(t.position, t.rcs) for t in targets]
    print(f"Targets: {len(targets)}")
    for i, (pos, rcs) in enumerate(target_info):
        print(f"  T{i+1}: pos={pos}, RCS={rcs}")

    # Compute axis conversions
    gate_near_range = result.gate_delay * C_LIGHT / 2.0
    range_bin_spacing = C_LIGHT / (2.0 * result.sample_rate)
    az_spacing = np.linalg.norm(result.velocities[0]) / radar.waveform.prf

    # --- Ground truth: compute broadside slant range and azimuth time for each target ---
    gt = []  # list of (label, broadside_range_m, broadside_pulse_idx, broadside_az_m, rcs)
    for i, t in enumerate(targets):
        ranges_to_t = np.array([np.linalg.norm(result.positions[p] - t.position)
                                for p in range(echo.shape[0])])
        bs_idx = np.argmin(ranges_to_t)
        bs_range = ranges_to_t[bs_idx]
        bs_az_m = bs_idx * az_spacing
        gt.append((f"T{i+1}", bs_range, bs_idx, bs_az_m, t.rcs))
        print(f"  Ground truth T{i+1}: R0={bs_range:.1f} m, pulse={bs_idx}, "
              f"az={bs_az_m:.2f} m, RCS={t.rcs}")

    target_colors = ["cyan", "lime", "magenta"]

    # --- Plot 1: Range-Time Diagram (range-compressed) ---
    print("Generating Plot 1: Range-Time Diagram (range-compressed)...")
    rc_all = np.zeros_like(echo)
    for i in range(echo.shape[0]):
        rc_all[i, :] = radar.waveform.range_compress(echo[i], radar.waveform.prf, result.sample_rate)
    rc_dB = 20 * np.log10(np.abs(rc_all) + 1e-30)
    vmax = np.max(rc_dB)

    # Zoom to region around targets
    gt_ranges = [g[1] for g in gt]
    r_center = np.mean(gt_ranges)
    r_margin = max(80, (max(gt_ranges) - min(gt_ranges)) * 2)
    r_lo_m = r_center - r_margin
    r_hi_m = r_center + r_margin
    bin_lo = max(0, int((r_lo_m - gate_near_range) / range_bin_spacing))
    bin_hi = min(echo.shape[1], int((r_hi_m - gate_near_range) / range_bin_spacing))
    range_axis = gate_near_range + np.arange(echo.shape[1]) * range_bin_spacing

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(
        rc_dB[:, bin_lo:bin_hi], aspect="auto", cmap="inferno",
        vmin=vmax - 40, vmax=vmax,
        extent=[range_axis[bin_lo], range_axis[min(bin_hi, len(range_axis)-1)],
                echo.shape[0], 0],
    )
    # Mark ground truth target ranges
    for (label, r0, _, _, rcs), color in zip(gt, target_colors):
        ax.axvline(r0, color=color, ls="--", linewidth=1.5, alpha=0.8,
                   label=f"{label} R0={r0:.1f} m (RCS={rcs})")
    ax.set_xlabel("Slant range (m)")
    ax.set_ylabel("Pulse index (slow time)")
    ax.set_title("Range-Time Diagram — 3 Targets, range-compressed (dB)")
    ax.legend(loc="upper right", fontsize=9)
    plt.colorbar(im, ax=ax, label="dB")
    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot1_range_time.png", dpi=150)
    print("  Saved: plot1_range_time.png")
    del rc_all

    # --- Image Formation ---
    algo_name = "omega_k"
    print(f"Running {algo_name} image formation...")
    raw = RawData(
        echo=echo, channel="single", sample_rate=result.sample_rate,
        carrier_freq=radar.carrier_freq, bandwidth=radar.bandwidth,
        prf=radar.waveform.prf, waveform_name=radar.waveform.name,
        sar_mode=radar.mode.value, gate_delay=result.gate_delay,
    )
    trajectory = Trajectory(
        time=result.pulse_times, position=result.positions,
        velocity=result.velocities,
        attitude=np.zeros((len(result.pulse_times), 3)),
    )
    algo = image_formation_registry.get(algo_name)()
    phd = algo.range_compress(raw, radar)
    image = algo.azimuth_compress(phd, radar, trajectory)
    img_data = image.data
    img_mag = np.abs(img_data)
    img_dB = 20 * np.log10(img_mag + 1e-30)
    peak_dB = np.max(img_dB)

    # --- Plot 2: Focused SAR Image (zoomed to target region) ---
    print("Generating Plot 2: Focused SAR Image...")

    # Compute crop bounds from ground truth positions with margin
    gt_r_bins = [int((g[1] - gate_near_range) / range_bin_spacing) for g in gt]
    gt_a_bins = [g[2] for g in gt]  # broadside pulse index = azimuth bin
    r_margin_bins = 300
    a_margin_bins = 100
    r_lo = max(0, min(gt_r_bins) - r_margin_bins)
    r_hi = min(img_dB.shape[1], max(gt_r_bins) + r_margin_bins)
    a_lo = max(0, min(gt_a_bins) - a_margin_bins)
    a_hi = min(img_dB.shape[0], max(gt_a_bins) + a_margin_bins)
    crop = img_dB[a_lo:a_hi, r_lo:r_hi]

    r_lo_m = gate_near_range + r_lo * range_bin_spacing
    r_hi_m = gate_near_range + r_hi * range_bin_spacing
    a_lo_m = a_lo * az_spacing
    a_hi_m = a_hi * az_spacing

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(
        crop, aspect="auto", cmap="gray",
        vmin=peak_dB - 40, vmax=peak_dB,
        extent=[r_lo_m, r_hi_m, a_hi_m, a_lo_m],
    )
    # Mark ground truth target positions and measure actual peak near each
    for (label, r0, bs_idx, bs_az, rcs), color in zip(gt, target_colors):
        # Search for actual peak near the expected position
        search_r = 30  # meters
        search_a = 20  # bins
        r_bin = int((r0 - gate_near_range) / range_bin_spacing)
        sr_lo = max(0, r_bin - int(search_r / range_bin_spacing))
        sr_hi = min(img_mag.shape[1], r_bin + int(search_r / range_bin_spacing))
        sa_lo = max(0, bs_idx - search_a)
        sa_hi = min(img_mag.shape[0], bs_idx + search_a)
        patch = img_mag[sa_lo:sa_hi, sr_lo:sr_hi]
        if patch.size > 0:
            pk = np.unravel_index(np.argmax(patch), patch.shape)
            actual_r_m = gate_near_range + (sr_lo + pk[1]) * range_bin_spacing
            actual_a_m = (sa_lo + pk[0]) * az_spacing
            actual_dB = img_dB[sa_lo + pk[0], sr_lo + pk[1]]
        else:
            actual_r_m, actual_a_m, actual_dB = r0, bs_az, float("nan")

        # Ground truth crosshair
        ax.plot(r0, bs_az, "+", color=color, markersize=25, markeredgewidth=2.5)
        # Actual detected peak
        ax.plot(actual_r_m, actual_a_m, "o", color=color, markersize=16,
                markerfacecolor="none", markeredgewidth=2)
        ax.annotate(
            f"{label} (RCS={rcs})\nR0={r0:.1f} m\npeak={actual_dB:.1f} dB",
            (r0 + 3, bs_az), color=color, fontsize=9, fontweight="bold",
            verticalalignment="center",
        )
    ax.set_xlabel("Slant range (m)")
    ax.set_ylabel("Azimuth (m)")
    ax.set_title("Focused SAR Image — Hamming Window (dB)\n(+ = ground truth, o = detected peak)")
    plt.colorbar(im, ax=ax, label="dB")
    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot2_focused_image.png", dpi=150)
    print("  Saved: plot2_focused_image.png")

    # --- Plot 3: Range Cut Through Brightest Target ---
    print("Generating Plot 3: Range Cut...")
    # Find the brightest target (highest RCS)
    brightest = max(gt, key=lambda g: g[4])
    brightest_r_bin = int((brightest[1] - gate_near_range) / range_bin_spacing)
    brightest_a_bin = brightest[2]
    # Search for actual peak near expected position
    search_r = int(10 / range_bin_spacing)
    search_a = 10
    patch = img_mag[max(0, brightest_a_bin - search_a):brightest_a_bin + search_a,
                    max(0, brightest_r_bin - search_r):brightest_r_bin + search_r]
    pk = np.unravel_index(np.argmax(patch), patch.shape)
    peak_a = max(0, brightest_a_bin - search_a) + pk[0]
    peak_r = max(0, brightest_r_bin - search_r) + pk[1]

    range_cut = img_dB[peak_a, :]
    peak_val = range_cut[peak_r]
    range_spacing = C_LIGHT / (2 * result.sample_rate)
    peak_range_m = gate_near_range + peak_r * range_spacing

    fig, ax = plt.subplots(figsize=(10, 5))
    # Plot in absolute slant range
    range_m = gate_near_range + np.arange(len(range_cut)) * range_spacing
    r_margin_m = 60
    r_mask = (range_m > peak_range_m - r_margin_m) & (range_m < peak_range_m + r_margin_m)
    ax.plot(range_m[r_mask], range_cut[r_mask] - peak_val)
    ax.axhline(-3, color="r", ls="--", alpha=0.5, label="-3 dB")
    ax.axhline(-42, color="green", ls="--", alpha=0.5, label="-42 dB (Hamming sidelobe)")
    # Mark ground truth ranges of all targets
    for (label, r0, _, _, rcs), color in zip(gt, target_colors):
        ax.axvline(r0, color=color, ls=":", linewidth=1.5, alpha=0.8,
                   label=f"{label} R0={r0:.1f} m")
    ax.set_xlabel("Slant range (m)")
    ax.set_ylabel("Normalized magnitude (dB)")
    ax.set_title(f"Range Cut Through {brightest[0]} (azimuth bin {peak_a})")
    ax.set_ylim(-60, 3)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot3_range_cut.png", dpi=150)
    print("  Saved: plot3_range_cut.png")

    # --- Plot 4: Relative Amplitude Comparison ---
    print("Generating Plot 4: Relative Amplitude Comparison...")
    # Measure peak amplitude near each ground truth target position
    measured = []
    for (label, r0, bs_idx, bs_az, rcs), color in zip(gt, target_colors):
        r_bin = int((r0 - gate_near_range) / range_bin_spacing)
        search_r = int(10 / range_bin_spacing)
        search_a = 20
        sa_lo = max(0, bs_idx - search_a)
        sa_hi = min(img_mag.shape[0], bs_idx + search_a)
        sr_lo = max(0, r_bin - search_r)
        sr_hi = min(img_mag.shape[1], r_bin + search_r)
        patch = img_mag[sa_lo:sa_hi, sr_lo:sr_hi]
        peak_val = np.max(patch) if patch.size > 0 else 1e-30
        peak_dB_val = 20 * np.log10(peak_val + 1e-30)
        measured.append((label, r0, rcs, peak_dB_val))

    fig, ax = plt.subplots(figsize=(8, 5))
    labels_plot = [f"{m[0]}\nR0={m[1]:.0f} m\nRCS={m[2]}" for m in measured]
    amplitudes = [m[3] for m in measured]
    max_amp = max(amplitudes)
    amp_norm = [a - max_amp for a in amplitudes]
    bars = ax.bar(labels_plot, amp_norm, color=target_colors)
    ax.set_ylabel("Relative amplitude (dB)")
    ax.set_title("Relative Target Amplitudes (measured at ground truth positions)")
    ax.grid(True, alpha=0.3, axis="y")

    for bar, amp in zip(bars, amplitudes):
        ax.annotate(
            f"{amp:.1f} dB", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            ha="center", va="bottom", fontsize=10,
        )

    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot4_relative_amplitude.png", dpi=150)
    print("  Saved: plot4_relative_amplitude.png")

    if SHOW:
        matplotlib.use("TkAgg")
        plt.show()

    print("Done. All plots saved to", CASE_DIR)


if __name__ == "__main__":
    main()
