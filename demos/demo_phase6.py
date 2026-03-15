"""Phase 6 demo: SAR Image Formation with 3 algorithms.

Simulates a multi-target scene and forms focused SAR images using all
three image formation algorithms:
1. Range-Doppler Algorithm (RDA)
2. Chirp Scaling Algorithm (CSA)
3. Omega-K Algorithm

Produces a 3x3 figure:
  Row 1: Full-scene SAR image (all targets visible)
  Row 2: Range impulse response cut through each target
  Row 3: Azimuth impulse response cut through each target

Uses --replot flag to skip simulation/imaging and only redo the plot
from cached .npz data.
"""

import os
import sys

import matplotlib
if "--no-show" in sys.argv or os.environ.get("MPLBACKEND"):
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pySimSAR.core.radar import C_LIGHT

_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(_DIR, "demo_phase6_cache.npz")


def simulate_and_image():
    """Run simulation + image formation, return results."""
    from pySimSAR.core.radar import AntennaPattern, Radar
    from pySimSAR.core.scene import PointTarget, Scene
    from pySimSAR.core.types import RawData
    from pySimSAR.motion.trajectory import Trajectory
    from pySimSAR.simulation.engine import SimulationEngine
    from pySimSAR.waveforms.lfm import LFMWaveform
    from pySimSAR.algorithms.image_formation import (
        RangeDopplerAlgorithm,
        ChirpScalingAlgorithm,
        OmegaKAlgorithm,
    )

    # --- Antenna (sinc pattern) ---
    az = np.linspace(-np.pi, np.pi, 91)
    el = np.linspace(-np.pi / 2, np.pi / 2, 91)
    az_grid, el_grid = np.meshgrid(az, el)
    bw_az, bw_el = np.radians(10), np.radians(10)
    pattern = 30.0 + 20 * np.log10(
        np.abs(np.sinc(az_grid / bw_az) * np.sinc(el_grid / bw_el)) + 1e-30
    )
    antenna = AntennaPattern(
        pattern_2d=pattern, az_beamwidth=bw_az, el_beamwidth=bw_el,
        peak_gain_dB=30.0, az_angles=az, el_angles=el,
    )

    # --- Scene ---
    scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
    target_specs = [
        [3000, 0, 0, 1e4],
        [4000, 0, 0, 1e4],
        [5000, 0, 0, 1e4],
    ]
    for pos_x, pos_y, pos_z, rcs in target_specs:
        scene.add_target(PointTarget(position=[pos_x, pos_y, pos_z], rcs=rcs))

    # --- Radar ---
    wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1)
    radar = Radar(
        carrier_freq=9.65e9, prf=1000.0, transmit_power=1000.0,
        waveform=wf, antenna=antenna, polarization="single",
        mode="stripmap", look_side="right", depression_angle=0.0,
        noise_figure=3.0,
    )
    sample_rate = 2.0 * radar.bandwidth

    # --- Platform ---
    V = 100.0
    n_pulses = 512
    aperture_length = V * n_pulses / radar.prf
    y_start = -aperture_length / 2.0

    print(f"Simulating {len(target_specs)} targets, {n_pulses} pulses...")
    engine = SimulationEngine(
        scene=scene, radar=radar, n_pulses=n_pulses,
        platform_start=np.array([0.0, y_start, 0.0]),
        platform_velocity=np.array([0.0, V, 0.0]),
        seed=42, sample_rate=sample_rate,
    )
    result = engine.run()
    echo = result.echo["single"]
    print(f"  Echo shape: {echo.shape}")

    raw_data = RawData(
        echo=echo, channel="single", sample_rate=sample_rate,
        carrier_freq=radar.carrier_freq, bandwidth=radar.bandwidth,
        prf=radar.prf, waveform_name="lfm", sar_mode="stripmap",
    )
    trajectory = Trajectory(
        time=result.pulse_times, position=result.positions,
        velocity=result.velocities, attitude=np.zeros((n_pulses, 3)),
    )

    # --- Image Formation ---
    algorithms = [
        ("Range-Doppler (RDA)", RangeDopplerAlgorithm()),
        ("Chirp Scaling (CSA)", ChirpScalingAlgorithm()),
        ("Omega-K", OmegaKAlgorithm()),
    ]

    image_data = []
    for name, algo in algorithms:
        print(f"Forming image with {name}...")
        img = algo.process(raw_data, radar, trajectory)
        image_data.append(img.data)
        mag = np.abs(img.data)
        print(f"  Peak/median = {np.max(mag)/np.median(mag):.0f}x "
              f"({20*np.log10(np.max(mag)/np.median(mag)):.0f} dB)")

    pixel_spacing_range = C_LIGHT / (2.0 * radar.bandwidth)
    pixel_spacing_azimuth = V / radar.prf

    # Cache results
    np.savez_compressed(
        CACHE_FILE,
        image0=image_data[0], image1=image_data[1], image2=image_data[2],
        sample_rate=sample_rate, bandwidth=radar.bandwidth,
        pixel_spacing_range=pixel_spacing_range,
        pixel_spacing_azimuth=pixel_spacing_azimuth,
        n_pulses=n_pulses,
        target_positions=np.array([[t[0], t[1], t[2]] for t in target_specs]),
    )
    print(f"  Cached to {CACHE_FILE}")

    return image_data, sample_rate, radar.bandwidth, pixel_spacing_range, \
        pixel_spacing_azimuth, n_pulses, target_specs


def load_cache():
    """Load cached image data."""
    d = np.load(CACHE_FILE)
    image_data = [d["image0"], d["image1"], d["image2"]]
    target_positions = d["target_positions"]
    target_specs = [[float(r[0]), float(r[1]), float(r[2]), 1e4]
                    for r in target_positions]
    return (image_data, float(d["sample_rate"]), float(d["bandwidth"]),
            float(d["pixel_spacing_range"]), float(d["pixel_spacing_azimuth"]),
            int(d["n_pulses"]), target_specs)


def plot(image_data, sample_rate, bandwidth, pixel_spacing_range,
         pixel_spacing_azimuth, n_pulses, target_specs):
    """Generate the 3x3 figure."""
    range_bin_spacing = C_LIGHT / (2.0 * sample_rate)
    theoretical_rng_res = C_LIGHT / (2.0 * bandwidth)
    n_rng = image_data[0].shape[1]

    targets = [
        {"pos": s[:3], "rcs": s[3], "label": f"T{i+1} ({s[0]/1000:.0f} km)"}
        for i, s in enumerate(target_specs)
    ]
    t_slants = [np.linalg.norm(t["pos"]) for t in targets]

    algo_names = ["Range-Doppler (RDA)", "Chirp Scaling (CSA)", "Omega-K"]
    algo_colors = ["#e41a1c", "#377eb8", "#4daf4a"]
    target_colors = ["#ff7f00", "#984ea3", "#a65628"]

    fig, axes = plt.subplots(3, 3, figsize=(17, 14))
    fig.suptitle("PySimSAR  —  Phase 6 Demo: Image Formation",
                 fontsize=16, fontweight="bold", y=0.995)

    for col in range(3):
        full_mag = np.abs(image_data[col])
        name = algo_names[col]

        # Find peaks
        peaks = []
        for t_sr in t_slants:
            t_bin = int(t_sr / range_bin_spacing)
            search_rng = 100
            rng_lo = max(0, t_bin - search_rng)
            rng_hi = min(n_rng, t_bin + search_rng)
            local = full_mag[:, rng_lo:rng_hi]
            local_peak = np.unravel_index(np.argmax(local), local.shape)
            peaks.append((local_peak[0], local_peak[1] + rng_lo))

        # --- Row 1: Full scene image ---
        ax = axes[0, col]

        # Crop range: from before T1 to after T3, with margin
        margin_m = 500  # meters
        rng_lo_bin = max(0, int((t_slants[0] - margin_m) / range_bin_spacing))
        rng_hi_bin = min(n_rng, int((t_slants[-1] + margin_m) / range_bin_spacing))

        crop = full_mag[:, rng_lo_bin:rng_hi_bin]

        # Decimate range for display (max-pool to ~800 display columns)
        n_disp_cols = 800
        bin_size = max(1, crop.shape[1] // n_disp_cols)
        n_use = (crop.shape[1] // bin_size) * bin_size
        crop_dec = crop[:, :n_use].reshape(crop.shape[0], -1, bin_size).max(axis=2)

        crop_dB = 20 * np.log10(crop_dec + 1e-30)
        vmax = np.max(crop_dB)
        vmin = vmax - 50

        range_axis_km = np.array([rng_lo_bin, rng_lo_bin + n_use]) * range_bin_spacing / 1000
        az_axis_m = np.array([0, n_pulses]) * pixel_spacing_azimuth

        im = ax.imshow(
            crop_dB, aspect="auto", cmap="inferno",
            extent=[range_axis_km[0], range_axis_km[1],
                    az_axis_m[1], az_axis_m[0]],
            vmin=vmin, vmax=vmax, interpolation="nearest",
        )
        # Mark targets with hollow circles
        for i, (peak_az, peak_rng) in enumerate(peaks):
            peak_range_km = peak_rng * range_bin_spacing / 1000
            peak_az_m = peak_az * pixel_spacing_azimuth
            ax.plot(peak_range_km, peak_az_m, "o", color=target_colors[i],
                    ms=20, mew=2, mfc="none", zorder=5)
            ax.annotate(targets[i]["label"],
                        (peak_range_km, peak_az_m),
                        textcoords="offset points", xytext=(14, -4),
                        fontsize=8, fontweight="bold", color=target_colors[i])

        ax.set_title(name, fontsize=13, fontweight="bold", color=algo_colors[col])
        ax.set_xlabel("Slant Range (km)", fontsize=10)
        if col == 0:
            ax.set_ylabel("Azimuth (m)", fontsize=10)
        plt.colorbar(im, ax=ax, label="dB", shrink=0.85, pad=0.02)

        # --- Row 2: Range impulse response cuts ---
        ax = axes[1, col]
        peak_az_t2, peak_rng_t2 = peaks[1]

        for i, (peak_az, peak_rng) in enumerate(peaks):
            cut_half = 50
            rng_lo_cut = max(0, peak_rng - cut_half)
            rng_hi_cut = min(n_rng, peak_rng + cut_half)
            range_cut = full_mag[peak_az, rng_lo_cut:rng_hi_cut]
            range_cut_norm = range_cut / np.max(range_cut)
            range_cut_dB = 20 * np.log10(range_cut_norm + 1e-30)
            r_offset_m = (np.arange(rng_lo_cut, rng_hi_cut) - peak_rng) * range_bin_spacing

            ax.plot(r_offset_m, range_cut_dB, "-", color=target_colors[i],
                    lw=1.8, label=targets[i]["label"], alpha=0.9)

        ax.axhline(-3, color="gray", ls=":", lw=1, alpha=0.7)
        ax.text(0.97, -3 + 0.5, "-3 dB", ha="right", fontsize=8, color="gray",
                transform=matplotlib.transforms.blended_transform_factory(
                    ax.transAxes, ax.transData))
        ax.set_xlabel("Range offset (m)", fontsize=10)
        if col == 0:
            ax.set_ylabel("Normalized (dB)", fontsize=10)
        ax.set_ylim(-35, 3)
        ax.set_xlim(-20, 20)
        ax.set_title("Range Impulse Response", fontsize=11)
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(True, alpha=0.3)

        rng_cut_lin = full_mag[peak_az_t2, max(0, peak_rng_t2-50):peak_rng_t2+50]
        thresh_3dB = np.max(rng_cut_lin) / np.sqrt(2)
        rng_3dB = np.sum(rng_cut_lin >= thresh_3dB) * range_bin_spacing
        ax.text(0.03, 0.05,
                f"Range res (T2): {rng_3dB:.2f}m\n"
                f"Theory: {theoretical_rng_res:.2f}m",
                transform=ax.transAxes, fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", fc="wheat", alpha=0.85))

        # --- Row 3: Azimuth impulse response cuts ---
        ax = axes[2, col]

        for i, (peak_az, peak_rng) in enumerate(peaks):
            az_cut = full_mag[:, peak_rng]
            az_cut_norm = az_cut / np.max(az_cut)
            az_cut_dB = 20 * np.log10(az_cut_norm + 1e-30)
            az_offset_m = (np.arange(n_pulses) - peak_az) * pixel_spacing_azimuth

            ax.plot(az_offset_m, az_cut_dB, "-", color=target_colors[i],
                    lw=1.8, label=targets[i]["label"], alpha=0.9)

        ax.axhline(-3, color="gray", ls=":", lw=1, alpha=0.7)
        ax.text(0.97, -3 + 0.5, "-3 dB", ha="right", fontsize=8, color="gray",
                transform=matplotlib.transforms.blended_transform_factory(
                    ax.transAxes, ax.transData))
        ax.set_xlabel("Azimuth offset (m)", fontsize=10)
        if col == 0:
            ax.set_ylabel("Normalized (dB)", fontsize=10)
        ax.set_ylim(-35, 3)
        ax.set_xlim(-8, 8)
        ax.set_title("Azimuth Impulse Response", fontsize=11)
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(True, alpha=0.3)

        az_cut_lin = full_mag[:, peaks[1][1]]
        thresh_az = np.max(az_cut_lin) / np.sqrt(2)
        az_3dB = np.sum(az_cut_lin >= thresh_az) * pixel_spacing_azimuth
        peak_snr = 20 * np.log10(np.max(full_mag) / np.median(full_mag))
        ax.text(0.03, 0.05,
                f"Azimuth res (T2): {az_3dB:.2f}m\n"
                f"Peak SNR: {peak_snr:.0f} dB",
                transform=ax.transAxes, fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", fc="wheat", alpha=0.85))

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out_path = os.path.join(_DIR, "demo_phase6.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nSaved {out_path}")
    plt.show()


def main():
    replot = "--replot" in sys.argv

    if replot and os.path.exists(CACHE_FILE):
        print(f"Loading cached data from {CACHE_FILE}...")
        data = load_cache()
    else:
        data = simulate_and_image()

    plot(*data)


if __name__ == "__main__":
    main()
