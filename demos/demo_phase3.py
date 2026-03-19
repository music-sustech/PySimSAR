"""Phase 3 demo: visualize SAR simulation results.

Runs the simulation engine on a point target grid and produces 4 plots:
1. Target scene layout (top-down view)
2. Range-compressed waterfall (range vs slow time)
3. Range profile (single pulse, decimated for clarity)
4. Phase history at a target range bin
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))

import matplotlib
if "--no-show" in sys.argv or os.environ.get("MPLBACKEND"):
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pySimSAR.core.radar import AntennaPattern, C_LIGHT, Radar
from pySimSAR.core.scene import PointTarget, Scene
from pySimSAR.simulation.engine import SimulationEngine
from pySimSAR.waveforms.lfm import LFMWaveform


def make_antenna(peak_gain_dB: float = 30.0) -> AntennaPattern:
    az = np.linspace(-np.pi, np.pi, 91)
    el = np.linspace(-np.pi / 2, np.pi / 2, 91)
    az_grid, el_grid = np.meshgrid(az, el)
    bw_az, bw_el = np.radians(10), np.radians(10)
    pattern = peak_gain_dB + 20 * np.log10(
        np.abs(np.sinc(az_grid / bw_az) * np.sinc(el_grid / bw_el)) + 1e-30
    )
    return AntennaPattern(
        pattern_2d=pattern, az_beamwidth=bw_az, el_beamwidth=bw_el,
        peak_gain_dB=peak_gain_dB, az_angles=az, el_angles=el,
    )


def decimate_range(data_2d, range_axis, n_bins):
    """Decimate range axis by taking max amplitude per bin."""
    n = data_2d.shape[1]
    bin_sz = max(1, n // n_bins)
    n_use = n_bins * bin_sz
    amp = np.abs(data_2d[:, :n_use]).reshape(data_2d.shape[0], n_bins, bin_sz)
    binned = amp.max(axis=2)
    r_binned = range_axis[:n_use].reshape(n_bins, bin_sz).mean(axis=1)
    return binned, r_binned


def main():
    # --- Scene: 4 well-separated point targets ---
    scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
    alt = 2000.0
    targets = [
        {"pos": [3000, -80, 0], "rcs": 1e6, "label": "T1"},
        {"pos": [4000, 40, 0], "rcs": 1e6, "label": "T2"},
        {"pos": [5000, 0, 0], "rcs": 1e6, "label": "T3"},
        {"pos": [6500, 120, 0], "rcs": 1e6, "label": "T4"},
    ]
    for t in targets:
        scene.add_target(PointTarget(position=t["pos"], rcs=t["rcs"]))

    # --- Radar ---
    wf = LFMWaveform(bandwidth=100e6, duty_cycle=0.1, prf=2000.0)
    antenna = make_antenna(peak_gain_dB=30.0)
    radar = Radar(
        carrier_freq=9.65e9, transmit_power=10000.0,
        waveform=wf, antenna=antenna, polarization="single",
        mode="stripmap", look_side="right", depression_angle=0.5,
        noise_figure=1.0,
    )
    sample_rate = 2.0 * radar.bandwidth

    # --- Platform ---
    platform_start = np.array([0.0, -500.0, alt])
    platform_vel = np.array([0.0, 80.0, 0.0])
    n_pulses = 512

    print(f"Running simulation ({n_pulses} pulses)...")
    engine = SimulationEngine(
        scene=scene, radar=radar, n_pulses=n_pulses,
        platform_start=platform_start, platform_velocity=platform_vel,
        seed=42, sample_rate=sample_rate,
    )
    result = engine.run()
    echo = result.echo["single"]
    print(f"  Echo: {echo.shape[0]} pulses x {echo.shape[1]} range samples")

    print("Range compressing...")
    compressed = radar.waveform.range_compress(echo, radar.waveform.prf, sample_rate)

    # --- Axes ---
    range_m = np.arange(echo.shape[1]) * C_LIGHT / (2.0 * sample_rate)
    time_ms = result.pulse_times * 1000

    # Target slant ranges
    t_slants = []
    for t in targets:
        p = np.array(t["pos"])
        t_slants.append(np.sqrt(p[0]**2 + p[1]**2 + (alt - p[2])**2))

    # ROI crop
    margin = 500
    i0 = max(0, int((min(t_slants) - margin) * 2 * sample_rate / C_LIGHT))
    i1 = min(echo.shape[1], int((max(t_slants) + margin) * 2 * sample_rate / C_LIGHT))
    r_crop = range_m[i0:i1]
    c_crop = compressed[:, i0:i1]

    # ===================== PLOTS =====================
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("PySimSAR  --  Phase 3 Demo", fontsize=15, fontweight="bold", y=0.98)

    # --- 1: Scene layout ---
    ax = axes[0, 0]
    colors = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3"]
    for i, t in enumerate(targets):
        ax.plot(t["pos"][1], t["pos"][0] / 1000, "o", color=colors[i], ms=12,
                markeredgecolor="k", markeredgewidth=1, zorder=5)
        ax.annotate(f'{t["label"]} ({t["pos"][0]/1000:.0f} km)',
                    (t["pos"][1], t["pos"][0] / 1000),
                    textcoords="offset points", xytext=(10, 0), fontsize=9,
                    fontweight="bold", color=colors[i])
    ax.plot(result.positions[:, 1], result.positions[:, 0] / 1000, "b-", lw=2.5,
            alpha=0.6, label="Flight path")
    ax.plot(result.positions[0, 1], result.positions[0, 0] / 1000, "b>", ms=12)
    ax.set_xlabel("Along-track (m)", fontsize=11)
    ax.set_ylabel("Cross-track (km)", fontsize=11)
    ax.set_title("Target Scene (top-down)", fontsize=12)
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(True, alpha=0.3)

    # --- 2: Waterfall (decimated) ---
    ax = axes[0, 1]
    n_disp = 600
    wf_binned, r_binned = decimate_range(c_crop, r_crop, n_disp)
    wf_dB = 20 * np.log10(wf_binned + 1e-30)
    vmax = np.max(wf_dB)
    vmin = vmax - 45
    im = ax.imshow(wf_dB, aspect="auto", cmap="inferno",
                   extent=[r_binned[0] / 1000, r_binned[-1] / 1000,
                           time_ms[-1], time_ms[0]],
                   vmin=vmin, vmax=vmax, interpolation="nearest")
    for i, sr in enumerate(t_slants):
        ax.axvline(sr / 1000, color="cyan", ls="--", alpha=0.7, lw=0.8)
        ax.text(sr / 1000, time_ms[5], f" {targets[i]['label']}",
                color="cyan", fontsize=8, va="top")
    plt.colorbar(im, ax=ax, label="dB", shrink=0.85)
    ax.set_xlabel("Slant Range (km)", fontsize=11)
    ax.set_ylabel("Slow Time (ms)", fontsize=11)
    ax.set_title("Range-Compressed Waterfall", fontsize=12)

    # --- 3: Range profile (decimated for cleaner line) ---
    ax = axes[1, 0]
    mid = n_pulses // 2
    # Decimate single pulse profile
    n_prof = 500
    prof_1d = np.abs(c_crop[mid, :])
    bin_sz = max(1, len(prof_1d) // n_prof)
    n_use = n_prof * bin_sz
    prof_dec = prof_1d[:n_use].reshape(n_prof, bin_sz).max(axis=1)
    r_dec = r_crop[:n_use].reshape(n_prof, bin_sz).mean(axis=1)
    prof_dB = 20 * np.log10(prof_dec + 1e-30)

    ax.fill_between(r_dec / 1000, prof_dB, np.min(prof_dB), alpha=0.3, color="steelblue")
    ax.plot(r_dec / 1000, prof_dB, "k-", lw=1)
    for i, sr in enumerate(t_slants):
        ax.axvline(sr / 1000, color=colors[i], ls="--", alpha=0.7, lw=1.5)
        # Find peak near this range
        idx = np.argmin(np.abs(r_dec - sr))
        ax.plot(r_dec[idx] / 1000, prof_dB[idx], "v", color=colors[i], ms=10,
                markeredgecolor="k", markeredgewidth=0.5)
        ax.annotate(targets[i]["label"], (r_dec[idx] / 1000, prof_dB[idx]),
                    textcoords="offset points", xytext=(8, 2), fontsize=9,
                    fontweight="bold", color=colors[i])
    ax.set_xlabel("Slant Range (km)", fontsize=11)
    ax.set_ylabel("Amplitude (dB)", fontsize=11)
    ax.set_title(f"Range Profile (pulse #{mid})", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(np.median(prof_dB) - 10, np.max(prof_dB) + 5)

    # --- 4: Phase history at T3 ---
    ax = axes[1, 1]
    t3_sr = t_slants[2]
    t3_bin = np.argmin(np.abs(range_m - t3_sr))
    phase_raw = np.angle(compressed[:, t3_bin])
    phase_uw = np.unwrap(phase_raw)
    # Remove linear trend for cleaner view
    poly = np.polyfit(time_ms, phase_uw, 1)
    phase_detrended = phase_uw - np.polyval(poly, time_ms)

    ax.plot(time_ms, phase_uw, "-", color="#4daf4a", lw=1, alpha=0.9)
    ax.set_xlabel("Slow Time (ms)", fontsize=11)
    ax.set_ylabel("Phase (rad)", fontsize=11)
    ax.set_title(f"Phase History at T3 ({t3_sr/1000:.1f} km)", fontsize=12)
    ax.grid(True, alpha=0.3)
    # Doppler info
    dt_s = (time_ms[-1] - time_ms[0]) / 1000
    f_dop = poly[0] / (2 * np.pi) * 1000  # Hz (slope is rad/ms)
    ax.text(0.03, 0.95,
            f"Doppler: {f_dop:.0f} Hz\n"
            f"Phase rate: {poly[0]:.1f} rad/ms",
            transform=ax.transAxes, fontsize=9, va="top",
            bbox=dict(boxstyle="round,pad=0.4", fc="wheat", alpha=0.85))

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out_path = os.path.join(_DIR, "demo_phase3.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved {out_path}")
    plt.show()


if __name__ == "__main__":
    main()
