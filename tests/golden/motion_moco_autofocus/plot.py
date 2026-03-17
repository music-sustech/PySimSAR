"""Generate diagnostic plots for Golden Case 3: Motion + MoCo + Autofocus.

Usage:
    python tests/golden/motion_moco_autofocus/plot.py [--show]

Saves PNG files to the same directory. Pass --show to display interactively.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pySimSAR.io.parameter_set import load_parameter_set, build_simulation
from pySimSAR.simulation.engine import SimulationEngine
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.types import RawData
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.algorithms.image_formation import image_formation_registry
from pySimSAR.algorithms.moco.first_order import FirstOrderMoCo
from pySimSAR.sensors.nav_data import NavigationData

CASE_DIR = Path(__file__).resolve().parent
SHOW = "--show" in sys.argv


def make_trajectory(result):
    """Build a Trajectory object from simulation result arrays."""
    return Trajectory(
        time=result.pulse_times,
        position=result.positions,
        velocity=result.velocities,
        attitude=np.zeros((len(result.pulse_times), 3)),
    )


def make_raw(echo, result, radar):
    """Build a RawData object from echo and simulation result."""
    return RawData(
        echo=echo, channel="single", sample_rate=result.sample_rate,
        carrier_freq=radar.carrier_freq, bandwidth=radar.bandwidth,
        prf=radar.prf, waveform_name=radar.waveform.name,
        sar_mode=radar.mode.value, gate_delay=result.gate_delay,
    )


def form_image(raw, radar, trajectory):
    """Range-compress and azimuth-compress using RDA."""
    algo = image_formation_registry.get("range_doppler")()
    phd = algo.range_compress(raw, radar)
    return algo.azimuth_compress(phd, radar, trajectory)


def main():
    print("Loading parameter set...")
    params = load_parameter_set(CASE_DIR)
    sim = build_simulation(params)

    radar = sim["radar"]
    print("Running simulation (512 pulses, Dryden turbulence)...")
    engine = SimulationEngine(
        scene=sim["scene"], radar=radar,
        platform=sim["platform"], **sim["engine_kwargs"],
    )
    result = engine.run()
    echo = result.echo["single"]
    print(f"Echo shape: {echo.shape}")

    ideal_traj = result.ideal_trajectory
    true_traj = result.true_trajectory
    target_pos = sim["scene"].point_targets[0].position

    # Axis conversions
    gate_near_range = result.gate_delay * C_LIGHT / 2.0
    range_bin_spacing = C_LIGHT / (2.0 * result.sample_rate)
    az_spacing = np.linalg.norm(result.velocities[0]) / radar.prf
    t = result.pulse_times

    # Ground truth
    R_ideal = np.array([np.linalg.norm(ideal_traj.position[i] - target_pos)
                        for i in range(len(t))])
    bs_idx = np.argmin(R_ideal)
    R0 = R_ideal[bs_idx]
    print(f"Target: pos={target_pos}, R0={R0:.1f} m, broadside pulse={bs_idx}")

    # --- Plot 1: Trajectory Comparison ---
    print("Generating Plot 1: Trajectory Comparison...")
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    labels = ["East (m)", "North (m)", "Up (m)"]

    for i, (ax, lbl) in enumerate(zip(axes, labels)):
        ax.plot(t, ideal_traj.position[:, i], "b-", label="Ideal", linewidth=1)
        ax.plot(t, true_traj.position[:, i], "r-", label="Perturbed", linewidth=1, alpha=0.8)
        ax.set_ylabel(lbl)
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)

    axes[0].set_title("Platform Trajectory: Ideal vs Perturbed (Dryden Turbulence)")
    axes[-1].set_xlabel("Time (s)")
    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot1_trajectory.png", dpi=150)
    print(f"  Saved: plot1_trajectory.png")

    # --- Plot 2: Position Error vs Pulse ---
    print("Generating Plot 2: Position Error...")
    diff = true_traj.position - ideal_traj.position
    dist = np.linalg.norm(diff, axis=1)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    for i, (lbl, color) in enumerate(zip(["East", "North", "Up"], ["tab:blue", "tab:orange", "tab:green"])):
        ax1.plot(t, diff[:, i], color=color, label=lbl, linewidth=1)
    ax1.set_ylabel("Position error (m)")
    ax1.set_title("Position Error Components (True - Ideal)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(t, dist, "k-", linewidth=1)
    ax2.set_ylabel("3D distance (m)")
    ax2.set_xlabel("Time (s)")
    ax2.set_title(f"Total Position Deviation (max = {np.max(dist):.3f} m)")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot2_position_error.png", dpi=150)
    print(f"  Saved: plot2_position_error.png")

    # --- Image Formation: 3 variants ---
    raw = make_raw(echo, result, radar)

    # (a) Ideal reference — run separate simulation without perturbation
    print("Running ideal reference simulation (no perturbation)...")
    from pySimSAR.core.platform import Platform as _Platform
    ideal_platform = _Platform(
        velocity=sim["platform"].velocity,
        altitude=sim["platform"].altitude,
        heading=sim["platform"].heading,
        start_position=sim["platform"].start_position,
        perturbation=None,
    )
    ideal_engine = SimulationEngine(
        scene=sim["scene"], radar=radar,
        platform=ideal_platform, **sim["engine_kwargs"],
    )
    ideal_result = ideal_engine.run()
    ideal_raw = make_raw(ideal_result.echo["single"], ideal_result, radar)
    ideal_ref_traj = ideal_result.ideal_trajectory
    img_ideal = form_image(ideal_raw, radar, ideal_ref_traj)

    # (b) Perturbed echo, no MoCo — shows defocus
    print("Running image formation with perturbed echo (no MoCo)...")
    img_no_moco = form_image(raw, radar, ideal_traj)

    # (c) Perturbed echo + first-order MoCo
    print("Applying first-order MoCo...")
    nav_data = NavigationData(
        time=true_traj.time,
        position=true_traj.position,
        velocity=true_traj.velocity,
        source="fused",
    )
    moco = FirstOrderMoCo(scene_center=target_pos)
    compensated_raw = moco.compensate(raw, nav_data, ideal_traj)
    print("Running image formation with MoCo-corrected data...")
    img_moco = form_image(compensated_raw, radar, ideal_traj)

    # --- Plot 3: Focused Image Comparison (3 panels) ---
    print("Generating Plot 3: Focused Image Comparison...")
    images = [
        (img_ideal.data, "Ideal (No Perturbation)"),
        (img_no_moco.data, "Perturbed, No MoCo"),
        (img_moco.data, "Perturbed + 1st-Order MoCo"),
    ]

    # Crop around target — use ideal image peak as anchor
    ref_mag = np.abs(img_ideal.data)
    peak_idx = np.unravel_index(np.argmax(ref_mag), ref_mag.shape)
    r_margin = 200
    a_margin = 80
    r_lo = max(0, peak_idx[1] - r_margin)
    r_hi = min(ref_mag.shape[1], peak_idx[1] + r_margin)
    a_lo = max(0, peak_idx[0] - a_margin)
    a_hi = min(ref_mag.shape[0], peak_idx[0] + a_margin)

    r_lo_m = gate_near_range + r_lo * range_bin_spacing
    r_hi_m = gate_near_range + r_hi * range_bin_spacing
    a_lo_m = a_lo * az_spacing
    a_hi_m = a_hi * az_spacing

    # Use ideal image peak as common reference
    ref_peak_dB = 20 * np.log10(np.max(ref_mag) + 1e-30)

    fig, axes = plt.subplots(1, 3, figsize=(18, 7))
    for ax, (data, title) in zip(axes, images):
        mag = np.abs(data)
        dB = 20 * np.log10(mag + 1e-30)
        crop = dB[a_lo:a_hi, r_lo:r_hi]
        peak_val = np.max(dB)
        im = ax.imshow(
            crop, aspect="auto", cmap="gray",
            vmin=ref_peak_dB - 40, vmax=ref_peak_dB,
            extent=[r_lo_m, r_hi_m, a_hi_m, a_lo_m],
        )
        # Mark ground truth
        gt_r_m = gate_near_range + peak_idx[1] * range_bin_spacing
        gt_a_m = peak_idx[0] * az_spacing
        ax.plot(gt_r_m, gt_a_m, "+", color="cyan", markersize=20, markeredgewidth=2)
        ax.set_xlabel("Slant range (m)")
        ax.set_ylabel("Azimuth (m)")
        ax.set_title(f"{title}\npeak = {peak_val:.1f} dB")
        plt.colorbar(im, ax=ax, label="dB", shrink=0.8)

    fig.suptitle("Focused SAR Images — Effect of Motion Compensation", fontsize=14)
    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot3_image_comparison.png", dpi=150)
    print(f"  Saved: plot3_image_comparison.png")

    # --- Plot 4: Azimuth Cuts Comparison ---
    print("Generating Plot 4: Azimuth Cuts...")
    fig, ax = plt.subplots(figsize=(10, 6))
    colors_az = ["tab:blue", "tab:red", "tab:green"]
    labels_az = ["Ideal (no perturbation)", "Perturbed, no MoCo", "Perturbed + MoCo"]

    for (data, _), color, label in zip(images, colors_az, labels_az):
        mag = np.abs(data)
        # Find peak in this image
        pk = np.unravel_index(np.argmax(mag), mag.shape)
        az_cut = 20 * np.log10(mag[:, pk[1]] + 1e-30)
        peak_val = np.max(az_cut)
        az_m = (np.arange(len(az_cut)) - pk[0]) * az_spacing
        a_mask = np.abs(az_m) < 15
        ax.plot(az_m[a_mask], az_cut[a_mask] - peak_val, color=color, label=label, linewidth=1.5)

    ax.axhline(-3, color="gray", ls="--", alpha=0.5, label="-3 dB")
    ax.set_xlabel("Azimuth (m)")
    ax.set_ylabel("Normalized magnitude (dB)")
    ax.set_title("Azimuth Impulse Response — Ideal vs Perturbed vs MoCo")
    ax.set_ylim(-40, 3)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot4_azimuth_cuts.png", dpi=150)
    print(f"  Saved: plot4_azimuth_cuts.png")

    # Free image arrays
    del img_ideal, img_no_moco, img_moco, compensated_raw

    # --- Plot 5: Phase Error Along Aperture ---
    print("Generating Plot 5: Phase Error Along Aperture...")
    R_true = np.array([np.linalg.norm(true_traj.position[i] - target_pos)
                       for i in range(len(t))])
    dR = R_true - R_ideal
    wavelength = C_LIGHT / radar.carrier_freq
    phase_error = 4 * np.pi * dR / wavelength

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    ax1.plot(t, dR * 1000, "b-", linewidth=1)  # mm
    ax1.set_ylabel("Range error (mm)")
    ax1.set_title("Slant Range Error: R_true - R_ideal")
    ax1.grid(True, alpha=0.3)

    ax2.plot(t, phase_error, "r-", linewidth=1)
    ax2.set_ylabel("Phase error (rad)")
    ax2.set_xlabel("Time (s)")
    ax2.set_title(f"Motion-Induced Phase Error: 4pi*dR/lambda (max = {np.max(np.abs(phase_error)):.1f} rad)")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(CASE_DIR / "plot5_phase_error.png", dpi=150)
    print(f"  Saved: plot5_phase_error.png")

    # --- Summary ---
    print("\nSummary:")
    print(f"  Max position deviation: {np.max(dist):.3f} m")
    print(f"  Max range error: {np.max(np.abs(dR))*1000:.1f} mm")
    print(f"  Max phase error: {np.max(np.abs(phase_error)):.1f} rad ({np.max(np.abs(phase_error))/(2*np.pi):.1f} cycles)")

    if SHOW:
        matplotlib.use("TkAgg")
        plt.show()

    print("\nDone. All plots saved to", CASE_DIR)


if __name__ == "__main__":
    main()
