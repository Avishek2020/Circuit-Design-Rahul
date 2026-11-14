# Charge Pump PLL — Design Specification
**f_ref = 100 MHz → f_out = 1 GHz | TSMC 180nm CMOS | VDD = 1.8V**

---

## 1. Architecture

```
                 ┌─────────────────────────────────────────────────┐
                 │                                                 │
  XTAL 100MHz   │                   Loop Filter                   │
  ──────────► PFD ──► Charge Pump ──► R1─C1─C2 ──► VCO ──► OUT (1 GHz)
               ▲  UP/DN  Icp=200µA   3.9kΩ,30pF,2pF  Kvco=400MHz/V
               │                                        │
               └────────────── ÷10 (÷2 × ÷5) ──────────┘
                               CML+TSPC
```

**Block summary:**

| Block | Topology | Key Param |
|---|---|---|
| PFD | 2× TSPC D-FF + NAND reset | Treset = 100 ps (dead-zone-free) |
| Charge Pump | Cascode P/N current mirror | Icp = 200 µA, mismatch < 1% |
| Loop Filter | Passive 3rd-order (R-C-C) | R1=3.9kΩ, C1=30pF, C2=2pF |
| VCO | NMOS cross-coupled LC | L=2nH, Ctank=12.7pF, Kvco=400MHz/V |
| Divider | CML ÷2 + TSPC ÷5 | 1GHz → 500MHz → 100MHz |
| Output Buffer | CML diff → SE, 50Ω | Ibias = 4 mA |

---

## 2. Loop Filter Design (Derivation)

### Target
- Loop bandwidth: **f_c = 5 MHz** (= f_ref / 20, well within stability rule)
- Phase margin: **PM = 60°**

### Topology
```
  CP_out ──┬── R1 ──┬── VCO_ctrl
           |        |
          C2       C1
           |        |
          GND      GND
```
Transfer function:
```
         1 + s·R1·C1
Z(s) = ────────────────────────────────
        s·(C1+C2)·(1 + s·R1·C1·C2/(C1+C2))
```
Zero:  fz  = 1/(2π·R1·C1) = **1.34 MHz**  
Pole2: fp2 = 1/(2π·R1·C2) = **18.7 MHz**

### Optimal Phase Placement
For maximum phase boost at crossover, place:
```
  f_c = √(fz · fp2)   ⟹   fz = fc/r,  fp2 = fc·r,  r = tan(75°) = 3.73
```
Phase margin = arctan(fc/fz) − arctan(fc/fp2) = **75.5° − 14.5° = 61°** ✓

### Component Values
```
  R1  = 2π·N·ωc / (Icp · Kvco_rad)  =  3927 Ω    → use 3.9 kΩ (1%)
  C1  = 1 / (ωz · R1)               = 30.3 pF    → use 30 pF
  C2  = 1 / (ωp2 · R1)              =  2.2 pF    → use 2.2 pF
```

---

## 3. VCO — NMOS Cross-Coupled LC Oscillator

```
       VDD
        |
   ┌────┴────┐
  L/2       L/2    (each 1nH, Rs=0.9Ω, Q=7 @1GHz)
   |         |
  VOP       VON
   |─┐   ┌─|
   | M2  M1 |    W=20µm/0.18µm, cross-coupled
   └─┘   └─┘
   |         |
  Cvar     Cvar   (inversion-mode MOS varactor, W=20µm/0.5µm)
   |         |
  VOP       VON → ctrl (loop filter output)
   |         |
   └────┬────┘
       M3 (tail)   W=50µm/0.5µm, Itail = 5 mA
        |
       GND
```

**Tank resonance:**
```
  f = 1/(2π√LC) = 1/(2π√(2nH · 12.7pF)) = 1 GHz  ✓
  
  Varactor tuning range: ΔC ≈ ±4 pF over 0.4V–1.4V
  Kvco = Δf/ΔV ≈ (1/2) · f/(LC) · ΔC/ΔV = 400 MHz/V
```

**Oscillation condition:**  gm > 1/Rp = ωL/(Q·R) → gm_min ≈ 1.1 mS  
**Actual gm** (Itail=5mA, two transistors): gm ≈ 2×Id/(2VT) = 2×2.5mA/52mV ≈ **48 mS** >> 1.1 mS (ample margin)

**Phase noise (Leeson):**
```
  L(fm) = 10·log[(f0/(2·Q·fm))² · F·kT/Ps]
         = -132 dBc/Hz  at fm = 1 MHz offset
```

---

## 4. Charge Pump — Cascode Current Source

```
  VDD ─── MP1(W=20/0.5) ─── MP2(W=20/0.5) cascode
                                   |
                              [SW_P, PMOS 10/0.18]  ← UP controls
                                   |
                              LF_OUT ──────────────► loop filter
                                   |
                              [SW_N, NMOS 10/0.18]  ← DN controls
                                   |
                            MN2(W=20/0.5) cascode ─── MN1(W=20/0.5)
  GND ───────────────────────────────────────────────────────────────
```

- **Icp = 200 µA** (set by PMOS/NMOS current mirror bias)
- Cascode ensures Zout > 1 MΩ (reduces static phase error)
- Mismatch target: < 1% (use common-centroid layout)
- Output voltage range: 0.3V – 1.5V (cascode headroom)

---

## 5. Frequency Divider (÷10)

### Stage 1: CML ÷2 (1 GHz → 500 MHz)
- Master-slave DFF in CML topology
- Differential: low sensitivity to supply noise
- Ibias = 2 × 1 mA = 2 mA per stage → **P = 3.6 mW**
- Sizing: W_diff = 8µm/0.18µm, W_load = PMOS 400Ω poly resistor

### Stage 2: TSPC ÷5 (500 MHz → 100 MHz)
- 3-bit synchronous modulo-5 counter using TSPC DFFs
- Reset state: Q2·Q0 → reset on state 5 → back to 0
- **P = 1.5 mW** (single-phase clock, reduced switching)

### Output: 100 MHz feedback to PFD

---

## 6. Power Budget

| Block | Power | % of Total |
|---|---|---|
| VCO (LC oscillator) | 9.0 mW | 45% |
| CML ÷2 divider | 3.6 mW | 18% |
| TSPC ÷5 divider | 1.5 mW | 8% |
| Output buffer | 4.0 mW | 20% |
| PFD | 0.8 mW | 4% |
| Charge pump | ~0 mW | 0% |
| Bias / bandgap | 1.5 mW | 8% |
| **TOTAL** | **~20 mW** | **< 100 mW ✓** |

**5× power margin** vs. the 100 mW budget.

---

## 7. Key Verified Results (from design_calc.py)

```
  f_ref          =  100 MHz
  f_out          =    1 GHz
  N              =   10 (÷2 CML + ÷5 TSPC)
  VDD            =  1.8 V  (TSMC 180nm)
  Loop BW f_c    =  4.72 MHz   (target 5 MHz)
  Phase Margin   =  60.9°      (target 60°)
  f_zero  fz     =  1.34 MHz
  f_pole2 fp2    = 18.66 MHz
  R1             =  3927 Ω
  C1             =  30.3 pF
  C2             =   2.2 pF
  Icp            =  200 µA
  Kvco           =  400 MHz/V
  L_tank         =    2 nH
  C_tank (fixed) =  12.7 pF (+ varactor ±4 pF)
  VCO PN @1MHz   = -132 dBc/Hz  (Leeson)
  Lock time      = ~1.2 µs  (5τ estimate, overdamped ζ=16)
  Total Power    =  19.8 mW
```

---

## 8. Simulation Files

| File | Description |
|---|---|
| `scripts/design_calc.py` | Python: all parameter calculations + Bode plots |
| `spice/cp_pll_behavioral.cir` | LTspice/ngspice behavioral transient netlist |
| `spice/pll_transistor_level.cir` | Transistor-level subckts (TSMC 180nm models) |
| `verilog_a/vco.vams` | Verilog-A VCO (Spectre / Cadence Virtuoso) |
| `verilog_a/pfd.vams` | Verilog-A PFD (tri-state, dead-zone-free) |
| `verilog_a/charge_pump.vams` | Verilog-A CP (with mismatch + leakage) |
| `verilog_a/divider.vams` | Verilog-A ÷2 CML + ÷5 TSPC |
| `verilog_a/pll_top.vams` | Verilog-A top-level with passive loop filter |
| `pll_bode.png` | Bode plot (magnitude + phase, generated) |
| `pll_step.png` | Step response / lock time estimate |

---

## 9. Layout Guidelines

**VCO:**
- Inductor: octagonal spiral, outer diameter ≤ 150 µm, 3–4 turns
- Keep substrate contacts away from inductor center (eddy current reduction)
- Use top metal (Metal 6) for inductor to maximise Q

**Charge Pump:**
- Common-centroid interdigitation for P/N current source matching
- Dummy transistors at array edges to equalise oxide fringe effects

**Loop Filter:**
- MIM capacitors (C1, C2) for low voltage coefficient
- Keep R1, C1, C2 close to CP output to minimise parasitic coupling

**Divider:**
- CML stage shields VCO from digital switching noise
- Place TSPC ÷5 away from VCO tank; use guard ring

**Reference floorplan (die area estimate ~0.5 mm²):**
```
  ┌────────────────────────────────────────┐
  │   Inductor (150µm × 150µm)             │
  │   ┌──────┐  ┌────────┐  ┌──────────┐  │
  │   │ VCO  │  │  LF    │  │  CP+PFD  │  │
  │   │ core │  │R1,C1,C2│  │          │  │
  │   └──────┘  └────────┘  └──────────┘  │
  │   ┌───────────────────┐  ┌──────────┐  │
  │   │  CML ÷2 + TSPC ÷5│  │ Out Buf  │  │
  │   └───────────────────┘  └──────────┘  │
  │            Bias / Bandgap              │
  └────────────────────────────────────────┘
```
