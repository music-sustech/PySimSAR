"""Generate diagnostic plots for Golden Case 1: Single Point Stripmap.

Usage:
    python tests/golden/single_point_stripmap/plot.py [--show]

Saves PNG files to the same directory. Pass --show to display interactively.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pySimSAR.io.parameter_set import load_parameter_set, build_simulation
from pySimSAR.simulation.engine import SimulationEngine
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.types import RawData
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.algorithms.image_formation import image_formation_registry

CASE_DIR = Path(__file__).resolve().parent
SHOW = "--show" in sys.argv


def main():
    print("Loading parameter set...")
    params = load_parameter_set(CASE_DIR)
    sim = build_simulation(params)

    print("Running simulation (256 pulses)...")
    engine = SimulationEngine(
        scene=sim["scene"], radar=sim["radar"],
        platform=sim["platform"], **sim["engine_kwargs"],
    )
    result = engine.run()
    radar = sim["radar"]
    echo = result.echo["single"]

    target_pos = sim["scene"].point_targets[0].position
    ranges = np.array([
        np.linalg.norm(result.positions[i] - target_pos)
        for i in range(echo.shape[0])
    ])
    broadside_idx = np.argmin(ranges)
    R0 = ranges[broadside_idx]
    print(f"Broadside pulse: {broadside_idx}, R0 = {R0:.1f} m")

    # Gate delay for converting bins to range
    gate_near_range = result.gate_delay * C_LIGHT / 2.0
    range_bin_spacing = C_LIGHT / (2.0 * result.sample_rate)
    az_spacing = np.linalg.norm(result.velocities[0]) / radar.waveform.prf

    # --- Plot 1: Range-Compressed Range-Time Diagram ---
    print("Generating Plot 1: Range-Time Diagram (range-compressed)...")
    # Range compress all pulses for the range-time display
    rc_all = np.zeros_like(echo)
    for i in range(echo.shape[0]):
        rc_all[i, :] = radar.waveform.range_compress(echo[i], radar.waveform.prf, result.sample_rate)
    rc_all_dB = 20 * np.log10(np.abs(rc_all) + 1e-30)
    vmax = np.max(rc_all_dB)

    # Convert x-axis to range in meters
    range_axis = gate_near_range + np.arange(echo.shape[1]) * range_bin_spacing

    fig, ax = plt.subplots(figsize=(10, 6))
    # Zoom to region around target
    r_lo_m = R0 - 50
    r_hi_m = R0 + 50
    bin_lo = max(0, int((r_lo_m - gate_near_range) / range_bin_spacing))
    bin_hi = min(echo.shape[1], int((r_hi_m - gate_near_range) / range_bin_spacing))
    im = ax.imshow(
        rc_all_dB[:, bin_lo:bin_hi], aspect="auto", cmap="inferno",
        vmin=vmax - 40, vmax=vmax,
        extent=[range_axis[bin_lo], range_axis[min(bin_hi, len(range_axis)-1)],
                echo.shape[0], 0],
    )
    ax.set_xlabel("Slant range (m)")
    ax.set_ylabel("Pulse index (slow time)")
    ax.set_title("Range-Time Diagram (range-compressed, dB)")
    plt.colorbar(im, ax=ax, label="dB")
    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot1_range_time.png", dpi=150)
    print(f"  Saved: plot1_range_time.png")
    del rc_all  # free memory

    # --- Plot 2: Range-Compressed Broadside Pulse ---
    print("Generating Plot 2: Range-Compressed Broadside Pulse...")
    rc_pulse = radar.waveform.range_compress(echo[broadside_idx], radar.waveform.prf, result.sample_rate)
    rc_mag_dB = 20 * np.log10(np.abs(rc_pulse) + 1e-30)
    rc_peak = np.max(rc_mag_dB)
    rc_peak_bin = np.argmax(np.abs(rc_pulse))

    # Target bin accounting for gate offset
    delay_bin = int(np.round((2 * R0 / C_LIGHT - result.gate_delay) * result.sample_rate))
    margin = 200
    lo = max(0, delay_bin - margin)
    hi = min(len(rc_pulse), delay_bin + margin)

    fig, ax = plt.subplots(figsize=(10, 5))
    range_m = gate_near_range + np.arange(lo, hi) * range_bin_spacing
    ax.plot(range_m, rc_mag_dB[lo:hi])
    target_range_m = gate_near_range + delay_bin * range_bin_spacing
    ax.axvline(target_range_m, color="r", ls="--", alpha=0.5,
               label=f"Target R = {target_range_m:.1f} m")
    ax.set_xlabel("Slant range (m)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_title(f"Range-Compressed Broadside Pulse (pulse {broadside_idx})")
    ax.set_ylim(rc_peak - 50, rc_peak + 5)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot2_range_compressed.png", dpi=150)
    print(f"  Saved: plot2_range_compressed.png")

    # --- Image Formation ---
    print("Running Range-Doppler image formation...")
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
    algo = image_formation_registry.get("range_doppler")()
    phd = algo.range_compress(raw, radar)
    image = algo.azimuth_compress(phd, radar, trajectory)
    img_data = image.data
    img_mag = np.abs(img_data)
    img_dB = 20 * np.log10(img_mag + 1e-30)
    peak_idx = np.unravel_index(np.argmax(img_mag), img_mag.shape)
    peak_dB = img_dB[peak_idx]

    # --- Plot 3: Focused SAR Image (cropped around target) ---
    print("Generating Plot 3: Focused SAR Image...")
    r_margin = 200
    a_margin = 80
    r_lo = max(0, peak_idx[1] - r_margin)
    r_hi = min(img_dB.shape[1], peak_idx[1] + r_margin)
    a_lo = max(0, peak_idx[0] - a_margin)
    a_hi = min(img_dB.shape[0], peak_idx[0] + a_margin)
    crop = img_dB[a_lo:a_hi, r_lo:r_hi]

    # Convert bin indices to slant range (m) and azimuth distance (m)
    r_lo_m = gate_near_range + r_lo * range_bin_spacing
    r_hi_m = gate_near_range + r_hi * range_bin_spacing
    a_lo_m = a_lo * az_spacing
    a_hi_m = a_hi * az_spacing
    peak_r_m = gate_near_range + peak_idx[1] * range_bin_spacing
    peak_a_m = peak_idx[0] * az_spacing

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(
        crop, aspect="auto", cmap="gray",
        vmin=peak_dB - 40, vmax=peak_dB,
        extent=[r_lo_m, r_hi_m, a_hi_m, a_lo_m],
    )
    ax.plot(peak_r_m, peak_a_m, "ro", markersize=18, markerfacecolor="none", markeredgewidth=2)
    ax.set_xlabel("Slant range (m)")
    ax.set_ylabel("Azimuth (m)")
    ax.set_title("Focused SAR Image — cropped around target (RDA, dB)")
    plt.colorbar(im, ax=ax, label="dB")
    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot3_focused_image.png", dpi=150)
    print(f"  Saved: plot3_focused_image.png")

    # --- Plot 4 & 5: Range and Azimuth Impulse Response Cuts ---
    print("Generating Plots 4-5: Impulse Response Cuts...")
    range_cut = img_dB[peak_idx[0], :]
    az_cut = img_dB[:, peak_idx[1]]

    # Range sample spacing
    range_spacing = C_LIGHT / (2 * result.sample_rate)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Range cut
    r_bins = (np.arange(len(range_cut)) - peak_idx[1]) * range_spacing
    r_margin_m = 15
    r_mask = np.abs(r_bins) < r_margin_m
    ax1.plot(r_bins[r_mask], range_cut[r_mask] - peak_dB)
    ax1.axhline(-3, color="r", ls="--", alpha=0.5, label="-3 dB")
    ax1.axhline(-13.3, color="orange", ls="--", alpha=0.5, label="-13.3 dB (sinc sidelobe)")
    ax1.set_xlabel("Range (m)")
    ax1.set_ylabel("Normalized magnitude (dB)")
    ax1.set_title("Range Impulse Response")
    ax1.set_ylim(-40, 3)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Azimuth cut
    a_bins = (np.arange(len(az_cut)) - peak_idx[0]) * az_spacing
    a_margin_m = 30
    a_mask = np.abs(a_bins) < a_margin_m
    ax2.plot(a_bins[a_mask], az_cut[a_mask] - peak_dB)
    ax2.axhline(-3, color="r", ls="--", alpha=0.5, label="-3 dB")
    ax2.set_xlabel("Azimuth (m)")
    ax2.set_ylabel("Normalized magnitude (dB)")
    ax2.set_title("Azimuth Impulse Response")
    ax2.set_ylim(-40, 3)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot4_5_impulse_response.png", dpi=150)
    print(f"  Saved: plot4_5_impulse_response.png")

    if SHOW:
        matplotlib.use("TkAgg")
        plt.show()

    print("Done. All plots saved to", CASE_DIR)


if __name__ == "__main__":
    main()
