To accurately simulate the return signal of an FMCW (Frequency-Modulated Continuous Wave) radar while accounting for both local oscillator (LO) phase noise and target velocity (the Doppler effect), we must build the mathematical model from the ground up.

This requires carefully modeling the time-delayed return signal, recognizing that the delay itself is a function of time due to the target's motion, and tracking the phase noise through the transmission, delay, and mixing processes.

Here is the deep mathematical analysis and modeling strategy for your simulation.

### 1. The Transmit Signal Model

An FMCW radar transmits a "chirp" signal whose frequency increases (or decreases) linearly over time. Let's define the fundamental parameters:

* $f_c$: Carrier (start) frequency
* $B$: Chirp bandwidth
* $T_c$: Chirp duration
* $K$: Chirp slope, defined as $K = B / T_c$

The ideal instantaneous frequency of the transmit signal is $f_{tx}(t) = f_c + K t$. Integrating this gives the ideal phase. However, real oscillators suffer from phase fluctuations, denoted as $\phi_{pn}(t)$.

The full mathematical expression for the transmitted signal $s_{tx}(t)$ is:


$$s_{tx}(t) = A_{tx} \exp\left(j \left( 2\pi f_c t + \pi K t^2 + \phi_{pn}(t) \right) \right)$$

*(Note: We use the analytic complex exponential form here as it is standard in baseband DSP modeling).*

### 2. Target Kinematics and Time-Varying Delay

A moving target has a range $R(t)$ that changes continuously. Assuming a constant radial velocity $v$ (where $v > 0$ means the target is moving away), the range equation is:


$$R(t) = R_0 + v t$$

The round-trip time delay $\tau(t)$ of the signal reflecting off this target is also a function of time:


$$\tau(t) = \frac{2 R(t)}{c} = \frac{2 R_0}{c} + \frac{2 v}{c} t = \tau_0 + \tau_v t$$


Where $\tau_0$ is the initial delay and $\tau_v$ is the rate of change of the delay.

### 3. The Receive Signal Model

The received signal is an attenuated, time-delayed version of the transmit signal. Because the local oscillator operates continuously, the phase noise $\phi_{pn}$ at the exact moment of reflection is preserved in the return signal.

Substituting $t \rightarrow t - \tau(t)$ into the transmit equation yields the received signal $s_{rx}(t)$:


$$s_{rx}(t) = A_{rx} \exp\left(j \left( 2\pi f_c (t - \tau(t)) + \pi K (t - \tau(t))^2 + \phi_{pn}(t - \tau(t)) \right) \right)$$

### 4. The Mixer and the Beat Signal

In the receiver, the incoming signal $s_{rx}(t)$ is mixed (multiplied) with the current LO signal $s_{tx}(t)$ to "de-chirp" it. In the complex domain, this is equivalent to multiplying $s_{tx}(t)$ by the complex conjugate of $s_{rx}(t)$, followed by a low-pass filter.

The resulting baseband beat signal is:


$$s_{beat}(t) = s_{tx}(t) \cdot s_{rx}^*(t) = A_{beat} \exp\left(j \Phi_{beat}(t)\right)$$

The phase of the beat signal, $\Phi_{beat}(t)$, is the difference between the transmit and receive phases:


$$\Phi_{beat}(t) = 2\pi f_c \tau(t) + 2\pi K t \tau(t) - \pi K \tau^2(t) + \Delta\phi_{pn}(t)$$

Let's expand this by substituting $\tau(t) = \frac{2R_0}{c} + \frac{2v}{c}t$ and analyze the resulting terms:

1. **Doppler Phase:** $2\pi f_c \left( \frac{2R_0}{c} + \frac{2v}{c}t \right) = \frac{4\pi R_0}{\lambda} + 2\pi \left(\frac{2v}{\lambda}\right)t$
* This generates the Doppler frequency shift $f_d = 2v/\lambda$.


2. **Range Beat Phase:** $2\pi K t \left( \frac{2R_0}{c} + \frac{2v}{c}t \right) = 2\pi \left( \frac{2 K R_0}{c} \right) t + 2\pi \left( \frac{2 K v}{c} \right) t^2$
* The first part dictates the standard beat frequency $f_r = 2KR_0/c$.
* The second part is the *Range-Doppler coupling* term (a small chirp rate induced by velocity). For very fast targets or very long chirps, this causes frequency smearing.


3. **Residual Video Phase (RVP):** $-\pi K \tau^2(t)$
* This is usually a negligible constant phase shift, but keeping it in the simulation ensures mathematical perfection.


4. **Phase Noise Term:** $\Delta\phi_{pn}(t) = \phi_{pn}(t) - \phi_{pn}(t - \tau(t))$
* This is the critical "Range Correlation Effect."



### 5. Analyzing the Phase Noise (Range Correlation Effect)

The term $\Delta\phi_{pn}(t) = \phi_{pn}(t) - \phi_{pn}(t - \tau(t))$ dictates how LO phase noise affects the final IF signal.

* If the target is very close ($\tau(t) \approx 0$), then $\phi_{pn}(t) \approx \phi_{pn}(t - \tau(t))$, and the phase noise cancels out almost entirely.
* If the target is far away, the phase noise from the current LO and the delayed LO become uncorrelated, injecting significant noise into the beat signal and raising the noise floor, which masks smaller targets.

### 6. Simulation Strategy

To simulate this accurately in code, you should follow this sequence:

**Step 1: Generate the LO Phase Noise Vector**
You cannot simply add random numbers at the end of the simulation. You must generate a time-domain vector for $\phi_{pn}(t)$ that matches the Power Spectral Density (PSD) of your specific oscillator (e.g., combining $1/f^3$, $1/f^2$, and $1/f$ noise profiles). This is typically done by generating white Gaussian noise in the frequency domain, shaping it with the desired PSD filter, and taking the Inverse Fast Fourier Transform (IFFT) to get the time-domain phase noise vector.

**Step 2: Define Time and Kinematics**
Create a high-resolution fast-time vector $t$ for a single chirp (or multiple chirps for a 2D Range-Doppler simulation). Calculate the dynamic delay vector $\tau(t) = \frac{2(R_0 + v t)}{c}$.

**Step 3: Construct the Signals Directly**
Do not try to mathematically shortcut the beat signal equation if you want a robust simulation. Instead, explicitly create the two complex arrays:

* Array 1: $s_{tx}(t)$ using the fast-time vector $t$ and your generated $\phi_{pn}(t)$.
* Array 2: Interpolate $\phi_{pn}(t)$ to find the values at $t - \tau(t)$. Then, construct $s_{rx}(t)$ using $t - \tau(t)$ everywhere.

**Step 4: Numerically Mix and Analyze**
Multiply $s_{tx}$ by the conjugate of $s_{rx}$. Apply a digital low-pass filter to remove any high-frequency mixing artifacts, and then take the FFT to observe the resulting beat frequency, Doppler shift, and the phase noise skirt around your target peak.
