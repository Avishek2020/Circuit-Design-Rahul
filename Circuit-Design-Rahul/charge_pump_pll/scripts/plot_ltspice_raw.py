"""
Parse LTspice .raw output and generate lock waveform plots.
Uses spicelib (pip install spicelib).
"""
import os
os.environ["MPLBACKEND"] = "Agg"

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from spicelib.raw.raw_read import RawRead

RAW = "D:/2026-LEARN/Circuit-Design-Rahul/charge_pump_pll/spice/cp_pll_ltspice.raw"
LOG = "D:/2026-LEARN/Circuit-Design-Rahul/charge_pump_pll/spice/cp_pll_ltspice.log"

# ── Read log measurements ──────────────────────────────
def parse_log(path):
    meas = {}
    with open(path) as f:
        for line in f:
            for key in ("t_lock", "vctrl_ss", "fvco_ss"):
                if line.lower().startswith(key):
                    # e.g. "t_lock=5.699e-08 FROM ... TO ..."
                    val = float(line.split("=")[1].split()[0])
                    meas[key] = val
    return meas

meas = parse_log(LOG)
t_lock_ns  = meas.get("t_lock", 0) * 1e9
vctrl_ss   = meas.get("vctrl_ss", 0.9)
fvco_ss    = meas.get("fvco_ss", 1.0)

print("=" * 55)
print("  LTSPICE SIMULATION — MEASURED RESULTS")
print("=" * 55)
print(f"  t_lock (first ×0.999 GHz)  = {t_lock_ns:.1f} ns")
print(f"  SS V(CTRL) avg (2.5–3 µs)  = {vctrl_ss:.6f} V")
print(f"  SS f_vco   avg (2.5–3 µs)  = {fvco_ss:.6f} GHz")
print(f"  SS freq error               = {(fvco_ss-1)*1e6:.3f} ppm")

# ── Parse .raw ─────────────────────────────────────────
print("\n  Reading LTspice .raw file …")
raw = RawRead(RAW)

print(f"  Variables found: {raw.get_trace_names()}")

time    = np.array(raw.get_trace("time").get_wave(0))
v_ctrl  = np.array(raw.get_trace("V(ctrl)").get_wave(0))
v_phe   = np.array(raw.get_trace("V(phe)").get_wave(0))
v_vco_f = np.array(raw.get_trace("V(vco_f)").get_wave(0))
I_cp_raw = np.array(raw.get_trace("I(Bcp)").get_wave(0))   # actual LTspice current
# LTspice sign: I(Bx) positive = current flowing from N+ to N- through device
# Bcp is "0 CTRL", so positive I(Bcp) = current flowing from 0→CTRL = sourcing
I_cp = -I_cp_raw   # flip: positive means CP sourcing into CTRL

t_us    = time * 1e6
f_GHz   = v_vco_f               # already in GHz units from B-source
phi_cyc = v_phe / (2 * np.pi)   # cycles

# Find settle time: last index where freq is outside ±0.1%
BAND = 0.001
outside = np.where(np.abs(f_GHz - 1.0) > BAND)[0]
t_settle_us = t_us[outside[-1]] if len(outside) > 0 else 0.0

print(f"\n  Settle time (±0.1% = ±1 MHz): {t_settle_us:.3f} µs")

# ── 4-panel waveform plot ──────────────────────────────
fig = plt.figure(figsize=(12, 10))
fig.suptitle(
    "CP-PLL Lock Simulation — LTspice 26 Output\n"
    "f_ref=100 MHz → f_out=1 GHz  |  N=10  |  Icp=200 µA  |  "
    "R1=3.9 kΩ, C1=30 pF, C2=2.2 pF  |  TSMC 180nm CMOS",
    fontsize=11,
)
gs = gridspec.GridSpec(4, 1, hspace=0.5)

# 1. VCO control voltage
ax1 = fig.add_subplot(gs[0])
ax1.plot(t_us, v_ctrl, "steelblue", lw=1.5, label="V(CTRL)")
ax1.axhline(0.9, color="k", ls="--", lw=0.9, label="Lock point 0.9 V")
ax1.axvline(t_lock_ns * 1e-3, color="tomato",   ls=":", lw=1.2,
            label=f"First cross {t_lock_ns:.1f} ns")
ax1.axvline(t_settle_us, color="darkgreen", ls=":", lw=1.2,
            label=f"Settled {t_settle_us:.3f} µs")
ax1.set_ylabel("V(CTRL)  [V]")
ax1.set_ylim(0.3, 1.6)
ax1.legend(fontsize=8, loc="upper right")
ax1.grid(True, alpha=0.3)
ax1.set_title("VCO Control Voltage")

# 2. VCO output frequency
ax2 = fig.add_subplot(gs[1])
ax2.plot(t_us, f_GHz * 1000, "darkorange", lw=1.5, label="f_VCO")
ax2.axhline(1000,       color="k",  ls="--", lw=0.9, label="1000 MHz target")
ax2.axhline(1000*1.001, color="g",  ls=":",  lw=0.8, label="±1 MHz (0.1%) band")
ax2.axhline(1000*0.999, color="g",  ls=":",  lw=0.8)
ax2.axvline(t_lock_ns * 1e-3, color="tomato",   ls=":", lw=1.2)
ax2.axvline(t_settle_us, color="darkgreen", ls=":", lw=1.2)
ax2.set_ylabel("f_VCO  [MHz]")
ax2.set_ylim(750, 1150)
ax2.legend(fontsize=8, loc="upper right")
ax2.grid(True, alpha=0.3)
ax2.set_title("VCO Output Frequency")

# 3. Phase error
ax3 = fig.add_subplot(gs[2])
ax3.plot(t_us, phi_cyc, "mediumpurple", lw=1.5)
ax3.axhline(0, color="k", ls="--", lw=0.9)
ax3.axvline(t_lock_ns * 1e-3, color="tomato",   ls=":", lw=1.2)
ax3.axvline(t_settle_us, color="darkgreen", ls=":", lw=1.2)
ax3.set_ylabel("Phase Error  [cycles]")
ax3.set_title("Accumulated Phase Error")
ax3.grid(True, alpha=0.3)

# 4. Charge pump current
ax4 = fig.add_subplot(gs[3])
ax4.plot(t_us, I_cp * 1e6, "tomato", lw=1.5)
ax4.axhline(0,    color="k",    ls="--", lw=0.9)
ax4.axhline( 200, color="gray", ls=":",  lw=0.8, label="+200 µA (sat)")
ax4.axhline(-200, color="gray", ls=":",  lw=0.8, label="−200 µA (sat)")
ax4.axvline(t_lock_ns * 1e-3, color="tomato",   ls=":", lw=1.2,
            label=f"First cross {t_lock_ns:.1f} ns")
ax4.axvline(t_settle_us, color="darkgreen", ls=":", lw=1.2,
            label=f"Settled {t_settle_us:.3f} µs")
ax4.set_ylabel("I_CP  [µA]")
ax4.set_xlabel("Time  [µs]")
ax4.set_title("Charge Pump Current")
ax4.legend(fontsize=8, loc="upper right")
ax4.grid(True, alpha=0.3)

for ax in [ax1, ax2, ax3, ax4]:
    ax.set_xlim(0, 3.0)

plt.savefig(
    "D:/2026-LEARN/Circuit-Design-Rahul/charge_pump_pll/pll_ltspice_waveforms.png",
    dpi=150, bbox_inches="tight",
)
print("\n  → pll_ltspice_waveforms.png  saved")

# ── Zoom: 0–300 ns  (acquisition) ────────────────────
fig2, (az1, az2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
fig2.suptitle(
    "CP-PLL Acquisition  (0–300 ns zoom)  |  LTspice 26",
    fontsize=12,
)

mask = t_us <= 0.3
az1.plot(t_us[mask] * 1e3, v_ctrl[mask], "steelblue", lw=1.5)
az1.axhline(0.9, color="k", ls="--", lw=0.9, label="0.9 V lock point")
az1.axvline(t_lock_ns, color="tomato", ls=":", lw=1.2, label=f"First cross {t_lock_ns:.1f} ns")
az1.set_ylabel("V(CTRL)  [V]")
az1.legend(fontsize=9)
az1.grid(True, alpha=0.3)
az1.set_title("VCO Control Voltage")

az2.plot(t_us[mask] * 1e3, f_GHz[mask] * 1000, "darkorange", lw=1.5)
az2.axhline(1000, color="k", ls="--", lw=0.9, label="1000 MHz")
az2.axhline(999,  color="g", ls=":",  lw=0.8, label="999 MHz (−0.1%)")
az2.axvline(t_lock_ns, color="tomato", ls=":", lw=1.2)
az2.set_ylabel("f_VCO  [MHz]")
az2.set_xlabel("Time  [ns]")
az2.legend(fontsize=9)
az2.grid(True, alpha=0.3)
az2.set_title("VCO Output Frequency")

plt.tight_layout()
plt.savefig(
    "D:/2026-LEARN/Circuit-Design-Rahul/charge_pump_pll/pll_ltspice_zoom_ns.png",
    dpi=150, bbox_inches="tight",
)
print("  → pll_ltspice_zoom_ns.png  saved")
