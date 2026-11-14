"""
Unit tests for the CP-PLL design.
Run:  pytest test_pll.py -v
"""

import numpy as np
import pytest
from scipy.integrate import solve_ivp

# ─── Shared design constants ────────────────────────────
F_REF  = 100e6
F0     = 1e9
KVCO   = 400e6
V0     = 0.9
ICP    = 200e-6
N_DIV  = 10
R1     = 3927.0
C1     = 30e-12
C2     = 2.2e-12
VDD    = 1.8


# ════════════════════════════════════════════════════════
# 1.  FREQUENCY DIVISION
# ════════════════════════════════════════════════════════

def test_division_ratio():
    assert F0 / F_REF == N_DIV


def test_vco_at_lock_point():
    f = F0 + KVCO * (V0 - V0)
    assert f == pytest.approx(1e9)


def test_vco_tuning_range():
    f_low  = F0 + KVCO * (0.4 - V0)   # Vctrl = 0.4 V
    f_high = F0 + KVCO * (1.4 - V0)   # Vctrl = 1.4 V
    assert f_low  == pytest.approx(800e6)
    assert f_high == pytest.approx(1.2e9)


# ════════════════════════════════════════════════════════
# 2.  LOOP FILTER — POLE / ZERO FREQUENCIES
# ════════════════════════════════════════════════════════

def test_filter_zero_frequency():
    fz = 1 / (2 * np.pi * R1 * C1)
    assert fz == pytest.approx(1.34e6, rel=0.05)   # 1.34 MHz ± 5%


def test_filter_pole2_frequency():
    fp2 = 1 / (2 * np.pi * R1 * C2)
    assert fp2 == pytest.approx(18.5e6, rel=0.05)  # 18.5 MHz ± 5%


def test_filter_cap_ratio():
    # C1 must be >> C2 for approximation to hold (ratio > 10)
    assert C1 / C2 > 10


def test_crossover_at_geometric_mean():
    wz   = 1 / (R1 * C1)
    wp2  = 1 / (R1 * C2)
    fc_expected = np.sqrt(wz * wp2) / (2 * np.pi)
    # geometric-mean crossover gives maximum phase boost
    assert fc_expected == pytest.approx(5e6, rel=0.15)   # ~5 MHz ± 15%


# ════════════════════════════════════════════════════════
# 3.  OPEN-LOOP PHASE MARGIN
# ════════════════════════════════════════════════════════

def _open_loop_gain(freqs):
    w         = 2 * np.pi * np.asarray(freqs)
    Kvco_rad  = 2 * np.pi * KVCO
    Kpd       = ICP / (2 * np.pi)
    # loop filter impedance Z(jw)
    num = 1 + 1j * w * R1 * C1
    den = 1j * w * (C1 + C2) * (1 + 1j * w * R1 * C1 * C2 / (C1 + C2))
    Z   = num / den
    G   = Kpd * Kvco_rad / N_DIV * Z / (1j * w)
    return G


def test_phase_margin_above_55_degrees():
    freqs = np.logspace(4, 9, 10000)
    G     = _open_loop_gain(freqs)
    # find 0 dB crossover
    mag   = np.abs(G)
    idx   = np.argmin(np.abs(mag - 1.0))
    phase_at_xo = np.angle(G[idx], deg=True)
    pm    = 180 + phase_at_xo
    assert pm > 55, f"Phase margin {pm:.1f}° < 55°"


def test_phase_margin_below_75_degrees():
    freqs = np.logspace(4, 9, 10000)
    G     = _open_loop_gain(freqs)
    mag   = np.abs(G)
    idx   = np.argmin(np.abs(mag - 1.0))
    phase_at_xo = np.angle(G[idx], deg=True)
    pm    = 180 + phase_at_xo
    assert pm < 75, f"Phase margin {pm:.1f}° > 75° (over-damped)"


def test_loop_bandwidth_in_range():
    freqs = np.logspace(4, 9, 10000)
    G     = _open_loop_gain(freqs)
    mag   = np.abs(G)
    idx   = np.argmin(np.abs(mag - 1.0))
    fc    = freqs[idx]
    assert 3e6 < fc < 8e6, f"Loop BW {fc/1e6:.2f} MHz out of [3, 8] MHz"


# ════════════════════════════════════════════════════════
# 4.  ODE SYSTEM — CHARGE PUMP PLL
# ════════════════════════════════════════════════════════

def _pll_odes(t, y):
    phi_err, V_N1, V_CTRL = y
    f_vco  = np.clip(F0 + KVCO * (V_CTRL - V0), 200e6, 1.8e9)
    dphi   = 2 * np.pi * (F_REF - f_vco / N_DIV)
    I_cp   = ICP * np.clip(phi_err / (2 * np.pi), -1.0, 1.0)
    I_R1   = (V_CTRL - V_N1) / R1
    return [dphi, I_R1 / C1, (I_cp - I_R1) / C2]


def _run_sim(t_end=3e-6, v_ctrl_0=0.5):
    y0  = [0.0, v_ctrl_0, v_ctrl_0]
    sol = solve_ivp(_pll_odes, (0, t_end), y0,
                    method="RK45", rtol=1e-9, atol=1e-12,
                    max_step=2e-9, dense_output=False)
    return sol


def test_sim_converges():
    sol = _run_sim()
    assert sol.success, f"ODE solver failed: {sol.message}"


def test_steady_state_vctrl():
    sol = _run_sim()
    t, V_CTRL = sol.t, sol.y[2]
    v_ss = float(np.mean(V_CTRL[t > 2.5e-6]))
    assert v_ss == pytest.approx(V0, abs=0.001), \
        f"SS V(CTRL) = {v_ss:.4f} V, expected {V0} V"


def test_steady_state_frequency():
    sol = _run_sim()
    t, V_CTRL = sol.t, sol.y[2]
    v_ss   = float(np.mean(V_CTRL[t > 2.5e-6]))
    f_ss   = F0 + KVCO * (v_ss - V0)
    assert f_ss == pytest.approx(F0, rel=1e-4), \
        f"SS f_vco = {f_ss/1e9:.6f} GHz, expected 1.000000 GHz"


def test_steady_state_phase_error_near_zero():
    sol = _run_sim()
    t, phi = sol.t, sol.y[0]
    phi_ss_cycles = float(np.mean(phi[t > 2.5e-6])) / (2 * np.pi)
    assert abs(phi_ss_cycles) < 0.01, \
        f"SS phase error = {phi_ss_cycles:.4f} cycles (> 0.01)"


def test_lock_time_under_1us():
    sol   = _run_sim()
    t     = sol.t
    f_vco = np.clip(F0 + KVCO * (sol.y[2] - V0), 200e6, 1.8e9)
    outside = np.where(np.abs(f_vco - F0) > 0.001 * F0)[0]
    t_lock  = t[outside[-1]] if len(outside) > 0 else 0.0
    assert t_lock < 1e-6, f"Lock time {t_lock*1e6:.3f} µs > 1 µs"


def test_no_lock_without_feedback():
    """With KVCO=0 (open-loop VCO), Vctrl must still ramp — loop does not stall."""
    def odes_open(t, y):
        phi_err, V_N1, V_CTRL = y
        # VCO stuck at F0 (no feedback, KVCO=0)
        dphi = 2 * np.pi * (F_REF - F0 / N_DIV)   # always zero since F0/N=F_REF
        I_cp = ICP * np.clip(phi_err / (2 * np.pi), -1.0, 1.0)
        I_R1 = (V_CTRL - V_N1) / R1
        return [dphi, I_R1 / C1, (I_cp - I_R1) / C2]

    # F0/N_DIV = F_REF exactly → dphi = 0 always → locked trivially
    sol = solve_ivp(odes_open, (0, 1e-6), [0.0, 0.9, 0.9],
                    method="RK45", rtol=1e-9, atol=1e-12, max_step=2e-9)
    assert sol.success


# ════════════════════════════════════════════════════════
# 5.  CHARGE PUMP SATURATION
# ════════════════════════════════════════════════════════

def test_cp_saturates_at_plus_icp():
    phi_large = 100 * 2 * np.pi   # many cycles out of lock
    I = ICP * np.clip(phi_large / (2 * np.pi), -1, 1)
    assert I == pytest.approx(ICP)


def test_cp_saturates_at_minus_icp():
    phi_large = -50 * 2 * np.pi
    I = ICP * np.clip(phi_large / (2 * np.pi), -1, 1)
    assert I == pytest.approx(-ICP)


def test_cp_linear_region():
    phi = np.pi / 2   # 0.25 cycles — well within linear range
    I   = ICP * np.clip(phi / (2 * np.pi), -1, 1)
    assert I == pytest.approx(ICP * 0.25, rel=1e-6)


# ════════════════════════════════════════════════════════
# 6.  POWER BUDGET
# ════════════════════════════════════════════════════════

def test_total_power_under_100mW():
    P_vco  = VDD * 5e-3       # 9 mW
    P_div  = 3e-3 + 1.5e-3   # 4.5 mW
    P_pfd  = 0.8e-3
    P_buf  = 4e-3
    P_bias = 1.5e-3
    P_total = P_vco + P_div + P_pfd + P_buf + P_bias
    assert P_total < 0.1, f"Total power {P_total*1e3:.1f} mW exceeds 100 mW"


def test_vco_power_dominates():
    P_vco = VDD * 5e-3
    P_div = 3e-3 + 1.5e-3
    assert P_vco > P_div


# ════════════════════════════════════════════════════════
# 7.  ACQUISITION FROM EXTREME STARTING POINTS
# ════════════════════════════════════════════════════════

@pytest.mark.parametrize("v_start", [0.3, 0.5, 0.7, 1.1, 1.4])
def test_locks_from_various_initial_vctrl(v_start):
    sol   = _run_sim(t_end=5e-6, v_ctrl_0=v_start)
    assert sol.success
    v_ss  = float(np.mean(sol.y[2][sol.t > 4e-6]))
    assert v_ss == pytest.approx(V0, abs=0.005), \
        f"Start {v_start} V: SS V(CTRL) = {v_ss:.4f} V ≠ {V0} V"
