"""
CP-PLL Lock Simulation — same ODEs as cp_pll_ltspice.cir
Solves the phase-domain nonlinear ODE system with scipy.
Produces lock waveform plots equivalent to LTspice output.
"""

import os
os.environ["MPLBACKEND"] = "Agg"

import numpy as np
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ─── Design parameters (must match LTspice file) ────────
F_REF  = 100e6       # Hz   reference
F0     = 1e9         # Hz   VCO nominal
KVCO   = 400e6       # Hz/V VCO gain
V0     = 0.9         # V    nominal Vctrl
ICP    = 200e-6      # A    charge pump current
N_DIV  = 10          # div  ratio
R1     = 3927.0      # Ω
C1     = 30e-12      # F
C2     = 2.2e-12     # F

# ─── ODE system ─────────────────────────────────────────
# State vector: y = [phi_err (rad), V_N1 (V), V_CTRL (V)]
#
# dy0/dt = 2π (f_ref − f_vco/N)         phase error accumulation
# dy1/dt = (V_CTRL − V_N1) / (R1·C1)   voltage at C1 node
# dy2/dt = (I_cp − I_R1) / C2           VCO control voltage
#
# I_cp   = ICP · clip(φ_err / 2π, −1, +1)
# I_R1   = (V_CTRL − V_N1) / R1

def pll_odes(t, y):
    phi_err, V_N1, V_CTRL = y

    # VCO frequency (clamped to tuning range)
    f_vco = np.clip(F0 + KVCO * (V_CTRL - V0), 200e6, 1.8e9)

    # Phase error rate  (rad/s)
    dphi_dt = 2 * np.pi * (F_REF - f_vco / N_DIV)

    # Charge pump current — hard clip at ±ICP
    I_cp = ICP * np.clip(phi_err / (2 * np.pi), -1.0, 1.0)

    # Current through R1 (from CTRL to N1)
    I_R1 = (V_CTRL - V_N1) / R1

    # Loop filter node voltages
    dV_N1_dt   = I_R1 / C1
    dV_CTRL_dt = (I_cp - I_R1) / C2

    return [dphi_dt, dV_N1_dt, dV_CTRL_dt]

# ─── Initial conditions ──────────────────────────────────
# V_CTRL = 0.5 V  →  f_vco = 840 MHz  (−160 MHz from target)
y0 = [0.0, 0.5, 0.5]

# ─── Solve ───────────────────────────────────────────────
T_END  = 3e-6         # 3 µs
t_eval = np.linspace(0, T_END, 30_000)

sol = solve_ivp(
    pll_odes, (0, T_END), y0,
    t_eval=t_eval,
    method="RK45",
    rtol=1e-9, atol=1e-12,
    max_step=2e-9,
)

t        = sol.t
phi_err  = sol.y[0]
V_N1     = sol.y[1]
V_CTRL   = sol.y[2]
f_vco    = np.clip(F0 + KVCO * (V_CTRL - V0), 200e6, 1.8e9)
I_cp     = ICP * np.clip(phi_err / (2 * np.pi), -1.0, 1.0)

# ─── Lock-time measurement ──────────────────────────────
TARGET_F  = F0                        # 1 GHz
LOCK_THRS = 0.001 * TARGET_F          # ±0.1 % = ±1 MHz band

# "Lock" = frequency stays within ±0.1% for the last 500 ns
t_lock = None
for i in range(len(t) - 1, 0, -1):
    if abs(f_vco[i] - TARGET_F) > LOCK_THRS:
        t_lock = t[i]
        break
if t_lock is None:
    t_lock = t[0]
t_lock_us = t_lock * 1e6

V_ctrl_ss   = float(np.mean(V_CTRL[t > 2.5e-6]))
f_vco_ss_GHz = float(np.mean(f_vco[t > 2.5e-6])) / 1e9
freq_err_ppm = (f_vco_ss_GHz * 1e9 - F0) / F0 * 1e6

print("=" * 50)
print("  CP-PLL LOCK SIMULATION RESULTS")
print("=" * 50)
print(f"  Initial V(CTRL)  = 0.500 V  → f_vco = 840 MHz")
print(f"  Target  V(CTRL)  = {V0} V  → f_vco = 1.000 GHz")
print(f"  Lock time        ≈ {t_lock_us:.3f} µs  (±0.1% band)")
print(f"  SS V(CTRL)       = {V_ctrl_ss:.4f} V")
print(f"  SS f_vco         = {f_vco_ss_GHz:.6f} GHz")
print(f"  SS freq error    = {freq_err_ppm:.3f} ppm")
print("=" * 50)

# ─── Plot ────────────────────────────────────────────────
fig = plt.figure(figsize=(12, 10))
fig.suptitle(
    "CP-PLL Lock Simulation  (Phase-Domain ODE = LTspice cp_pll_ltspice.cir)\n"
    f"f_ref=100 MHz → f_out=1 GHz,  N=10,  Icp=200 µA,  R1=3.9 kΩ,  C1=30 pF,  C2=2.2 pF",
    fontsize=12,
)
gs = gridspec.GridSpec(4, 1, hspace=0.45)

# ── Plot 1: VCO control voltage ───
ax1 = fig.add_subplot(gs[0])
ax1.plot(t * 1e6, V_CTRL, "steelblue", lw=1.5, label="V(CTRL)")
ax1.plot(t * 1e6, V_N1,   "cornflowerblue", lw=1.0, ls="--", label="V(N1) — C1 node")
ax1.axhline(V0, color="k",  ls="--", lw=0.8, label=f"Lock point {V0} V")
ax1.axvline(t_lock_us, color="red", ls=":", lw=1.2, label=f"t_lock ≈ {t_lock_us:.2f} µs")
ax1.set_ylabel("Voltage (V)")
ax1.set_title("VCO Control Voltage")
ax1.set_ylim(0.3, 1.6)
ax1.legend(fontsize=8, loc="upper right")
ax1.grid(True, alpha=0.3)

# ── Plot 2: VCO output frequency ───
ax2 = fig.add_subplot(gs[1])
ax2.plot(t * 1e6, f_vco / 1e6, "darkorange", lw=1.5)
ax2.axhline(1000, color="k", ls="--", lw=0.8, label="Target 1000 MHz")
ax2.axhline(1000 * (1 + 0.001), color="g", ls=":", lw=0.8, label="±0.1% band")
ax2.axhline(1000 * (1 - 0.001), color="g", ls=":", lw=0.8)
ax2.axvline(t_lock_us, color="red", ls=":", lw=1.2, label=f"t_lock ≈ {t_lock_us:.2f} µs")
ax2.set_ylabel("Frequency (MHz)")
ax2.set_title("VCO Output Frequency")
ax2.set_ylim(750, 1150)
ax2.legend(fontsize=8, loc="upper right")
ax2.grid(True, alpha=0.3)

# ── Plot 3: Phase error ───
ax3 = fig.add_subplot(gs[2])
ax3.plot(t * 1e6, phi_err / (2 * np.pi), "mediumpurple", lw=1.5)
ax3.axhline(0, color="k", ls="--", lw=0.8)
ax3.axvline(t_lock_us, color="red", ls=":", lw=1.2)
ax3.set_ylabel("Phase Error (cycles)")
ax3.set_title("Accumulated Phase Error  (1 cycle = 2π rad)")
ax3.grid(True, alpha=0.3)
# zoom y-axis to show lock detail
max_err = np.max(np.abs(phi_err[t > t_lock])) / (2 * np.pi) * 20
ax3.set_ylim(-max_err, max(phi_err / (2 * np.pi)) * 1.1)

# ── Plot 4: Charge pump current ───
ax4 = fig.add_subplot(gs[3])
ax4.plot(t * 1e6, I_cp * 1e6, "tomato", lw=1.5)
ax4.axhline(0,   color="k",  ls="--", lw=0.8)
ax4.axhline( ICP * 1e6, color="gray", ls=":", lw=0.8, label=f"+Icp = {ICP*1e6:.0f} µA")
ax4.axhline(-ICP * 1e6, color="gray", ls=":", lw=0.8, label=f"−Icp = −{ICP*1e6:.0f} µA")
ax4.axvline(t_lock_us, color="red", ls=":", lw=1.2, label=f"t_lock ≈ {t_lock_us:.2f} µs")
ax4.set_ylabel("Current (µA)")
ax4.set_xlabel("Time (µs)")
ax4.set_title("Charge Pump Output Current  (saturated during acquisition)")
ax4.legend(fontsize=8)
ax4.grid(True, alpha=0.3)

for ax in [ax1, ax2, ax3, ax4]:
    ax.set_xlim(0, T_END * 1e6)

plt.savefig("../pll_lock_waveforms.png", dpi=150, bbox_inches="tight")
print("\n  Waveform plot → pll_lock_waveforms.png")

# ─── Zoom plot: settling detail (0.5–2 µs) ──────────────
fig2, (axz1, axz2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
fig2.suptitle("CP-PLL Lock Settling Detail  (0.5–2.5 µs window)", fontsize=12)

mask = (t >= 0.5e-6) & (t <= 2.5e-6)
axz1.plot(t[mask] * 1e6, V_CTRL[mask],   "steelblue",  lw=1.5, label="V(CTRL)")
axz1.axhline(V0, color="k", ls="--", lw=0.8, label=f"Lock point {V0} V")
axz1.axvline(t_lock_us, color="red", ls=":", lw=1.2, label=f"t_lock ≈ {t_lock_us:.2f} µs")
axz1.set_ylabel("V(CTRL) (V)")
axz1.legend(fontsize=9)
axz1.grid(True, alpha=0.3)
axz1.set_ylim(0.6, 1.3)

axz2.plot(t[mask] * 1e6, f_vco[mask] / 1e6, "darkorange", lw=1.5)
axz2.axhline(1000, color="k", ls="--", lw=0.8)
axz2.axhline(1000 * 1.001, color="g", ls=":", lw=0.8, label="±1 MHz band")
axz2.axhline(1000 * 0.999, color="g", ls=":", lw=0.8)
axz2.axvline(t_lock_us, color="red", ls=":", lw=1.2)
axz2.set_ylabel("f_vco (MHz)")
axz2.set_xlabel("Time (µs)")
axz2.legend(fontsize=9)
axz2.grid(True, alpha=0.3)
axz2.set_ylim(900, 1050)

plt.tight_layout()
plt.savefig("../pll_lock_zoom.png", dpi=150, bbox_inches="tight")
print("  Zoom plot      → pll_lock_zoom.png")
