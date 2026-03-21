import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import interp1d


def simulate_fmcw_radar():
    # ---------------------------------------------------------
    # 1. System and Target Parameters
    # ---------------------------------------------------------
    c = 3e8              # Speed of light (m/s)
    fc = 77e9            # Carrier frequency (77 GHz)
    B = 1e9              # Chirp bandwidth (1 GHz)
    Tc = 50e-6           # Chirp duration (50 us)
    fs = 50e6            # Sampling frequency (50 MHz)

    R0 = 150.0           # Target initial range (150 m)
    v = 30.0             # Target radial velocity (30 m/s moving away)

    K = B / Tc           # Chirp slope (Hz/s)

    # Fast-time vector
    t = np.arange(0, Tc, 1/fs)
    N = len(t)

    # ---------------------------------------------------------
    # 2. Phase Noise Generation (1/f Pink Noise model)
    # ---------------------------------------------------------
    # We generate a realistic phase noise profile in the frequency
    # domain and transform it to the time domain.
    freqs = np.fft.rfftfreq(N, 1/fs)
    freqs[0] = freqs[1]  # Avoid divide-by-zero at DC
    psd = 1 / freqs      # 1/f power spectral density

    # Generate random phases for the noise spectrum
    random_phases = np.random.uniform(0, 2*np.pi, len(freqs))
    complex_spectrum = np.sqrt(psd) * np.exp(1j * random_phases)

    phi_pn = np.fft.irfft(complex_spectrum, n=N)
    # Scale phase noise standard deviation to a noticeable level for simulation
    phi_pn = (phi_pn / np.std(phi_pn)) * 0.1

    # ---------------------------------------------------------
    # 3. Kinematics and Continuous Time Delay
    # ---------------------------------------------------------
    # This is where the within-pulse motion is modeled!
    # tau(t) is not a constant; it grows as the target moves during the chirp.
    tau = 2 * (R0 + v * t) / c

    # ---------------------------------------------------------
    # 4. Signal Construction (Baseband Equivalents)
    # ---------------------------------------------------------
    # Transmit signal phase
    phase_tx = 2 * np.pi * fc * t + np.pi * K * t**2 + phi_pn
    s_tx = np.exp(1j * phase_tx)

    # Receive signal requires the delayed time: t_delayed = t - tau(t)
    t_delayed = t - tau

    # Interpolate phase noise for the exact delayed moments.
    # If t_delayed < 0 (before the first reflection arrives), we pad with the initial phase.
    interp_func = interp1d(t, phi_pn, bounds_error=False, fill_value=(phi_pn[0], phi_pn[-1]))
    phi_pn_delayed = interp_func(t_delayed)

    # Receive signal phase
    phase_rx = 2 * np.pi * fc * t_delayed + np.pi * K * t_delayed**2 + phi_pn_delayed
    s_rx = np.exp(1j * phase_rx)

    # ---------------------------------------------------------
    # 5. The Mixer (De-chirping)
    # ---------------------------------------------------------
    # Mix the signals (multiply Tx by the complex conjugate of Rx)
    s_beat = s_tx * np.conjugate(s_rx)

    # ---------------------------------------------------------
    # 6. Spectral Analysis (FFT)
    # ---------------------------------------------------------
    # Apply a Hanning window to reduce spectral leakage
    window = np.hanning(N)
    s_beat_windowed = s_beat * window

    # Compute FFT
    fft_result = np.fft.fft(s_beat_windowed)
    fft_freqs = np.fft.fftfreq(N, 1/fs)

    # Keep only the positive frequencies for the plot
    pos_idx = np.where(fft_freqs >= 0)
    fft_freqs_pos = fft_freqs[pos_idx]
    fft_mag_db = 20 * np.log10(np.abs(fft_result[pos_idx]) + 1e-12)

    # Normalize the peak to 0 dB for easy viewing
    fft_mag_db -= np.max(fft_mag_db)

    # ---------------------------------------------------------
    # 7. Calculate Theoretical Frequencies for Verification
    # ---------------------------------------------------------
    f_beat_theoretical = (2 * K * R0) / c
    f_doppler_theoretical = (2 * v * fc) / c
    f_expected = f_beat_theoretical + f_doppler_theoretical

    print(f"Theoretical Beat Freq (Range):   {f_beat_theoretical/1e6:.3f} MHz")
    print(f"Theoretical Doppler Freq:        {f_doppler_theoretical:.3f} Hz")
    print(f"Total Expected Peak:             {f_expected/1e6:.3f} MHz")

    # ---------------------------------------------------------
    # 8. Plotting
    # ---------------------------------------------------------
    plt.figure(figsize=(12, 6))

    # Plot 1: The Phase Noise Time-Domain Profile
    plt.subplot(1, 2, 1)
    plt.plot(t * 1e6, phi_pn)
    plt.title(r"Simulated LO Phase Noise $\phi_{pn}(t)$")
    plt.xlabel("Fast Time (us)")
    plt.ylabel("Phase Deviation (rad)")
    plt.grid(True)

    # Plot 2: The Beat Signal Spectrum
    plt.subplot(1, 2, 2)
    plt.plot(fft_freqs_pos / 1e6, fft_mag_db)
    plt.axvline(x=f_expected / 1e6, color='r', linestyle='--', label=f'Expected: {f_expected/1e6:.3f} MHz')
    plt.xlim(0, 30) # Zoom in up to 30 MHz
    plt.ylim(-100, 5)
    plt.title("Beat Signal Spectrum (Range Profile)")
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Magnitude (dB)")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    simulate_fmcw_radar()


"""
Code Architecture Breakdown — Continuous Kinematics Check:

 * Notice how tau is calculated as an array based on the t array.
   By plugging t_delayed directly into the t^2 portion of the
   received phase, the script inherently captures the Range-Doppler
   coupling effect we discussed.

 * Precision Handling: We model the entire complex exponent
   np.exp(1j * ...) directly.  Because Python uses 64-bit floats
   by default, it retains enough precision to handle numbers as
   large as 77 GHz multiplied by microseconds without devastating
   truncation errors in the phase.

 * Phase Noise Emulation: I generated 1/f (pink) noise.  This is
   much more realistic for oscillators than white noise.  We then
   use scipy.interpolate.interp1d to figure out exactly what the
   delayed phase noise phi_pn(t - tau(t)) looks like, managing the
   boundary conditions where t < tau.

 * Verification: The code prints the theoretical range and Doppler
   beat frequencies so you can visually verify that the FFT peak
   lands exactly where the continuous-time math says it should.
"""
