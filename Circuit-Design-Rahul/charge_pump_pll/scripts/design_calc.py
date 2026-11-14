"""
Charge Pump PLL Design Calculator
Target: f_ref = 100 MHz, f_out = 1 GHz, P < 100 mW
Technology: TSMC 180nm CMOS, VDD = 1.8V
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ─────────────────────────────────────────────
# 1.  TOP-LEVEL SPECIFICATIONS
# ─────────────────────────────────────────────
F_REF   = 100e6          # Hz  reference frequency
F_OUT   = 1e9            # Hz  output (VCO) frequency
N_DIV   = int(F_OUT / F_REF)  # 10  division ratio
VDD     = 1.8            # V
PM_TGT  = 60             # deg  target phase margin
FC_TGT  = 5e6            # Hz  target loop BW (< f_ref/10)

print("=" * 55)
print("  CHARGE PUMP PLL — DESIGN PARAMETER SUMMARY")
print("=" * 55)
print(f"  f_ref  = {F_REF/1e6:.0f} MHz")
print(f"  f_out  = {F_OUT/1e9:.0f} GHz")
print(f"  N      = {N_DIV}")
print(f"  VDD    = {VDD} V")
print(f"  PM tgt = {PM_TGT}°")
print(f"  f_c    = {FC_TGT/1e6:.0f} MHz")

# ─────────────────────────────────────────────
# 2.  VCO — NMOS CROSS-COUPLED LC OSCILLATOR
# ─────────────────────────────────────────────
print("\n--- 2. VCO (LC Oscillator) ---")

L_tank  = 2e-9           # H   on-chip spiral (Q≈7 at 1GHz)
# Resonance: f = 1/(2π√LC)  →  C = 1/(4π²f²L)
C_tank  = 1 / (4 * np.pi**2 * F_OUT**2 * L_tank)
Kvco    = 400e6          # Hz/V   VCO sensitivity
I_tail  = 5e-3           # A   tail current for sufficient swing
V_swing = I_tail * L_tank * 2 * np.pi * F_OUT  # rough estimate (Itail*wL)
P_vco   = VDD * I_tail

print(f"  L       = {L_tank*1e9:.1f} nH")
print(f"  C_tank  = {C_tank*1e12:.1f} pF  (varactor tuning ±20%)")
print(f"  Kvco    = {Kvco/1e6:.0f} MHz/V")
print(f"  I_tail  = {I_tail*1e3:.0f} mA")
print(f"  P_vco   = {P_vco*1e3:.0f} mW")

# ─────────────────────────────────────────────
# 3.  CHARGE PUMP
# ─────────────────────────────────────────────
print("\n--- 3. Charge Pump ---")

Icp      = 200e-6        # A   nominal charge pump current
# Cascode current source for high Zout
# P-type mirror for UP, N-type mirror for DN
# Matching: use unit-cell layout, common-centroid
P_cp     = VDD * Icp * 0.1   # CP active only during phase error; ≈10% duty

print(f"  Icp     = {Icp*1e6:.0f} µA")
print(f"  P_cp    ≈ {P_cp*1e6:.0f} µW  (10% duty avg)")

# ─────────────────────────────────────────────
# 4.  LOOP FILTER  (passive, 3rd-order)
# ─────────────────────────────────────────────
# Topology: R1 in series with C1, then C2 shunt to ground
#   Z(s) = (1 + s·R1·C1) / (s·(C1+C2)·(1 + s·R1·C1·C2/(C1+C2)))
# Approximation (C1 >> C2):
#   zero  : ωz  = 1/(R1·C1)
#   pole  : ωp2 = 1/(R1·C2)
#   ωc = √(ωz · ωp2)  →  maximum phase boost at crossover
print("\n--- 4. Loop Filter ---")

wc  = 2 * np.pi * FC_TGT
wz  = wc / np.tan(np.radians(90 - (90 - PM_TGT) / 2 + PM_TGT / 2))

# Using optimal placement for 60° PM:
# φm = arctan(wc/wz) - arctan(wc/wp2)
# Maximise: wc = √(wz·wp2)  →  wp2 = wc²/wz
# φm = 2·arctan(√(wp2/wz)) - 90°   ...re-derive numerically:
# For PM = 60°: arctan(r) - arctan(1/r) = 60°  where r = wc/wz = √(wp2/wz)
# → 2·arctan(r) = 60° + 90° = 150°  → arctan(r) = 75°  → r = tan(75°) ≈ 3.732
r   = np.tan(np.radians(75))        # ≈ 3.732
wz  = wc / r
wp2 = wc * r

# Open loop gain unity at wc:
# |G(jwc)| = Icp·Kvco_rad / (2π·N) × |Z(jwc)| / wc = 1
# |Z(jwc)| ≈ R1 (at wc, R1 dominates for C1>>C2)
Kvco_rad = 2 * np.pi * Kvco
R1 = (2 * np.pi * N_DIV * wc) / (Icp * Kvco_rad)

C1 = 1 / (wz * R1)
C2 = 1 / (wp2 * R1)

# Verify C1/C2 ratio
ratio = C1 / C2

# Actual zero / pole frequencies
fz  = wz  / (2 * np.pi)
fp2 = wp2 / (2 * np.pi)

print(f"  R1      = {R1:.0f} Ω  ({R1/1e3:.2f} kΩ)")
print(f"  C1      = {C1*1e12:.1f} pF")
print(f"  C2      = {C2*1e12:.2f} pF")
print(f"  C1/C2   = {ratio:.1f}  (need >> 1 for approximation ✓)")
print(f"  fz      = {fz/1e6:.2f} MHz")
print(f"  fp2     = {fp2/1e6:.2f} MHz")

# ─────────────────────────────────────────────
# 5.  OPEN-LOOP BODE PLOT & PHASE MARGIN VERIFY
# ─────────────────────────────────────────────
freqs = np.logspace(4, 9, 5000)
w     = 2 * np.pi * freqs

# Z(jw) exact
def Z_lf(w, R1, C1, C2):
    num = 1 + 1j * w * R1 * C1
    den = 1j * w * (C1 + C2) * (1 + 1j * w * R1 * C1 * C2 / (C1 + C2))
    return num / den

Z   = Z_lf(w, R1, C1, C2)
G   = (Icp * Kvco_rad) / (2 * np.pi * N_DIV) * Z / (1j * w)
G_dB    = 20 * np.log10(np.abs(G))
G_phase = np.angle(G, deg=True)

# Find actual crossover
idx_xo  = np.argmin(np.abs(np.abs(G) - 1))
fc_act  = freqs[idx_xo]
pm_act  = 180 + G_phase[idx_xo]

print(f"\n  --- Bode Verification ---")
print(f"  Actual f_c   = {fc_act/1e6:.2f} MHz  (target {FC_TGT/1e6} MHz)")
print(f"  Actual PM    = {pm_act:.1f}°        (target {PM_TGT}°)")

# ─────────────────────────────────────────────
# 6.  FREQUENCY DIVIDER (÷10)
# ─────────────────────────────────────────────
# Stage 1: CML ÷2  (1 GHz → 500 MHz)   higher power, runs fast
# Stage 2: TSPC ÷5 (500 MHz → 100 MHz)
print("\n--- 6. Frequency Divider (N=10 = ÷2 × ÷5) ---")

P_div1 = 3e-3    # W  CML ÷2 at 1 GHz
P_div2 = 1.5e-3  # W  TSPC ÷5 at 500 MHz
P_div  = P_div1 + P_div2

print(f"  Stage1: CML ÷2  @ 1 GHz  → P ≈ {P_div1*1e3:.1f} mW")
print(f"  Stage2: TSPC ÷5 @ 500MHz → P ≈ {P_div2*1e3:.1f} mW")
print(f"  P_div   = {P_div*1e3:.1f} mW")

# ─────────────────────────────────────────────
# 7.  PFD (D flip-flop tri-state detector)
# ─────────────────────────────────────────────
print("\n--- 7. PFD ---")
P_pfd = 0.8e-3   # W  two DFFs + NAND at 100 MHz
print(f"  P_pfd   = {P_pfd*1e3:.1f} mW")

# ─────────────────────────────────────────────
# 8.  OUTPUT BUFFER
# ─────────────────────────────────────────────
print("\n--- 8. Output Buffer ---")
P_buf = 4e-3     # W  differential to single-ended, 50Ω drive
print(f"  P_buf   = {P_buf*1e3:.1f} mW")

# ─────────────────────────────────────────────
# 9.  BIAS CIRCUITS
# ─────────────────────────────────────────────
P_bias = 1.5e-3  # W  bandgap ref + current mirrors

# ─────────────────────────────────────────────
# 10.  TOTAL POWER BUDGET
# ─────────────────────────────────────────────
print("\n--- Power Budget ---")
budget = {
    "VCO (LC osc)"    : P_vco,
    "Charge Pump"     : P_cp,
    "Loop Filter"     : 0.0,
    "Divider (÷10)"   : P_div,
    "PFD"             : P_pfd,
    "Output Buffer"   : P_buf,
    "Bias/References" : P_bias,
}
P_total = sum(budget.values())

for block, p in budget.items():
    bar = "█" * int(p / P_total * 30)
    print(f"  {block:<20} {p*1e3:5.1f} mW  {bar}")
print(f"  {'─'*42}")
print(f"  {'TOTAL':<20} {P_total*1e3:5.1f} mW  {'< 100 mW ✓' if P_total < 0.1 else '✗ EXCEEDS BUDGET'}")

# ─────────────────────────────────────────────
# 11.  NOISE ANALYSIS
# ─────────────────────────────────────────────
print("\n--- 11. Phase Noise Budget (at 1 MHz offset) ---")
# Reference oscillator (crystal TCXO at 100MHz):  -150 dBc/Hz at 1MHz offset
# In-band PLL contribution: ref noise × 20log(N) = -150 + 20log(10) = -130 dBc/Hz
# VCO free-running (Leeson): L(fm) ≈ 10log[(f0/2Q·fm)² × FkT/Ps × (1+(fc/fm))]
# Typical LC VCO at 1GHz: -120 dBc/Hz at 1MHz (free-running)
# PLL suppresses inside BW; outside BW = VCO free-running

fm        = 1e6     # Hz offset
Q_L       = 7       # on-chip inductor Q
F_noise   = 3       # dB noise figure
kT        = 4e-21   # J at 300K (kT at room temp)
P_signal  = 0.001   # W  signal power in tank ~1mW

# Leeson equation
S_vco_dbc = 10 * np.log10(
    (F_OUT / (2 * Q_L * fm))**2 * F_noise * kT / P_signal
)

print(f"  VCO L(1MHz) ≈ {S_vco_dbc:.0f} dBc/Hz  (Leeson model)")
print(f"  Ref contribution: -130 dBc/Hz (in-band, N=10)")
print(f"  At 1MHz offset VCO dominates (outside BW)")

# ─────────────────────────────────────────────
# 12.  BODE PLOT
# ─────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
fig.suptitle("Charge Pump PLL — Open Loop Bode Plot\n"
             f"f_ref={F_REF/1e6:.0f}MHz, f_out={F_OUT/1e9:.0f}GHz, N={N_DIV}",
             fontsize=13)

ax1.semilogx(freqs, G_dB, 'b', linewidth=2)
ax1.axhline(0,  color='k', linestyle='--', linewidth=0.8, label='0 dB')
ax1.axvline(fc_act, color='r', linestyle=':', linewidth=1.2,
            label=f'f_c = {fc_act/1e6:.2f} MHz')
ax1.axvline(fz,  color='g', linestyle=':', linewidth=1.0,
            label=f'f_z = {fz/1e6:.2f} MHz')
ax1.axvline(fp2, color='orange', linestyle=':', linewidth=1.0,
            label=f'f_p2 = {fp2/1e6:.2f} MHz')
ax1.set_ylabel("Magnitude (dB)")
ax1.set_ylim(-60, 80)
ax1.grid(True, which='both', alpha=0.3)
ax1.legend(fontsize=9)

ax2.semilogx(freqs, G_phase, 'darkorange', linewidth=2)
ax2.axhline(-180, color='k', linestyle='--', linewidth=0.8)
ax2.axhline(-180 + pm_act, color='r', linestyle=':', linewidth=1.2,
            label=f'PM = {pm_act:.1f}°')
ax2.axvline(fc_act, color='r', linestyle=':', linewidth=1.2)
ax2.set_ylabel("Phase (°)")
ax2.set_xlabel("Frequency (Hz)")
ax2.set_ylim(-270, -60)
ax2.grid(True, which='both', alpha=0.3)
ax2.legend(fontsize=9)

plt.tight_layout()
plt.savefig("../pll_bode.png", dpi=150, bbox_inches='tight')
print("\n  Bode plot saved → pll_bode.png")

# ─────────────────────────────────────────────
# 13.  CLOSED-LOOP STEP RESPONSE
# ─────────────────────────────────────────────
# Simplified 2nd-order step response for locking estimation
wn   = np.sqrt(Icp * Kvco_rad * wz / (2 * np.pi * N_DIV))
zeta = wn / (2 * wz) + wz / (2 * wn)   # rough estimate

t    = np.linspace(0, 2e-6, 10000)
# Under-damped step: phase steps from 0 to target
if zeta < 1:
    wd   = wn * np.sqrt(1 - zeta**2)
    step = 1 - np.exp(-zeta * wn * t) * (np.cos(wd * t) +
                      (zeta / np.sqrt(1 - zeta**2)) * np.sin(wd * t))
else:
    step = 1 - np.exp(-wn * t)

t_lock_est = 1 / (zeta * wn) * 5   # 5× time constant
print(f"\n--- Locking Estimate ---")
print(f"  ωn   = {wn/(2*np.pi)/1e6:.2f} MHz")
print(f"  ζ    = {zeta:.2f}")
print(f"  t_lock ≈ {t_lock_est*1e6:.2f} µs  (5τ estimate)")

fig2, ax3 = plt.subplots(figsize=(9, 4))
ax3.plot(t * 1e6, step * 100, 'b', linewidth=2)
ax3.set_xlabel("Time (µs)")
ax3.set_ylabel("Phase Lock (%)")
ax3.set_title(f"CP-PLL Approximate Step Response  (ζ={zeta:.2f}, ωn={wn/(2*np.pi)/1e6:.1f} MHz)")
ax3.axhline(100, color='k', linestyle='--', linewidth=0.8)
ax3.axhline(90,  color='g', linestyle=':', linewidth=0.8, label='90%')
ax3.grid(True, alpha=0.3)
ax3.legend()
plt.tight_layout()
plt.savefig("../pll_step.png", dpi=150, bbox_inches='tight')
print("  Step response saved → pll_step.png")

# ─────────────────────────────────────────────
# 14.  DESIGN SUMMARY TABLE
# ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("  FINAL DESIGN SUMMARY")
print("=" * 55)
params = [
    ("f_ref",        f"{F_REF/1e6:.0f} MHz"),
    ("f_out",        f"{F_OUT/1e9:.0f} GHz"),
    ("N (÷10)",      f"{N_DIV}  (÷2 CML + ÷5 TSPC)"),
    ("VDD",          f"{VDD} V"),
    ("Technology",   "TSMC 180nm CMOS"),
    ("Loop BW f_c",  f"{fc_act/1e6:.2f} MHz"),
    ("Phase Margin", f"{pm_act:.1f}°"),
    ("f_zero",       f"{fz/1e6:.2f} MHz"),
    ("f_pole2",      f"{fp2/1e6:.2f} MHz"),
    ("R1",           f"{R1:.0f} Ω"),
    ("C1",           f"{C1*1e12:.1f} pF"),
    ("C2",           f"{C2*1e12:.2f} pF"),
    ("Icp",          f"{Icp*1e6:.0f} µA"),
    ("Kvco",         f"{Kvco/1e6:.0f} MHz/V"),
    ("L_tank",       f"{L_tank*1e9:.0f} nH"),
    ("C_tank",       f"{C_tank*1e12:.1f} pF"),
    ("TOTAL Power",  f"{P_total*1e3:.1f} mW  (budget: 100 mW)"),
]
for k, v in params:
    print(f"  {k:<18} {v}")
print("=" * 55)

plt.show()
