#!/usr/bin/env python3
"""
Diagnostic test suite for qu_model_viewer.py polarisation models.

For each RM-Tools model, a P(lambda^2) spectrum is synthesised using
analytically-chosen parameters whose FDF peak locations are known exactly.
RM synthesis is then run and the detected peaks are compared against the
expected values to within half the RMSF FWHM (the Faraday resolution limit).

A summary table is printed and a figure of all 10 model FDFs is saved.

Usage:
    python3 test_models.py freqFile.dat
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# -- Import physics functions from the viewer ----------------------------------
sys.path.insert(0, os.path.dirname(__file__))
src = open(os.path.join(os.path.dirname(__file__), "qu_model_viewer.py")).read()
src = src.replace("if __name__ == '__main__':", "if False:")
_ns = {}
exec(compile(src, "qu_model_viewer.py", "exec"), _ns)
model_P      = _ns["model_P"]
rm_synthesis = _ns["rm_synthesis"]

C = 2.998e8

PHI_MIN, PHI_MAX, N_PHI = -600.0, 600.0, 2401
phi  = np.linspace(PHI_MIN, PHI_MAX, N_PHI)
dphi = (PHI_MAX - PHI_MIN) / (N_PHI - 1)

# -- Test cases ----------------------------------------------------------------
# Each entry: (model_id, parameter_values, expected_peak_phis, description)
TEST_CASES = [
    ("m1",
     [0.5,  0.0,  100.0],
     [100.0],
     "thin source at RM=100"),

    ("m2",
     [0.5,  0.0,  100.0,  10.0],
     [100.0],
     "external dispersion, RM=100, sigma=10"),

    ("m5",
     [0.5,  0.0,   60.0,  40.0],
     [80.0],                         # peak at RM + dRM/2 = 60+20 = 80
     "Burn slab RM=60, dRM=40; peak at 80"),

    ("m6",
     [0.5,  0.0,  -80.0, 20.0,
      0.3, 45.0,  100.0, 20.0],
     [-70.0, 110.0],                 # RM1+dRM1/2=-70, RM2+dRM2/2=110
     "double Burn slab; peaks at -70, 110"),

    ("m7",
     [0.5,  0.0,  100.0,  5.0,  5.0],
     [100.0],
     "internal dispersion, RM=100, dRM=5, sigma=5"),

    ("m11",
     [0.5,  0.0,  -80.0,
      0.3, 45.0,  100.0],
     [-80.0, 100.0],
     "two thin sources at -80 and +100"),

    ("m3",
     [0.5,  0.0,  -80.0,
      0.3, 45.0,  100.0,  5.0],
     [-80.0, 100.0],
     "two thin + shared sigma=5"),

    ("m4",
     [0.5,  0.0,  -80.0,  3.0,
      0.3, 45.0,  100.0,  5.0],
     [-80.0, 100.0],
     "two thin + individual sigmas 3, 5"),

    ("m12",
     [0.5,  0.0,  100.0,  5.0,  5.0,  5.0],
     [100.0],
     "internal dispersion + foreground screen, RM_screen=100"),

    ("m111",
     [0.5,  0.0, -100.0,
      0.3, 45.0,   50.0,
      0.2,-45.0,  150.0],
     [-100.0, 50.0, 150.0],
     "three thin sources at -100, +50, +150"),
]


def run_tests(freqs):
    lam2 = (C / freqs) ** 2

    # RMSF FWHM: tolerance for peak matching
    dl2   = lam2.max() - lam2.min()
    fwhm  = 2 * np.sqrt(3) / dl2      # rad/m^2
    tol   = fwhm / 2.0
    minsep = max(1, int(fwhm / (2 * dphi)))   # minimum peak separation in samples

    print(f"\n  Frequencies : {len(freqs)} channels  "
          f"({freqs.min()/1e9:.3f} - {freqs.max()/1e9:.3f} GHz)")
    print(f"  RMSF FWHM   : {fwhm:.1f} rad/m²   (match tolerance ± {tol:.1f} rad/m²)\n")
    print(f"  {'Model':<6} {'Expected peaks':>28}  {'Detected peaks':>28}  "
          f"{'Max Δφ':>9}  {'Result'}")
    print("  " + "-" * 88)

    results   = []
    fig, axes = plt.subplots(2, 5, figsize=(18, 7), sharey=False)
    fig.suptitle("RM-Tools Model Diagnostic  -  FDF peak-location test\n"
                 f"({len(freqs)} channels, RMSF FWHM ≈ {fwhm:.1f} rad/m²,  "
                 f"tolerance ± {tol:.1f} rad/m²)",
                 fontsize=11, fontweight="bold")

    for ax, (model, vals, expected, desc) in zip(axes.flat, TEST_CASES):
        P   = model_P(model, vals, lam2)
        amp = np.abs(rm_synthesis(P, lam2, phi))
        amax = amp.max() if amp.max() > 0 else 1.0

        pk_idx, _ = find_peaks(amp,
                               height=0.05 * amax,
                               prominence=0.15 * amax,
                               distance=minsep)
        detected = sorted([round(phi[i], 1) for i in pk_idx])

        # Match: every expected peak must have a detected peak within tolerance
        matched = []
        for exp_phi in expected:
            close = [d for d in detected if abs(d - exp_phi) <= tol]
            matched.append(bool(close))
        passed = all(matched)

        max_delta = max(
            (min(abs(d - e) for d in detected) if detected else 999.0)
            for e in expected
        )

        tag = "PASS" if passed else "FAIL"
        results.append(passed)
        exp_str = str([f"{e:+.0f}" for e in expected])
        det_str = str([f"{d:+.1f}" for d in detected[:len(expected)+2]])
        print(f"  {model:<6} {exp_str:>28}  {det_str:>28}  {max_delta:>8.1f}  {tag}")

        # -- Subplot -----------------------------------------------------------
        color = "#2ecc71" if passed else "#e74c3c"
        ax.plot(phi, amp / amax, color="steelblue", lw=1.3)
        for e in expected:
            ax.axvline(e, color="green",  lw=1.0, ls="--", alpha=0.7)
        for i in pk_idx:
            ax.axvline(phi[i], color="tomato", lw=0.9, ls=":", alpha=0.8)
        ax.set_title(f"{model}  [{tag}]", fontsize=9,
                     color=color, fontweight="bold")
        ax.set_xlabel("φ [rad/m²]", fontsize=7)
        ax.set_ylabel("|FDF| (norm.)", fontsize=7)
        ax.tick_params(labelsize=6)
        ax.set_xlim(PHI_MIN, PHI_MAX)
        ax.set_ylim(0, 1.25)
        ax.grid(True, alpha=0.2)
        ax.text(0.02, 0.95, desc, transform=ax.transAxes,
                fontsize=6, va="top", color="gray")

    # Legend
    from matplotlib.lines import Line2D
    legend = [Line2D([0],[0], color="green",  ls="--", lw=1.2, label="expected peak"),
              Line2D([0],[0], color="tomato",  ls=":",  lw=1.2, label="detected peak")]
    fig.legend(handles=legend, loc="lower center", ncol=2,
               fontsize=8, framealpha=0.8)

    n_pass = sum(results)
    print("  " + "-" * 88)
    print(f"\n  {n_pass}/{len(results)} models PASSED\n")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    out = os.path.join(os.path.dirname(__file__), "model_diagnostics.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"  Figure saved: {out}\n")
    return n_pass == len(results)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_models.py freqFile.dat")
        sys.exit(1)
    freqs = np.loadtxt(sys.argv[1])
    ok    = run_tests(freqs)
    sys.exit(0 if ok else 1)
