"""
CP-PLL Web Simulator
Run: uvicorn app:app --reload --port 8000
"""

import os
import numpy as np
from pathlib import Path
from scipy.integrate import solve_ivp

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ── Constants ──────────────────────────────────────────────
F_REF = 100e6
F0    = 1e9
V0    = 0.9
VDD   = 1.8
N_DIV = 10

LOG_PATH = Path(__file__).parent.parent / "spice" / "cp_pll_ltspice.log"

app = FastAPI(title="CP-PLL Simulator")

STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC / "index.html"))


# ── Simulation request schema ──────────────────────────────
class SimParams(BaseModel):
    icp:        float = Field(200e-6,  ge=10e-6,  le=1e-3,  description="Charge pump current (A)")
    kvco:       float = Field(400e6,   ge=50e6,   le=2e9,   description="VCO gain (Hz/V)")
    r1:         float = Field(3927.0,  ge=100,    le=50000, description="Loop filter R (Ω)")
    c1:         float = Field(30e-12,  ge=1e-12,  le=200e-12, description="Loop filter C1 (F)")
    c2:         float = Field(2.2e-12, ge=0.1e-12, le=50e-12, description="Loop filter C2 (F)")
    v_ctrl_init: float = Field(0.5,   ge=0.1,    le=1.7,   description="Initial Vctrl (V)")
    t_end_us:   float = Field(3.0,    ge=0.5,    le=20.0,  description="Sim duration (µs)")


# ── ODE system ─────────────────────────────────────────────
def _make_odes(icp, kvco, r1, c1, c2):
    def odes(t, y):
        phi_err, V_N1, V_CTRL = y
        f_vco = np.clip(F0 + kvco * (V_CTRL - V0), 200e6, 1.8e9)
        dphi  = 2 * np.pi * (F_REF - f_vco / N_DIV)
        I_cp  = icp * np.clip(phi_err / (2 * np.pi), -1.0, 1.0)
        I_R1  = (V_CTRL - V_N1) / r1
        return [dphi, I_R1 / c1, (I_cp - I_R1) / c2]
    return odes


def _run(p: SimParams):
    t_end = p.t_end_us * 1e-6
    y0    = [0.0, p.v_ctrl_init, p.v_ctrl_init]
    sol   = solve_ivp(
        _make_odes(p.icp, p.kvco, p.r1, p.c1, p.c2),
        (0, t_end), y0,
        method="RK45", rtol=1e-9, atol=1e-12,
        max_step=2e-9, dense_output=False,
    )
    if not sol.success:
        raise ValueError(sol.message)
    return sol


def _metrics(sol, icp, t_end_us):
    t      = sol.t
    V_CTRL = sol.y[2]
    phi    = sol.y[0]
    f_vco  = np.clip(F0 + 400e6 * (V_CTRL - V0), 200e6, 1.8e9)   # for display

    # Steady-state window: last 20% of sim
    ss_start = t[-1] * 0.8
    mask_ss  = t > ss_start
    v_ss     = float(np.mean(V_CTRL[mask_ss])) if mask_ss.any() else V_CTRL[-1]
    f_ss     = float(np.mean(f_vco[mask_ss]))  if mask_ss.any() else f_vco[-1]
    ppm      = (f_ss - F0) / F0 * 1e6

    # Lock time: last sample outside ±0.1% of F0
    BAND    = 0.001
    outside = np.where(np.abs(f_vco - F0) > BAND * F0)[0]
    t_lock  = float(t[outside[-1]] * 1e6) if len(outside) > 0 else 0.0

    # Phase margin from open-loop Bode (using sim params)
    # (re-compute analytically for display)
    return {
        "lock_time_us":   round(t_lock, 4),
        "v_ctrl_ss_v":    round(v_ss, 6),
        "freq_ss_ghz":    round(f_ss / 1e9, 7),
        "freq_error_ppm": round(ppm, 4),
    }


def _power(icp):
    P_vco  = VDD * 5e-3
    P_div  = 3e-3 + 1.5e-3
    P_pfd  = 0.8e-3
    P_buf  = 4e-3
    P_bias = 1.5e-3
    return round((P_vco + P_div + P_pfd + P_buf + P_bias) * 1e3, 2)   # mW


def _phase_margin(icp, kvco, r1, c1, c2):
    freqs      = np.logspace(4, 9, 10000)
    w          = 2 * np.pi * freqs
    Kvco_rad   = 2 * np.pi * kvco
    Kpd        = icp / (2 * np.pi)
    num        = 1 + 1j * w * r1 * c1
    den        = 1j * w * (c1 + c2) * (1 + 1j * w * r1 * c1 * c2 / (c1 + c2))
    Z          = num / den
    G          = Kpd * Kvco_rad / N_DIV * Z / (1j * w)
    mag        = np.abs(G)
    idx        = np.argmin(np.abs(mag - 1.0))
    fc         = freqs[idx]
    phase_xo   = np.angle(G[idx], deg=True)
    pm         = 180 + phase_xo
    return round(float(pm), 1), round(float(fc / 1e6), 2)


# ── LTspice log parser ─────────────────────────────────────
def _parse_log():
    if not LOG_PATH.exists():
        return None
    meas = {}
    with open(LOG_PATH) as f:
        for line in f:
            for key in ("t_lock", "vctrl_ss", "fvco_ss"):
                if line.lower().startswith(key):
                    try:
                        meas[key] = float(line.split("=")[1].split()[0])
                    except Exception:
                        pass
    return meas if meas else None


# ── API endpoint ───────────────────────────────────────────
@app.post("/simulate")
def simulate(p: SimParams):
    try:
        sol = _run(p)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    t      = sol.t
    V_CTRL = sol.y[2]
    V_N1   = sol.y[1]
    phi    = sol.y[0]
    f_vco  = np.clip(F0 + p.kvco * (V_CTRL - V0), 200e6, 1.8e9)
    I_cp   = p.icp * np.clip(phi / (2 * np.pi), -1.0, 1.0)

    # Downsample to ≤4000 points for fast JSON transfer
    n      = len(t)
    step   = max(1, n // 4000)
    sl     = slice(None, None, step)

    metrics   = _metrics(sol, p.icp, p.t_end_us)
    pm, fc    = _phase_margin(p.icp, p.kvco, p.r1, p.c1, p.c2)
    spice_log = _parse_log()

    # Loop filter frequencies
    fz  = round(1 / (2 * np.pi * p.r1 * p.c1) / 1e6, 3)
    fp2 = round(1 / (2 * np.pi * p.r1 * p.c2) / 1e6, 3)

    return JSONResponse({
        "time_us":      list(t[sl] * 1e6),
        "v_ctrl":       list(V_CTRL[sl]),
        "v_n1":         list(V_N1[sl]),
        "f_vco_mhz":    list(f_vco[sl] / 1e6),
        "phase_cycles": list(phi[sl] / (2 * np.pi)),
        "i_cp_ua":      list(I_cp[sl] * 1e6),
        "metrics":      metrics,
        "loop": {
            "phase_margin_deg": pm,
            "crossover_mhz":    fc,
            "zero_mhz":         fz,
            "pole2_mhz":        fp2,
            "power_mw":         _power(p.icp),
        },
        "spice_log": spice_log,
    })
