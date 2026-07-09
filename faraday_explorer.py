#!/usr/bin/env python3
"""
Faraday Explorer — Interactive Faraday depth polarisation model viewer.

PyQt5 application: native controls, embedded matplotlib canvases.
Run:  conda run -n faraday_explorer python3 faraday_explorer.py FDF.fits I.fits Q.fits U.fits freqFile.dat
"""

import os, sys, json, subprocess
import numpy as np
from scipy.signal import find_peaks
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavToolbar,
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDockWidget,
    QSplitter, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QDoubleSpinBox, QSlider, QLineEdit,
    QGroupBox, QScrollArea, QFrame, QSizePolicy, QStatusBar,
    QDialog, QFormLayout, QPushButton, QFileDialog,
    QCheckBox, QSpinBox, QMessageBox, QStackedWidget, QProgressBar,
    QToolButton, QMenu, QAction, QActionGroup, QInputDialog,
)
from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSettings, QEventLoop, QLocale
from PyQt5.QtGui import QFont, QPixmap, QImage

# Two-phase splash: branding video → app-name video.
# Both decoded frame-by-frame via ffmpeg pipe — no GStreamer needed.
_HERE = os.path.dirname(os.path.abspath(__file__))
SPLASH_VIDEO_1  = os.path.join(_HERE, "splash.mp4")       # amani Astro branding
SPLASH_VIDEO_2  = os.path.join(_HERE, "splash_app.mp4")   # Faraday Explorer title
SPLASH_IMAGE    = os.path.join(_HERE, "splash_frame.png") # static fallback
SPLASH_WIDTH    = 500   # display width in pixels (height scaled proportionally)
SPLASH_EXTRA_MS = 500   # ms to hold last frame of video 2 before closing (2x faster)

# Resolve ffmpeg/ffprobe from the conda env's bin (same dir as sys.executable).
# The launcher runs Python directly without `conda activate`, so the env's bin
# directory is NOT on PATH — subprocess("ffmpeg") would silently fail.
def _find_bin(name):
    env_bin = os.path.join(os.path.dirname(sys.executable), name)
    return env_bin if os.path.exists(env_bin) else name
_FFMPEG  = _find_bin("ffmpeg")
_FFPROBE = _find_bin("ffprobe")


# ── Physical constants ────────────────────────────────────────────────────────
C = 2.998e8

FREQ_MIN = 856e6
FREQ_MAX = 1711e6
N_CHAN   = 9

PHI_MIN  = -600.0
PHI_MAX  =  600.0
N_PHI    = 2401

FITS_PATH = os.path.join(os.path.dirname(__file__), "NGC1097_FDF.fits")
MAP_STEP  = 24


# ── RM-Tools model parameter specs ───────────────────────────────────────────
MODEL_PARAMS = {
    "m1": [
        ("p₀",            0.0,  1.0,   0.5),
        ("χ₀  [°]",     -90.0, 90.0,   0.0),
        ("RM  [rad/m²]", -400, 400,   50.0),
    ],
    "m2": [
        ("p₀",              0.0,  1.0,   0.5),
        ("χ₀  [°]",       -90.0, 90.0,   0.0),
        ("RM  [rad/m²]",   -400, 400,   50.0),
        ("σ_RM [rad/m²]",     0, 200,   20.0),
    ],
    "m5": [
        ("p₀",            0.0,  1.0,   0.5),
        ("χ₀  [°]",     -90.0, 90.0,   0.0),
        ("RM  [rad/m²]", -400, 400,   40.0),
        ("ΔRM [rad/m²]",    0, 100,   20.0),
    ],
    "m6": [
        ("p₁",            0.0,  1.0,   0.5),
        ("χ₁  [°]",     -90.0, 90.0,   0.0),
        ("RM₁ [rad/m²]", -400, 400,  -60.0),
        ("ΔRM₁[rad/m²]",    0, 100,   20.0),
        ("p₂",            0.0,  1.0,   0.3),
        ("χ₂  [°]",     -90.0, 90.0,  45.0),
        ("RM₂ [rad/m²]", -400, 400,   80.0),
        ("ΔRM₂[rad/m²]",    0, 100,   20.0),
    ],
    "m7": [
        ("p₀",              0.0,  1.0,   0.5),
        ("χ₀  [°]",       -90.0, 90.0,   0.0),
        ("RM  [rad/m²]",   -400, 400,   50.0),
        ("ΔRM [rad/m²]",      0, 100,   10.0),
        ("σ_RM [rad/m²]",     0, 100,   10.0),
    ],
    "m11": [
        ("p₁",            0.0,  1.0,   0.5),
        ("χ₁  [°]",     -90.0, 90.0,   0.0),
        ("RM₁ [rad/m²]", -400, 400,  -50.0),
        ("p₂",            0.0,  1.0,   0.3),
        ("χ₂  [°]",     -90.0, 90.0,  45.0),
        ("RM₂ [rad/m²]", -400, 400,  100.0),
    ],
    "m3": [
        ("p₁",             0.0,  1.0,   0.5),
        ("χ₁  [°]",      -90.0, 90.0,   0.0),
        ("RM₁ [rad/m²]",  -400, 400,  -50.0),
        ("p₂",             0.0,  1.0,   0.3),
        ("χ₂  [°]",      -90.0, 90.0,  45.0),
        ("RM₂ [rad/m²]",  -400, 400,  100.0),
        ("σ_RM [rad/m²]",    0, 200,    7.0),
    ],
    "m4": [
        ("p₁",              0.0,  1.0,   0.5),
        ("χ₁  [°]",       -90.0, 90.0,   0.0),
        ("RM₁ [rad/m²]",   -400, 400,  -50.0),
        ("σ_RM₁[rad/m²]",     0, 200,    3.0),
        ("p₂",              0.0,  1.0,   0.3),
        ("χ₂  [°]",       -90.0, 90.0,  45.0),
        ("RM₂ [rad/m²]",   -400, 400,  100.0),
        ("σ_RM₂[rad/m²]",     0, 200,    8.0),
    ],
    "m12": [
        ("p₀",               0.0,  1.0,   0.5),
        ("χ₀  [°]",        -90.0, 90.0,   0.0),
        ("RM_scr[rad/m²]",  -400, 400,   50.0),
        ("ΔRM [rad/m²]",       0, 100,   10.0),
        ("σ_int [rad/m²]",     0, 100,    8.0),
        ("σ_fg  [rad/m²]",     0, 100,    5.0),
    ],
    "m111": [
        ("p₁",            0.0,  1.0,   0.5),
        ("χ₁  [°]",     -90.0, 90.0,   0.0),
        ("RM₁ [rad/m²]", -400, 400, -100.0),
        ("p₂",            0.0,  1.0,   0.3),
        ("χ₂  [°]",     -90.0, 90.0,  45.0),
        ("RM₂ [rad/m²]", -400, 400,   50.0),
        ("p₃",            0.0,  1.0,   0.2),
        ("χ₃  [°]",     -90.0, 90.0, -45.0),
        ("RM₃ [rad/m²]", -400, 400,  150.0),
    ],
}

RM_INDICES = {
    "m1":   [2], "m2": [2], "m5": [2], "m6": [2, 6],
    "m7":   [2], "m11": [2, 5], "m3": [2, 5],
    "m4":   [2, 6], "m12": [2], "m111": [2, 5, 8],
}
RM_COLOURS = ["#2ca02c", "#d62728", "#9467bd"]


# ── Physics ───────────────────────────────────────────────────────────────────

def make_lambda2(freqs):
    return (C / freqs) ** 2


def _burn_slab(p0, chi0, RM, dRM, lam2):
    sinc = np.sinc(dRM * lam2 / np.pi)
    return p0 * np.exp(2j * (np.deg2rad(chi0) + (RM + 0.5 * dRM) * lam2)) * sinc


def _internal_factor(dRM, s, lam2):
    S    = 2.0 * s**2 * lam2**2 - 2j * dRM * lam2
    safe = np.where(np.abs(S) < 1e-12, 1.0, (1.0 - np.exp(-S)) / S)
    return safe


def model_P(model, vals, lam2):
    exp, rad = np.exp, np.deg2rad
    if model == "m1":
        p0, c0, RM = vals
        return p0 * exp(2j * (rad(c0) + RM * lam2))
    if model == "m2":
        p0, c0, RM, s = vals
        return p0 * exp(2j * (rad(c0) + RM * lam2)) * exp(-2.0 * s**2 * lam2**2)
    if model == "m5":
        p0, c0, RM, dRM = vals
        return _burn_slab(p0, c0, RM, dRM, lam2)
    if model == "m6":
        p1, c1, RM1, dRM1, p2, c2, RM2, dRM2 = vals
        return _burn_slab(p1, c1, RM1, dRM1, lam2) + _burn_slab(p2, c2, RM2, dRM2, lam2)
    if model == "m7":
        p0, c0, RM, dRM, s = vals
        return p0 * exp(2j * (rad(c0) + RM * lam2)) * _internal_factor(dRM, s, lam2)
    if model == "m11":
        p1, c1, RM1, p2, c2, RM2 = vals
        return (p1 * exp(2j * (rad(c1) + RM1 * lam2))
              + p2 * exp(2j * (rad(c2) + RM2 * lam2)))
    if model == "m3":
        p1, c1, RM1, p2, c2, RM2, s = vals
        return ((p1 * exp(2j * (rad(c1) + RM1 * lam2))
               + p2 * exp(2j * (rad(c2) + RM2 * lam2)))
               * exp(-2.0 * s**2 * lam2**2))
    if model == "m4":
        p1, c1, RM1, s1, p2, c2, RM2, s2 = vals
        return (p1 * exp(2j * (rad(c1) + RM1 * lam2)) * exp(-2.0 * s1**2 * lam2**2)
              + p2 * exp(2j * (rad(c2) + RM2 * lam2)) * exp(-2.0 * s2**2 * lam2**2))
    if model == "m12":
        p0, c0, RM_s, dRM, s_i, s_f = vals
        return (p0 * exp(2j * (rad(c0) + RM_s * lam2))
                * _internal_factor(dRM, s_i, lam2)
                * exp(-2.0 * s_f**2 * lam2**2))
    if model == "m111":
        p1, c1, RM1, p2, c2, RM2, p3, c3, RM3 = vals
        return (p1 * exp(2j * (rad(c1) + RM1 * lam2))
              + p2 * exp(2j * (rad(c2) + RM2 * lam2))
              + p3 * exp(2j * (rad(c3) + RM3 * lam2)))
    raise ValueError(f"Unknown model: {model!r}")


def rm_synthesis(P, lam2, phi):
    return (np.exp(-2j * np.outer(phi, lam2)) @ P) / len(lam2)


def model_P_components(model, vals, lam2):
    """
    Extract individual component contributions for multi-component models.
    Returns list of component polarizations: [P_comp1, P_comp2, ...].
    Single-component models return [P_total].
    """
    exp, rad = np.exp, np.deg2rad

    if model == "m1":
        p0, c0, RM = vals
        P = p0 * exp(2j * (rad(c0) + RM * lam2))
        return [P]

    if model == "m2":
        p0, c0, RM, s = vals
        P = p0 * exp(2j * (rad(c0) + RM * lam2)) * exp(-2.0 * s**2 * lam2**2)
        return [P]

    if model == "m5":
        p0, c0, RM, dRM = vals
        from faraday_explorer import _burn_slab
        P = _burn_slab(p0, c0, RM, dRM, lam2)
        return [P]

    if model == "m6":
        p1, c1, RM1, dRM1, p2, c2, RM2, dRM2 = vals
        from faraday_explorer import _burn_slab
        P1 = _burn_slab(p1, c1, RM1, dRM1, lam2)
        P2 = _burn_slab(p2, c2, RM2, dRM2, lam2)
        return [P1, P2]

    if model == "m7":
        p0, c0, RM, dRM, s = vals
        from faraday_explorer import _internal_factor
        P = p0 * exp(2j * (rad(c0) + RM * lam2)) * _internal_factor(dRM, s, lam2)
        return [P]

    if model == "m11":
        p1, c1, RM1, p2, c2, RM2 = vals
        P1 = p1 * exp(2j * (rad(c1) + RM1 * lam2))
        P2 = p2 * exp(2j * (rad(c2) + RM2 * lam2))
        return [P1, P2]

    if model == "m3":
        p1, c1, RM1, p2, c2, RM2, s = vals
        P1 = p1 * exp(2j * (rad(c1) + RM1 * lam2)) * exp(-2.0 * s**2 * lam2**2)
        P2 = p2 * exp(2j * (rad(c2) + RM2 * lam2)) * exp(-2.0 * s**2 * lam2**2)
        return [P1, P2]

    if model == "m4":
        p1, c1, RM1, s1, p2, c2, RM2, s2 = vals
        P1 = p1 * exp(2j * (rad(c1) + RM1 * lam2)) * exp(-2.0 * s1**2 * lam2**2)
        P2 = p2 * exp(2j * (rad(c2) + RM2 * lam2)) * exp(-2.0 * s2**2 * lam2**2)
        return [P1, P2]

    if model == "m12":
        p0, c0, RM_s, dRM, s_i, s_f = vals
        from faraday_explorer import _internal_factor
        P = (p0 * exp(2j * (rad(c0) + RM_s * lam2))
             * _internal_factor(dRM, s_i, lam2)
             * exp(-2.0 * s_f**2 * lam2**2))
        return [P]

    if model == "m111":
        p1, c1, RM1, p2, c2, RM2, p3, c3, RM3 = vals
        P1 = p1 * exp(2j * (rad(c1) + RM1 * lam2))
        P2 = p2 * exp(2j * (rad(c2) + RM2 * lam2))
        P3 = p3 * exp(2j * (rad(c3) + RM3 * lam2))
        return [P1, P2, P3]

    raise ValueError(f"Unknown model: {model!r}")


def model_fdf_clean(model, vals, phi, lam2):
    """Intrinsic Faraday spectrum — no RMSF convolution.

    Each model component is rendered analytically in Faraday-depth space:
    thin screens → narrow Gaussian spike, dispersed screens → Gaussian in φ,
    Burn slabs → rectangular tophat.  m7 / m12 (complex internal structure)
    fall back to dense uniform λ² sampling (minimal sidelobe approximation).
    """
    dphi = phi[1] - phi[0]

    def spike(p0, rm):
        s = max(dphi * 0.4, 1.0)
        return abs(p0) * np.exp(-0.5 * ((phi - rm) / s) ** 2)

    def gauss_disp(p0, rm, sigma_rm):
        s = np.sqrt(2.0) * abs(sigma_rm) if abs(sigma_rm) > dphi * 0.5 else dphi * 0.5
        return abs(p0) * np.exp(-0.5 * ((phi - rm) / s) ** 2)

    def rect_slab(p0, rm, drm):
        rm1, rm2 = sorted([rm, rm + drm])
        if abs(drm) < dphi:
            return spike(p0, 0.5 * (rm1 + rm2))
        return np.where((phi >= rm1) & (phi <= rm2), abs(p0), 0.0)

    if model == "m1":
        p0, c0, RM = vals
        return spike(p0, RM)
    if model == "m2":
        p0, c0, RM, s = vals
        return gauss_disp(p0, RM, s)
    if model == "m5":
        p0, c0, RM, dRM = vals
        return rect_slab(p0, RM, dRM)
    if model == "m6":
        p1, c1, RM1, dRM1, p2, c2, RM2, dRM2 = vals
        return rect_slab(p1, RM1, dRM1) + rect_slab(p2, RM2, dRM2)
    if model == "m11":
        p1, c1, RM1, p2, c2, RM2 = vals
        return spike(p1, RM1) + spike(p2, RM2)
    if model == "m3":
        p1, c1, RM1, p2, c2, RM2, s = vals
        return gauss_disp(p1, RM1, s) + gauss_disp(p2, RM2, s)
    if model == "m4":
        p1, c1, RM1, s1, p2, c2, RM2, s2 = vals
        return gauss_disp(p1, RM1, s1) + gauss_disp(p2, RM2, s2)
    if model == "m111":
        p1, c1, RM1, p2, c2, RM2, p3, c3, RM3 = vals
        return spike(p1, RM1) + spike(p2, RM2) + spike(p3, RM3)
    # m7, m12: no closed-form FT — approximate with dense uniform λ² grid
    lam2_dense = np.linspace(lam2.min(), lam2.max(), 4000)
    return np.abs(rm_synthesis(model_P(model, vals, lam2_dense), lam2_dense, phi))


def model_fdf_clean_component(model, vals, phi, lam2, comp_idx=0):
    """Intrinsic Faraday spectrum for a single component (no RMSF convolution).

    Args:
        model: model name (e.g., "m1", "m111")
        vals: full parameter list
        phi: Faraday depth array
        lam2: wavelength-squared array
        comp_idx: which component to extract (0, 1, 2, etc.)

    Returns:
        Amplitude array for just that component
    """
    dphi = phi[1] - phi[0]

    def spike(p0, rm):
        s = max(dphi * 0.4, 1.0)
        return abs(p0) * np.exp(-0.5 * ((phi - rm) / s) ** 2)

    def gauss_disp(p0, rm, sigma_rm):
        s = np.sqrt(2.0) * abs(sigma_rm) if abs(sigma_rm) > dphi * 0.5 else dphi * 0.5
        return abs(p0) * np.exp(-0.5 * ((phi - rm) / s) ** 2)

    def rect_slab(p0, rm, drm):
        rm1, rm2 = sorted([rm, rm + drm])
        if abs(drm) < dphi:
            return spike(p0, 0.5 * (rm1 + rm2))
        return np.where((phi >= rm1) & (phi <= rm2), abs(p0), 0.0)

    # Single-component models always return component 0
    if model == "m1":
        if comp_idx != 0:
            return np.zeros_like(phi)
        p0, c0, RM = vals
        return spike(p0, RM)

    if model == "m2":
        if comp_idx != 0:
            return np.zeros_like(phi)
        p0, c0, RM, s = vals
        return gauss_disp(p0, RM, s)

    if model == "m5":
        if comp_idx != 0:
            return np.zeros_like(phi)
        p0, c0, RM, dRM = vals
        return rect_slab(p0, RM, dRM)

    if model == "m6":
        p1, c1, RM1, dRM1, p2, c2, RM2, dRM2 = vals
        if comp_idx == 0:
            return rect_slab(p1, RM1, dRM1)
        elif comp_idx == 1:
            return rect_slab(p2, RM2, dRM2)
        else:
            return np.zeros_like(phi)

    if model == "m7":
        if comp_idx != 0:
            return np.zeros_like(phi)
        p0, c0, RM, dRM, s = vals
        from faraday_explorer import _internal_factor
        lam2_dense = np.linspace(lam2.min(), lam2.max(), 4000)
        P = model_P(model, vals, lam2_dense)
        return np.abs(rm_synthesis(P, lam2_dense, phi))

    if model == "m11":
        p1, c1, RM1, p2, c2, RM2 = vals
        if comp_idx == 0:
            return spike(p1, RM1)
        elif comp_idx == 1:
            return spike(p2, RM2)
        else:
            return np.zeros_like(phi)

    if model == "m3":
        p1, c1, RM1, p2, c2, RM2, s = vals
        if comp_idx == 0:
            return gauss_disp(p1, RM1, s)
        elif comp_idx == 1:
            return gauss_disp(p2, RM2, s)
        else:
            return np.zeros_like(phi)

    if model == "m4":
        p1, c1, RM1, s1, p2, c2, RM2, s2 = vals
        if comp_idx == 0:
            return gauss_disp(p1, RM1, s1)
        elif comp_idx == 1:
            return gauss_disp(p2, RM2, s2)
        else:
            return np.zeros_like(phi)

    if model == "m12":
        if comp_idx != 0:
            return np.zeros_like(phi)
        p0, c0, RM_s, dRM, s_i, s_f = vals
        from faraday_explorer import _internal_factor
        lam2_dense = np.linspace(lam2.min(), lam2.max(), 4000)
        P = model_P(model, vals, lam2_dense)
        return np.abs(rm_synthesis(P, lam2_dense, phi))

    if model == "m111":
        p1, c1, RM1, p2, c2, RM2, p3, c3, RM3 = vals
        if comp_idx == 0:
            return spike(p1, RM1)
        elif comp_idx == 1:
            return spike(p2, RM2)
        elif comp_idx == 2:
            return spike(p3, RM3)
        else:
            return np.zeros_like(phi)

    return np.zeros_like(phi)


def _gaussian_restore(intrinsic_amp, phi, rmsf):
    """Convolve an intrinsic Faraday spectrum with a Gaussian restoring beam.

    The Gaussian FWHM is measured from the main lobe of the real RMSF (first
    zero-crossing on each side of the peak), so the convolved result traces the
    RMSF main peak shape without any sidelobes.
    """
    dphi = abs(phi[1] - phi[0])
    peak_idx = int(np.argmax(rmsf))

    # Left half-width at half-maximum (in bins)
    left = rmsf[:peak_idx][::-1]
    l_bins = next((i for i, v in enumerate(left) if v < 0.5), max(1, len(left) - 1))
    # Right half-width at half-maximum (in bins)
    right = rmsf[peak_idx:]
    r_bins = next((i for i, v in enumerate(right) if v < 0.5), max(1, len(right) - 1))

    fwhm  = (l_bins + r_bins) * dphi
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    if sigma < dphi * 0.5:
        return intrinsic_amp          # degenerate coverage — no-op

    half_w = int(np.ceil(3.5 * sigma / dphi))
    k      = np.arange(-half_w, half_w + 1) * dphi
    kernel = np.exp(-0.5 * (k / sigma) ** 2)
    kernel /= kernel.sum()
    return np.convolve(intrinsic_amp, kernel, mode='same')


# ── Theme management ──────────────────────────────────────────────────────────

class Theme:
    """Color scheme definitions for dark/light modes."""

    DARK = {
        "name": "Dark",
        "param_highlight_bg": "#2a4a3a",      # Dark teal
        "param_highlight_label": "#a0d0c0",   # Light teal text
        "slider_groove": "#1e5c46",            # Darker teal for groove
        "slider_handle": "#00c896",            # Bright teal for handle
        "stylesheet": """
            QMainWindow, QDialog, QWidget { background-color: #1e1e1e; color: #e0e0e0; }
            QMenuBar { background-color: #252525; color: #e0e0e0; border-bottom: 1px solid #333; }
            QMenuBar::item:selected { background-color: #3a3a3a; }
            QMenu { background-color: #252525; color: #e0e0e0; border: 1px solid #333; }
            QMenu::item:selected { background-color: #3a3a3a; }
            QToolBar { background-color: #252525; border: none; }
            QDockWidget { color: #e0e0e0; }
            QDockWidget::title { background-color: #252525; padding: 3px; }
            QLabel { color: #e0e0e0; }
            QLineEdit, QTextEdit { background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #444; }
            QComboBox { background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #444; }
            QComboBox::drop-down { border: none; }
            QPushButton { background-color: #0d47a1; color: #fff; border: 1px solid #0d47a1; padding: 4px; border-radius: 3px; }
            QPushButton:hover { background-color: #1565c0; }
            QPushButton:pressed { background-color: #0d3f8f; }
            QSpinBox, QDoubleSpinBox { background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #444; }
            QSlider::groove:horizontal { background-color: #444; border-radius: 2px; }
            QSlider::handle:horizontal { background-color: #0d47a1; border-radius: 5px; width: 12px; }
            QGroupBox { color: #e0e0e0; border: 1px solid #444; border-radius: 3px; margin-top: 8px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
            QScrollArea { background-color: #1e1e1e; }
            QFrame { background-color: #1e1e1e; color: #e0e0e0; }
            QStatusBar { background-color: #252525; color: #e0e0e0; border-top: 1px solid #333; }
        """
    }

    LIGHT = {
        "name": "Light",
        "param_highlight_bg": "#e8f5e9",      # Light green
        "param_highlight_label": "#1b5e20",   # Dark green text
        "slider_groove": "#c8e6c9",            # Medium green for groove
        "slider_handle": "#2e7d32",            # Dark green for handle
        "stylesheet": """
            QMainWindow, QDialog, QWidget { background-color: #f5f5f5; color: #212121; }
            QMenuBar { background-color: #fafafa; color: #212121; border-bottom: 1px solid #e0e0e0; }
            QMenuBar::item:selected { background-color: #eeeeee; }
            QMenu { background-color: #fafafa; color: #212121; border: 1px solid #e0e0e0; }
            QMenu::item:selected { background-color: #eeeeee; }
            QToolBar { background-color: #fafafa; border: none; }
            QDockWidget { color: #212121; }
            QDockWidget::title { background-color: #fafafa; padding: 3px; }
            QLabel { color: #212121; }
            QLineEdit, QTextEdit { background-color: #ffffff; color: #212121; border: 1px solid #bdbdbd; }
            QComboBox { background-color: #ffffff; color: #212121; border: 1px solid #bdbdbd; }
            QComboBox::drop-down { border: none; }
            QPushButton { background-color: #1976d2; color: #fff; border: 1px solid #1976d2; padding: 4px; border-radius: 3px; }
            QPushButton:hover { background-color: #1565c0; }
            QPushButton:pressed { background-color: #1155cc; }
            QSpinBox, QDoubleSpinBox { background-color: #ffffff; color: #212121; border: 1px solid #bdbdbd; }
            QSlider::groove:horizontal { background-color: #bdbdbd; border-radius: 2px; }
            QSlider::handle:horizontal { background-color: #1976d2; border-radius: 5px; width: 12px; }
            QGroupBox { color: #212121; border: 1px solid #bdbdbd; border-radius: 3px; margin-top: 8px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
            QScrollArea { background-color: #f5f5f5; }
            QFrame { background-color: #f5f5f5; color: #212121; }
            QStatusBar { background-color: #fafafa; color: #212121; border-top: 1px solid #e0e0e0; }
        """
    }

    @staticmethod
    def get_theme(name="dark"):
        """Get theme by name."""
        return Theme.DARK if name.lower() == "dark" else Theme.LIGHT


# ── CompactNavToolbar: matplotlib toolbar with smaller icons ───────────────────

class CompactNavToolbar(NavToolbar):
    """NavToolbar with smaller icons for better space utilization."""

    def __init__(self, canvas, parent=None):
        super().__init__(canvas, parent)
        from PyQt5.QtCore import QSize
        # Use standard 22x22 icon size (looks correct on macOS)
        self.setIconSize(QSize(22, 22))
        # Reduce toolbar height slightly
        self.setFixedHeight(28)


# ── ParamWidget: slider + spinbox + editable min/max ─────────────────────────

class ParamWidget(QFrame):
    valueChanged = pyqtSignal()

    def __init__(self, label="", vmin=0.0, vmax=1.0, vinit=0.5, parent=None):
        super().__init__(parent)
        self._vmin = vmin
        self._vmax = vmax
        self._guard = False
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        g = QGridLayout(self)
        g.setContentsMargins(6, 3, 6, 3)
        g.setHorizontalSpacing(4)
        g.setVerticalSpacing(2)

        self._lbl = QLabel(f"<b>{label}</b>")
        self._lbl.setMinimumWidth(110)

        self.spin = QDoubleSpinBox()
        self.spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))  # Use period as decimal
        self.spin.setDecimals(4)
        self.spin.setRange(vmin, vmax)
        self.spin.setValue(vinit)
        self.spin.setSingleStep(max(1e-4, (vmax - vmin) / 200))
        self.spin.setFixedWidth(105)
        self.spin.setAlignment(Qt.AlignRight)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 2000)
        self.slider.setValue(self._to_sl(vinit))
        self.slider.setToolTip("Drag to sweep · use the spinbox for precise values")

        self.min_edit = QLineEdit(f"{vmin:.5g}")
        self.max_edit = QLineEdit(f"{vmax:.5g}")
        for e in (self.min_edit, self.max_edit):
            e.setFixedWidth(70)
            e.setAlignment(Qt.AlignRight)
            f = e.font(); f.setPointSize(8); e.setFont(f)

        # Row 0: label | spinbox
        g.addWidget(self._lbl,    0, 0)
        g.addWidget(self.spin,    0, 2)
        # Row 1: min | slider | max
        g.addWidget(self.min_edit, 1, 0)
        g.addWidget(self.slider,   1, 1)
        g.addWidget(self.max_edit, 1, 2)
        g.setColumnStretch(1, 1)

        self.slider.valueChanged.connect(self._sl_changed)
        self.spin.valueChanged.connect(self._spin_changed)
        self.min_edit.returnPressed.connect(self._apply_min)
        self.max_edit.returnPressed.connect(self._apply_max)

        # Convert commas to periods in spinbox input
        self.spin.lineEdit().textChanged.connect(self._convert_comma_to_period)

    # ── internal helpers ──────────────────────────────────────────────────────
    def _to_sl(self, v):
        r = self._vmax - self._vmin
        return int((v - self._vmin) / r * 2000) if r else 0

    def _from_sl(self, sv):
        return self._vmin + sv / 2000 * (self._vmax - self._vmin)

    def _sl_changed(self, sv):
        if self._guard: return
        self._guard = True
        self.spin.setValue(self._from_sl(sv))
        self._guard = False
        self.valueChanged.emit()

    def _spin_changed(self, v):
        if self._guard: return
        self._guard = True
        self.slider.setValue(self._to_sl(v))
        self._guard = False
        self.valueChanged.emit()

    def _convert_comma_to_period(self, text):
        """Convert commas to periods in spinbox input for user convenience."""
        if "," in text:
            cursor_pos = self.spin.lineEdit().cursorPosition()
            new_text = text.replace(",", ".")
            self.spin.lineEdit().blockSignals(True)
            self.spin.lineEdit().setText(new_text)
            self.spin.lineEdit().setCursorPosition(cursor_pos)
            self.spin.lineEdit().blockSignals(False)

    def _apply_min(self):
        try:
            nv = float(self.min_edit.text())
            if nv < self._vmax:
                self._vmin = nv
                self.spin.setRange(self._vmin, self._vmax)
                self.spin.setSingleStep(max(1e-4, (self._vmax - self._vmin) / 200))
                self.slider.setValue(self._to_sl(self.spin.value()))
        except ValueError:
            self.min_edit.setText(f"{self._vmin:.5g}")

    def _apply_max(self):
        try:
            nv = float(self.max_edit.text())
            if nv > self._vmin:
                self._vmax = nv
                self.spin.setRange(self._vmin, self._vmax)
                self.spin.setSingleStep(max(1e-4, (self._vmax - self._vmin) / 200))
                self.slider.setValue(self._to_sl(self.spin.value()))
        except ValueError:
            self.max_edit.setText(f"{self._vmax:.5g}")

    # ── public API ────────────────────────────────────────────────────────────
    def value(self):
        return self.spin.value()

    def set_highlighted(self, highlighted=True, theme="dark"):
        """Highlight this parameter widget when selected/editing."""
        if highlighted:
            t = Theme.get_theme(theme)
            self.setStyleSheet(
                f"QFrame {{ background-color: {t['param_highlight_bg']}; border-radius: 3px; }}"
                f"QLabel {{ font-weight: bold; color: {t['param_highlight_label']}; }}"
            )
            self.slider.setStyleSheet(
                f"QSlider::groove:horizontal {{ background-color: {t['slider_groove']}; height: 6px; }}"
                f"QSlider::handle:horizontal {{ background-color: {t['slider_handle']}; "
                f"border: 1px solid {t['slider_handle']}; width: 12px; margin: -3px 0; border-radius: 6px; }}"
            )
        else:
            self.setStyleSheet("")
            self.slider.setStyleSheet("")

    def reconfigure(self, label, vmin, vmax, vinit):
        self._guard = True
        self._vmin, self._vmax = vmin, vmax
        self._lbl.setText(f"<b>{label}</b>")
        self.spin.setRange(vmin, vmax)
        self.spin.setSingleStep(max(1e-4, (vmax - vmin) / 200))
        self.spin.setValue(vinit)
        self.slider.setValue(self._to_sl(vinit))
        self.min_edit.setText(f"{vmin:.5g}")
        self.max_edit.setText(f"{vmax:.5g}")
        self._guard = False


# ── ApertureEditDialog ────────────────────────────────────────────────────────

class ApertureEditDialog(QDialog):
    """Lets the user tweak an already-drawn aperture's semi-axes and PA.

    If pix_scale_ds (arcsec per downsampled pixel) is provided, the dialog
    defaults to arcsec and shows a units dropdown to switch to pixels.
    """

    def __init__(self, a_px, b_px, pa_deg, pix_scale_ds=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Aperture")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(300)

        self._ps   = pix_scale_ds       # arcsec / ds-px, or None
        self._a_px = a_px               # stored in px for unit conversion
        self._b_px = b_px

        layout = QVBoxLayout(self)

        # ── Units selector ────────────────────────────────────────────────────
        units_row = QHBoxLayout()
        units_row.addWidget(QLabel("Units:"))
        self._units = QComboBox()
        if pix_scale_ds:
            self._units.addItem('arcsec (")')
            self._units.addItem("pixels (ds-px)")
        else:
            self._units.addItem("pixels (ds-px)")
        units_row.addStretch()
        units_row.addWidget(self._units)
        layout.addLayout(units_row)

        # ── Axes spinboxes ────────────────────────────────────────────────────
        form = QFormLayout()
        layout.addLayout(form)

        self._a_spin = QDoubleSpinBox()
        self._a_spin.setRange(0.01, 99999)
        self._a_spin.setDecimals(2)
        self._a_spin.setSingleStep(0.5)
        self._a_spin.setToolTip("Semi-major axis length")
        form.addRow("Semi-major (a):", self._a_spin)

        self._b_spin = QDoubleSpinBox()
        self._b_spin.setRange(0.01, 99999)
        self._b_spin.setDecimals(2)
        self._b_spin.setSingleStep(0.5)
        self._b_spin.setToolTip("Semi-minor axis length")
        form.addRow("Semi-minor (b):", self._b_spin)

        self._pa_spin = QDoubleSpinBox()
        self._pa_spin.setRange(0, 360)
        self._pa_spin.setDecimals(1)
        self._pa_spin.setSingleStep(5.0)
        self._pa_spin.setWrapping(True)
        self._pa_spin.setValue(round(pa_deg % 360, 1))
        self._pa_spin.setSuffix("°")
        self._pa_spin.setToolTip(
            "Counter-clockwise rotation of the semi-major axis from the +x (East) direction")
        form.addRow("Position angle:", self._pa_spin)

        # Initialise axis values in the default unit
        self._refresh_spinboxes()
        # Connect after initial population to avoid spurious conversions
        self._units.currentIndexChanged.connect(self._on_units_changed)

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _in_arcsec(self):
        return self._ps is not None and self._units.currentIndex() == 0

    def _refresh_spinboxes(self):
        """Populate spinboxes from stored _a_px/_b_px in the current unit."""
        if self._in_arcsec():
            a_disp = self._a_px * self._ps
            b_disp = self._b_px * self._ps
            suffix = '"'
        else:
            a_disp = self._a_px
            b_disp = self._b_px
            suffix = " ds-px"
        for spin, val in ((self._a_spin, a_disp), (self._b_spin, b_disp)):
            spin.blockSignals(True)
            spin.setValue(round(val, 2))
            spin.setSuffix(suffix)
            spin.blockSignals(False)

    def _on_units_changed(self, _idx):
        # Snapshot current displayed values back to px before switching
        if self._in_arcsec():
            # We just switched TO arcsec; previous unit was px
            self._a_px = self._a_spin.value()
            self._b_px = self._b_spin.value()
        else:
            # We just switched TO px; previous unit was arcsec
            if self._ps:
                self._a_px = self._a_spin.value() / self._ps
                self._b_px = self._b_spin.value() / self._ps
        self._refresh_spinboxes()

    def values(self):
        """Return (a_px, b_px, pa_deg) always in downsampled pixels."""
        if self._in_arcsec() and self._ps:
            return (self._a_spin.value() / self._ps,
                    self._b_spin.value() / self._ps,
                    self._pa_spin.value())
        return self._a_spin.value(), self._b_spin.value(), self._pa_spin.value()


class CoordinateApertureDialog(QDialog):
    """Input aperture by coordinates (RA/Dec, decimal degrees, or pixel).

    Live-updates aperture position and size via sliders on the map preview.
    Pans the map to keep the aperture centered in view.
    """

    aperture_set = pyqtSignal(np.ndarray, float, float, float, float, float)  # mask,cx,cy,a,b,pa

    def __init__(self, wcs_2d=None, map_canvas=None, pix_scale_ds=None,
                 map_shape=None, map_step=1, parent=None):
        """
        wcs_2d: astropy.wcs.WCS object for the 2D map (for RA/Dec ↔ pixel conversion)
        map_canvas: MapCanvas instance to update live
        pix_scale_ds: arcsec per downsampled pixel
        map_shape: (ny, nx) for downsampled map
        map_step: downsampling factor (1 = native, 24 = 24x downsampled)
        """
        super().__init__(parent)
        self.setWindowTitle("Aperture by Coordinates")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(450)
        self.setMinimumHeight(600)

        self.wcs_2d = wcs_2d
        self.map_canvas = map_canvas
        self._ps = pix_scale_ds  # arcsec / ds-px
        self.map_shape = map_shape  # (ny, nx)
        self.map_step = map_step

        self.cx_px = None  # center in downsampled pixels
        self.cy_px = None
        self.a_px = 10.0   # semi-major in ds-px
        self.b_px = 5.0    # semi-minor in ds-px
        self.pa_deg = 0.0  # position angle

        self._build_ui()
        self._update_preview()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Coordinate input section ──────────────────────────────────────
        coord_grp = QGroupBox("Aperture Center Position")
        coord_form = QFormLayout(coord_grp)

        # Coordinate format selector
        self._coord_format = QComboBox()
        self._coord_format.addItem("RA/Dec (HH:MM:SS ±DD:MM:SS)")
        self._coord_format.addItem("Decimal degrees (°)")
        self._coord_format.addItem("Pixel coordinates (ds-px)")
        self._coord_format.currentIndexChanged.connect(self._on_format_changed)
        coord_form.addRow("Format:", self._coord_format)

        # RA field
        self._ra_input = QLineEdit()
        self._ra_input.setPlaceholderText("RA or RA/x in selected format")
        self._ra_input.setToolTip("RA in selected format (HH:MM:SS, decimal degrees, or pixel)")
        self._ra_input.textChanged.connect(self._on_coords_changed)
        coord_form.addRow("RA / X:", self._ra_input)

        # Dec field
        self._dec_input = QLineEdit()
        self._dec_input.setPlaceholderText("Dec or Dec/y in selected format")
        self._dec_input.setToolTip("Dec in selected format (±DD:MM:SS, decimal degrees, or pixel)")
        self._dec_input.textChanged.connect(self._on_coords_changed)
        coord_form.addRow("Dec / Y:", self._dec_input)

        layout.addWidget(coord_grp)

        # ── Aperture dimensions section ──────────────────────────────────
        apert_grp = QGroupBox("Aperture Dimensions")
        apert_form = QFormLayout(apert_grp)

        # Units selector
        self._units = QComboBox()
        if self._ps:
            self._units.addItem('arcsec (")')
            self._units.addItem("pixels (ds-px)")
        else:
            self._units.addItem("pixels (ds-px)")
        self._units.currentIndexChanged.connect(self._on_units_changed)
        apert_form.addRow("Units:", self._units)

        # Semi-major slider
        self._a_slider = QSlider(Qt.Horizontal)
        self._a_slider.setRange(1, 500)
        self._a_slider.setValue(int(self.a_px))
        self._a_slider.setTickPosition(QSlider.TicksBelow)
        self._a_slider.setTickInterval(50)
        self._a_slider.sliderMoved.connect(self._on_slider_moved)
        self._a_slider.valueChanged.connect(self._on_slider_moved)

        self._a_label = QLabel()
        a_row = QHBoxLayout()
        a_row.addWidget(QLabel("Semi-major (a):"))
        a_row.addWidget(self._a_slider)
        a_row.addWidget(self._a_label)
        a_row.setStretchFactor(self._a_slider, 1)
        apert_form.addRow(a_row)

        # Semi-minor slider
        self._b_slider = QSlider(Qt.Horizontal)
        self._b_slider.setRange(1, 500)
        self._b_slider.setValue(int(self.b_px))
        self._b_slider.setTickPosition(QSlider.TicksBelow)
        self._b_slider.setTickInterval(50)
        self._b_slider.sliderMoved.connect(self._on_slider_moved)
        self._b_slider.valueChanged.connect(self._on_slider_moved)

        self._b_label = QLabel()
        b_row = QHBoxLayout()
        b_row.addWidget(QLabel("Semi-minor (b):"))
        b_row.addWidget(self._b_slider)
        b_row.addWidget(self._b_label)
        b_row.setStretchFactor(self._b_slider, 1)
        apert_form.addRow(b_row)

        # Position angle slider
        self._pa_slider = QSlider(Qt.Horizontal)
        self._pa_slider.setRange(0, 360)
        self._pa_slider.setValue(0)
        self._pa_slider.setTickPosition(QSlider.TicksBelow)
        self._pa_slider.setTickInterval(30)
        self._pa_slider.sliderMoved.connect(self._on_slider_moved)
        self._pa_slider.valueChanged.connect(self._on_slider_moved)

        self._pa_label = QLabel("0.0°")
        pa_row = QHBoxLayout()
        pa_row.addWidget(QLabel("Position angle:"))
        pa_row.addWidget(self._pa_slider)
        pa_row.addWidget(self._pa_label)
        pa_row.setStretchFactor(self._pa_slider, 1)
        apert_form.addRow(pa_row)

        layout.addWidget(apert_grp)

        # ── Status/error display ──────────────────────────────────────────
        self._status_label = QLabel()
        self._status_label.setStyleSheet(
            "color: #d32f2f; font-weight: bold; padding: 4px; "
            "background-color: rgba(211, 47, 47, 0.1); border-radius: 3px;"
        )
        self._status_label.setVisible(False)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # ── Buttons ───────────────────────────────────────────────────────
        btns = QHBoxLayout()
        accept_btn = QPushButton("Accept")
        accept_btn.setDefault(True)
        accept_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(accept_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

        self._update_labels()

    def _in_arcsec(self):
        return self._ps is not None and self._units.currentIndex() == 0

    def _update_labels(self):
        """Update slider value labels with current units."""
        if self._in_arcsec():
            a_val = self.a_px * self._ps
            b_val = self.b_px * self._ps
            suffix = '"'
        else:
            a_val = self.a_px
            b_val = self.b_px
            suffix = " ds-px"
        self._a_label.setText(f"{a_val:.2f}{suffix}")
        self._b_label.setText(f"{b_val:.2f}{suffix}")
        self._pa_label.setText(f"{self.pa_deg:.1f}°")

    def _on_format_changed(self):
        self._ra_input.clear()
        self._dec_input.clear()

    def _on_units_changed(self):
        self._update_labels()
        # Adjust sliders if switching to/from arcsec
        if self._in_arcsec() and self._ps:
            # Now in arcsec; update slider ranges to make sense in arcsec
            self._a_slider.blockSignals(True)
            self._b_slider.blockSignals(True)
            max_arcsec = 500 * self._ps
            self._a_slider.setRange(1, int(max_arcsec))
            self._a_slider.setValue(int(self.a_px * self._ps))
            self._b_slider.setRange(1, int(max_arcsec))
            self._b_slider.setValue(int(self.b_px * self._ps))
            self._a_slider.blockSignals(False)
            self._b_slider.blockSignals(False)
        else:
            # Back to pixels
            self._a_slider.blockSignals(True)
            self._b_slider.blockSignals(True)
            self._a_slider.setRange(1, 500)
            self._a_slider.setValue(int(self.a_px))
            self._b_slider.setRange(1, 500)
            self._b_slider.setValue(int(self.b_px))
            self._a_slider.blockSignals(False)
            self._b_slider.blockSignals(False)

    def _on_coords_changed(self):
        """Parse coordinate input and update preview."""
        fmt = self._coord_format.currentIndex()
        ra_str = self._ra_input.text().strip()
        dec_str = self._dec_input.text().strip()

        if not ra_str or not dec_str:
            self._status_label.setVisible(False)
            return

        try:
            if fmt == 0:  # RA/Dec HH:MM:SS
                self.cx_px, self.cy_px = self._parse_radec(ra_str, dec_str)
            elif fmt == 1:  # Decimal degrees
                self.cx_px, self.cy_px = self._parse_degrees(ra_str, dec_str)
            else:  # Pixels
                self.cx_px, self.cy_px = self._parse_pixels(ra_str, dec_str)

            if self.cx_px is not None and self.cy_px is not None:
                self._status_label.setVisible(False)
                self._update_preview()
        except Exception as e:
            self._status_label.setText(f"⚠ Error: {str(e)}")
            self._status_label.setVisible(True)

    def _on_slider_moved(self):
        """Update aperture dimensions from sliders and refresh preview."""
        if self._in_arcsec() and self._ps:
            self.a_px = self._a_slider.value() / self._ps
            self.b_px = self._b_slider.value() / self._ps
        else:
            self.a_px = float(self._a_slider.value())
            self.b_px = float(self._b_slider.value())
        self.pa_deg = float(self._pa_slider.value())

        self._update_labels()
        self._update_preview()

    def _parse_radec(self, ra_str, dec_str):
        """Parse RA (HH:MM:SS) and Dec (±DD:MM:SS) to pixel coords via WCS."""
        from astropy.coordinates import Angle
        import astropy.units as u

        if not self.wcs_2d:
            raise ValueError("No WCS available for RA/Dec parsing")

        try:
            ra_angle = Angle(ra_str, unit=u.hour)
            dec_angle = Angle(dec_str, unit=u.degree)
            ra_deg = ra_angle.deg
            dec_deg = dec_angle.deg

            x_px, y_px = self.wcs_2d.all_world2pix(ra_deg, dec_deg, 0)
            x_ds = x_px / self.map_step
            y_ds = y_px / self.map_step
            return float(x_ds), float(y_ds)
        except Exception as e:
            raise ValueError(
                f"Invalid RA/Dec format. Expected HH:MM:SS.S ±DD:MM:SS.S, got '{ra_str}' / '{dec_str}'"
            )

    def _parse_degrees(self, ra_str, dec_str):
        """Parse RA and Dec as decimal degrees to pixel coords via WCS."""
        if not self.wcs_2d:
            raise ValueError("No WCS available for degree parsing")

        try:
            ra_deg = float(ra_str)
            dec_deg = float(dec_str)

            x_px, y_px = self.wcs_2d.all_world2pix(ra_deg, dec_deg, 0)
            x_ds = x_px / self.map_step
            y_ds = y_px / self.map_step
            return float(x_ds), float(y_ds)
        except ValueError as e:
            raise ValueError(f"Failed to parse degrees: {e}")

    def _parse_pixels(self, x_str, y_str):
        """Parse direct pixel coordinates."""
        try:
            x = float(x_str)
            y = float(y_str)
            return float(x), float(y)
        except ValueError as e:
            raise ValueError(f"Failed to parse pixels: {e}")

    def _update_preview(self):
        """Update the aperture preview on the map and pan to center."""
        if self.map_canvas is None or self.cx_px is None or self.cy_px is None:
            return

        # Pan map to center on aperture
        ax = self.map_canvas.ax
        hw = (ax.get_xlim()[1] - ax.get_xlim()[0]) / 2
        hh = (ax.get_ylim()[1] - ax.get_ylim()[0]) / 2
        ax.set_xlim(self.cx_px - hw, self.cx_px + hw)
        ax.set_ylim(self.cy_px - hh, self.cy_px + hh)

        # Remove old patch if exists
        if hasattr(self.map_canvas, '_patch') and self.map_canvas._patch is not None:
            self.map_canvas._patch.remove()

        # Draw new aperture patch
        patch = mpatches.Ellipse(
            (self.cx_px, self.cy_px), width=2*self.a_px, height=2*self.b_px,
            angle=self.pa_deg, fill=False, edgecolor="lime", lw=2.0,
            ls=":", zorder=5)
        ax.add_patch(patch)
        self.map_canvas._patch = patch
        self.map_canvas.draw_idle()

    def values(self):
        """Return (cx_px, cy_px, a_px, b_px, pa_deg) in downsampled pixels."""
        return self.cx_px, self.cy_px, self.a_px, self.b_px, self.pa_deg


# ── MapCanvas: FDF peak map with aperture drawing ────────────────────────────

class MapCanvas(FigureCanvas):
    aperture_ready   = pyqtSignal(np.ndarray, float, float, float, float, float)  # mask,cx,cy,a,b,pa
    aperture_cleared = pyqtSignal()

    _MIN_DRAG_PX = 4

    def __init__(self, peak_map, parent=None):
        self.fig = Figure(facecolor="#111111")
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        ax = self.fig.add_axes([0.07, 0.05, 0.90, 0.90])
        vlo = float(np.nanpercentile(peak_map, 2.0))
        vhi = float(np.nanpercentile(peak_map, 99.5))
        ax.imshow(peak_map, origin="lower", aspect="equal",
                  cmap="inferno", vmin=vlo, vmax=vhi)
        ax.set_title("Peak |FDF|  [Jy/beam/RMSF]",
                     fontsize=9, color="white", pad=4)
        ax.set_xlabel("RA pixel (downsampled)", fontsize=7, color="white")
        ax.set_ylabel("Dec pixel (downsampled)", fontsize=7, color="white")
        ax.tick_params(colors="white", labelsize=6)
        for sp in ax.spines.values():
            sp.set_edgecolor("white")
        self.ax = ax
        self._ny, self._nx = peak_map.shape

        # ── Interaction state ─────────────────────────────────────────────────
        # States: idle | panning | aperture_wait | aperture_drawing | aperture_dragging
        self._state      = "idle"
        self._pan_ref    = None   # (canvas_x, canvas_y) at pan start
        self._xlim0      = None   # axes limits at pan start
        self._ylim0      = None
        self._press_xy   = None   # canvas pos at last button-press (for drag threshold)
        self._apert_cx          = None
        self._apert_cy          = None
        self._apert_pa          = 0.0   # PA of finalised aperture (degrees)
        self._patch             = None
        self._marker            = None
        self._aperture_finalised = False
        self._aperture_locked   = False  # if True, aperture cannot be moved
        self._pix_scale_ds      = None  # arcsec / downsampled-pixel (set by MainWindow)

        self.mpl_connect("button_press_event",   self._on_press)
        self.mpl_connect("motion_notify_event",  self._on_motion)
        self.mpl_connect("button_release_event", self._on_release)
        self.mpl_connect("scroll_event",         self._on_scroll)

    def set_pixel_scale(self, pix_scale_ds):
        """Store arcsec-per-downsampled-pixel for the aperture edit dialog."""
        self._pix_scale_ds = pix_scale_ds

    # ── Scroll zoom ───────────────────────────────────────────────────────────

    def _on_scroll(self, ev):
        if ev.inaxes != self.ax:
            return
        factor = 0.85 if ev.button == "up" else 1.0 / 0.85
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        xc, yc = ev.xdata, ev.ydata
        self.ax.set_xlim([xc + (x - xc) * factor for x in xlim])
        self.ax.set_ylim([yc + (y - yc) * factor for y in ylim])
        self.draw_idle()

    # ── Press ─────────────────────────────────────────────────────────────────

    def _on_press(self, ev):
        if ev.inaxes != self.ax:
            return

        if ev.button == 2:                          # middle-click → centre view
            self._centre_view(ev.xdata, ev.ydata)
            return

        if ev.button == 1:
            self._press_xy = (ev.x, ev.y)
            if ev.dblclick:
                if self._aperture_finalised:
                    if self._inside_aperture(ev.xdata, ev.ydata):
                        # Double-click inside existing aperture → edit it
                        self._open_aperture_edit()
                    else:
                        # Double-click outside → clear
                        self._clear_aperture()
                    return
                # Place centre marker; button still held → enter drawing immediately
                self._place_centre(ev.xdata, ev.ydata)
                self._state = "aperture_drawing"
            elif self._aperture_finalised and not self._aperture_locked and self._inside_aperture(ev.xdata, ev.ydata):
                # Single-click inside unlocked aperture → drag to move it
                self._state = "aperture_dragging"
                self._pan_ref = (ev.xdata, ev.ydata)
                self.setCursor(Qt.ClosedHandCursor)
            elif self._state == "aperture_wait":
                # Single press after centre set → start drawing
                self._state = "aperture_drawing"
            else:
                # Default: start pan
                self._pan_ref = (ev.x, ev.y)
                self._xlim0   = self.ax.get_xlim()
                self._ylim0   = self.ax.get_ylim()
                self._state   = "panning"
                self.setCursor(Qt.ClosedHandCursor)

    # ── Motion ────────────────────────────────────────────────────────────────

    def _on_motion(self, ev):
        if self._state == "panning" and ev.x is not None:
            self._do_pan(ev.x, ev.y)
        elif self._state == "aperture_drawing" and ev.inaxes == self.ax:
            self._update_ellipse(ev.xdata, ev.ydata)
        elif self._state == "aperture_dragging" and ev.inaxes == self.ax and self._pan_ref is not None:
            self._drag_aperture(ev.xdata, ev.ydata)

    # ── Release ───────────────────────────────────────────────────────────────

    def _on_release(self, ev):
        if ev.button == 1:
            if self._state == "panning":
                self._state = "idle"
                self.unsetCursor()

            elif self._state == "aperture_dragging":
                self._state = "idle"
                self.unsetCursor()
                self._emit_aperture_from_patch()

            elif self._state == "aperture_drawing":
                # Check if mouse actually moved (distinguish click from drag)
                px, py = self._press_xy or (ev.x, ev.y)
                moved  = ((ev.x - px)**2 + (ev.y - py)**2) ** 0.5

                if moved < self._MIN_DRAG_PX or ev.inaxes != self.ax:
                    # No meaningful drag — keep centre set, wait for a drag
                    self._state = "aperture_wait"
                else:
                    self._finalise_aperture(ev.xdata, ev.ydata)
                    self._state = "idle"

    # ── Pan helpers ───────────────────────────────────────────────────────────

    def _do_pan(self, cx, cy):
        if self._pan_ref is None:
            return
        dx = cx - self._pan_ref[0]
        dy = cy - self._pan_ref[1]
        self._pan_ref = (cx, cy)
        bbox = self.ax.get_window_extent()
        xl, xr = self.ax.get_xlim()
        yb, yt = self.ax.get_ylim()
        sx = (xr - xl) / max(bbox.width,  1)
        sy = (yt - yb) / max(bbox.height, 1)
        self.ax.set_xlim(xl - dx * sx, xr - dx * sx)
        self.ax.set_ylim(yb - dy * sy, yt - dy * sy)
        self.draw_idle()

    def _centre_view(self, x, y):
        xl, xr = self.ax.get_xlim()
        yb, yt = self.ax.get_ylim()
        hw = (xr - xl) / 2.0
        hh = (yt - yb) / 2.0
        self.ax.set_xlim(x - hw, x + hw)
        self.ax.set_ylim(y - hh, y + hh)
        self.draw_idle()

    # ── Aperture helpers ──────────────────────────────────────────────────────

    def _place_centre(self, x, y):
        self._apert_cx, self._apert_cy = x, y
        if self._marker: self._marker.remove()
        if self._patch:  self._patch.remove(); self._patch = None
        self._marker, = self.ax.plot(x, y, "+", color="cyan",
                                     ms=14, mew=2, zorder=6)
        self.draw_idle()

    def _update_ellipse(self, x, y):
        if x is None or y is None:
            return
        a = max(abs(x - self._apert_cx), 0.5)
        b = max(abs(y - self._apert_cy), 0.5)
        if self._patch: self._patch.remove()
        self._patch = mpatches.Ellipse(
            (self._apert_cx, self._apert_cy), width=2*a, height=2*b,
            fill=False, edgecolor="cyan", lw=1.5, ls="--", zorder=5)
        self.ax.add_patch(self._patch)
        self.draw_idle()

    def _drag_aperture(self, x, y):
        """Drag the finalized aperture to a new position."""
        if self._patch is None or self._pan_ref is None:
            return
        dx = x - self._pan_ref[0]
        dy = y - self._pan_ref[1]
        self._pan_ref = (x, y)

        cx, cy = self._patch.center
        self._patch.set_center((cx + dx, cy + dy))
        self.draw_idle()

    def _finalise_aperture(self, x, y):
        a = max(abs(x - self._apert_cx), 0.5)
        b = max(abs(y - self._apert_cy), 0.5)
        cx, cy = self._apert_cx, self._apert_cy

        if self._patch: self._patch.remove()
        self._patch = mpatches.Ellipse(
            (cx, cy), width=2*a, height=2*b, angle=0.0,
            fill=False, edgecolor="cyan", lw=2.0, zorder=5)
        self.ax.add_patch(self._patch)
        if self._marker: self._marker.remove(); self._marker = None
        self.draw_idle()

        self._aperture_finalised = True
        self._apert_cx = self._apert_cy = None
        self._emit_aperture_from_patch()

    def _emit_aperture_from_patch(self):
        """Recompute mask from current patch geometry and emit aperture_ready."""
        cx, cy = self._patch.center
        a   = max(self._patch.width  / 2, 0.5)
        b   = max(self._patch.height / 2, 0.5)
        pa  = self._patch.angle
        ys, xs = np.ogrid[0:self._ny, 0:self._nx]
        pa_rad = np.deg2rad(pa)
        cos_a, sin_a = np.cos(pa_rad), np.sin(pa_rad)
        dx, dy = xs - cx, ys - cy
        x_rot  = dx * cos_a + dy * sin_a
        y_rot  = -dx * sin_a + dy * cos_a
        mask   = (x_rot / a) ** 2 + (y_rot / b) ** 2 <= 1.0
        if mask.sum() > 0:
            self.aperture_ready.emit(mask, float(cx), float(cy),
                                     float(a), float(b), float(pa))

    def _inside_aperture(self, x, y):
        if self._patch is None:
            return False
        cx, cy = self._patch.center
        a = max(self._patch.width  / 2, 0.5)
        b = max(self._patch.height / 2, 0.5)
        pa_rad = np.deg2rad(self._patch.angle)
        dx, dy = x - cx, y - cy
        x_rot  = dx * np.cos(pa_rad) + dy * np.sin(pa_rad)
        y_rot  = -dx * np.sin(pa_rad) + dy * np.cos(pa_rad)
        return (x_rot / a) ** 2 + (y_rot / b) ** 2 <= 1.5   # slight margin for usability

    def _open_aperture_edit(self):
        cx, cy = self._patch.center
        a   = self._patch.width  / 2
        b   = self._patch.height / 2
        pa  = self._patch.angle
        dlg = ApertureEditDialog(a, b, pa,
                                 pix_scale_ds=self._pix_scale_ds,
                                 parent=self.parent())
        if dlg.exec_() != QDialog.Accepted:
            return
        a_new, b_new, pa_new = dlg.values()
        a_new = max(0.5, a_new)
        b_new = max(0.5, b_new)
        if self._patch: self._patch.remove()
        self._patch = mpatches.Ellipse(
            (cx, cy), width=2*a_new, height=2*b_new, angle=pa_new,
            fill=False, edgecolor="cyan", lw=2.0, zorder=5)
        self.ax.add_patch(self._patch)
        self.draw_idle()
        self._emit_aperture_from_patch()

    def toggle_aperture_lock(self):
        """Toggle aperture lock state (locked = immovable, unlocked = draggable)."""
        if self._aperture_finalised:
            self._aperture_locked = not self._aperture_locked
            # Change patch edge color to indicate lock state
            if self._patch:
                color = "#ccaa00" if self._aperture_locked else "cyan"
                self._patch.set_edgecolor(color)
                self.draw_idle()
            return self._aperture_locked
        return self._aperture_locked

    def _clear_aperture(self):
        if self._patch:  self._patch.remove();  self._patch  = None
        if self._marker: self._marker.remove(); self._marker = None
        self._aperture_finalised = False
        self._aperture_locked = False
        self._apert_cx = self._apert_cy = None
        self._state = "idle"
        self.draw_idle()
        self.aperture_cleared.emit()


# ── Beam / pixel-scale helpers ────────────────────────────────────────────────

def _read_beam(header):
    """Return (bmaj_arcsec, bmin_arcsec, bpa_deg) from primary header, or None."""
    try:
        bmaj = float(header["BMAJ"]) * 3600   # degrees → arcsec
        bmin = float(header["BMIN"]) * 3600
        bpa  = float(header.get("BPA", 0.0))
        return (round(bmaj, 4), round(bmin, 4), round(bpa, 4))
    except (KeyError, ValueError, TypeError):
        return None


def _read_beam_from_hdul(hdul):
    """Return (median_beam_tuple, per_channel_array_or_None, source_label).

    median_beam_tuple = (bmaj_arcsec, bmin_arcsec, bpa_deg) or None
    per_channel_array = np.ndarray shape (N,3) [bmaj,bmin,bpa] in arcsec/deg, or None
    source_label      = human-readable string describing where the beam came from

    Priority:
    1. CASA BEAMS binary table extension — returns full per-channel array
    2. Primary header BMAJ/BMIN/BPA (degrees) — returns single beam, no per-channel
    """
    # ── Try CASA BEAMS extension first ────────────────────────────────────────
    for ext in hdul[1:]:
        if ext.header.get('EXTNAME', '') == 'BEAMS':
            try:
                d    = ext.data
                cols = [c.name.upper() for c in ext.columns]
                bmaj_col = ext.columns[cols.index('BMAJ')]
                unit     = (bmaj_col.unit or '').lower()
                bmaj_arr = np.array(d['BMAJ'], dtype=float)
                bmin_arr = np.array(d['BMIN'], dtype=float)
                bpa_arr  = np.array(d['BPA'],  dtype=float)
                if 'deg' in unit:
                    bmaj_arr *= 3600
                    bmin_arr *= 3600
                per_ch = np.column_stack([bmaj_arr, bmin_arr, bpa_arr])
                # Use the channel with the largest beam (worst resolution) as reference
                idx_max  = int(np.argmax(bmaj_arr))
                rep_beam = (round(float(bmaj_arr[idx_max]), 4),
                            round(float(bmin_arr[idx_max]), 4),
                            round(float(bpa_arr[idx_max]),  4))
                return rep_beam, per_ch, "CASA BEAMS table"
            except Exception:
                pass

    # ── Fall back to primary header ────────────────────────────────────────────
    b = _read_beam(hdul[0].header)
    if b is not None:
        return b, None, "FITS header (BMAJ/BMIN/BPA)"

    return None, None, None


def _read_pixscale(header):
    """Return pixel scale in arcsec/pixel, or None."""
    for key in ("CDELT2", "CDELT1"):
        try:
            v = float(header[key])
            if v != 0:
                return abs(v) * 3600
        except (KeyError, ValueError, TypeError):
            pass
    return None


class BeamInputDialog(QDialog):
    """Shown when no FITS cube carries beam information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Beam Information Required")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.values = None

        vbox = QVBoxLayout(self)
        note = QLabel(
            "No beam information (BMAJ / BMIN / BPA) was found in any of the "
            "provided FITS cubes.\n\n"
            "Please enter the restoring beam parameters manually (in arcseconds / degrees)."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555;")
        vbox.addWidget(note)

        grp  = QGroupBox("Restoring beam")
        form = QFormLayout(grp)

        self._bmaj = QDoubleSpinBox()
        self._bmaj.setRange(0.001, 3600); self._bmaj.setDecimals(3)
        self._bmaj.setSuffix(' "');       self._bmaj.setValue(15.0)

        self._bmin = QDoubleSpinBox()
        self._bmin.setRange(0.001, 3600); self._bmin.setDecimals(3)
        self._bmin.setSuffix(' "');       self._bmin.setValue(12.0)

        self._bpa = QDoubleSpinBox()
        self._bpa.setRange(-180, 180);    self._bpa.setDecimals(1)
        self._bpa.setSuffix(' °');        self._bpa.setValue(0.0)

        form.addRow("BMAJ — major axis FWHM:", self._bmaj)
        form.addRow("BMIN — minor axis FWHM:", self._bmin)
        form.addRow("BPA  — position angle:",  self._bpa)
        vbox.addWidget(grp)

        btns   = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.setStyleSheet("background:#1a7abf;color:white;font-weight:bold;"
                         "padding:4px 18px;border-radius:3px;")
        ok.clicked.connect(self._ok)
        btns.addWidget(cancel); btns.addStretch(); btns.addWidget(ok)
        vbox.addLayout(btns)

    def _ok(self):
        self.values = (self._bmaj.value(), self._bmin.value(), self._bpa.value())
        self.accept()


def validate_inputs(paths, parent=None):
    """Check dimensions, extract and validate beam info across all cubes.

    Returns (ok, beam_info) where beam_info is a dict with keys:
        bmaj, bmin, bpa  — arcseconds / degrees
        pix_scale        — arcsec per native pixel (may be None)
        source           — human-readable label for which cube supplied the beam
    Returns (False, None) if the user should not proceed.
    """
    from astropy.io import fits as _fits

    cube_paths = [
        ("FDF",          paths.get("fdf")),
        ("Stokes I",     paths.get("i")),
        ("Stokes Q",     paths.get("q")),
        ("Stokes U",     paths.get("u")),
        ("Full Stokes",  paths.get("full_stokes")),
    ]
    available = [(lbl, p) for lbl, p in cube_paths if p and os.path.exists(p)]
    if not available:
        return False, None

    # ── Read headers + full HDU lists (needed for BEAMS extension) ───────────
    headers = {}
    hduls   = {}
    for lbl, p in available:
        try:
            hdul = _fits.open(p, memmap=True)
            headers[lbl] = hdul[0].header
            hduls[lbl]   = hdul
        except Exception as e:
            QMessageBox.critical(parent, "File Error",
                                 f"Could not read {lbl}:\n{p}\n\n{e}")
            return False, None

    # ── Spatial dimension check ───────────────────────────────────────────────
    shapes = {lbl: (h.get("NAXIS1"), h.get("NAXIS2")) for lbl, h in headers.items()}
    unique_shapes = set(shapes.values())
    if len(unique_shapes) > 1:
        detail = "\n".join(f"  {lbl}: {n1} × {n2} px"
                           for lbl, (n1, n2) in shapes.items())
        QMessageBox.critical(
            parent, "Dimension Mismatch",
            "Spatial dimensions do not match across cubes:\n\n"
            + detail +
            "\n\nAll cubes must share the same RA/Dec pixel grid."
        )
        return False, None

    # ── Pixel scale ───────────────────────────────────────────────────────────
    pix_scale = None
    for h in headers.values():
        ps = _read_pixscale(h)
        if ps:
            pix_scale = ps
            break

    # ── Beam extraction ───────────────────────────────────────────────────────
    raw_beams    = {lbl: _read_beam_from_hdul(hduls[lbl]) for lbl in hduls}
    # raw_beams[lbl] = (median_tuple, per_channel_or_None, source_label)
    beams        = {lbl: r[0] for lbl, r in raw_beams.items() if r[0] is not None}
    per_ch_beams = {lbl: r[1] for lbl, r in raw_beams.items() if r[1] is not None}
    sources      = {lbl: r[2] for lbl, r in raw_beams.items() if r[0] is not None}

    # ── Inform user when CASA BEAMS extension(s) found ───────────────────────
    casa_cubes = [lbl for lbl, r in raw_beams.items()
                  if r[0] is not None and r[2] == "CASA BEAMS table"]
    if casa_cubes:
        details = "\n".join(
            f"  {lbl}: largest beam = {beams[lbl][0]:.3f}\" × {beams[lbl][1]:.3f}\""
            f"  (out of {len(per_ch_beams[lbl])} channels)"
            for lbl in casa_cubes
        )
        QMessageBox.information(
            parent, "CASA Per-Channel Beam Tables Found",
            f"CASA per-channel restoring beam tables were found in:\n\n"
            f"{details}\n\n"
            f"The largest beam per cube is shown above and will be used as the "
            f"reference for aperture size reporting. Individual per-channel beams "
            f"will be used for aperture photometry during the interactive session.\n\n"
            f"Cubes without a BEAMS table will use a uniform aperture "
            f"for all frequency slices."
        )

    # Case A: no beam info anywhere → ask user, then confirm
    if not beams:
        dlg = BeamInputDialog(parent)
        if dlg.exec_() != QDialog.Accepted or dlg.values is None:
            return False, None
        bmaj, bmin, bpa = dlg.values
        return _confirm_resolution(
            parent, headers,
            dict(bmaj=bmaj, bmin=bmin, bpa=bpa,
                 pix_scale=pix_scale, source="user input")
        )

    # Case B: beams differ beyond tolerance → hard stop
    # Tolerance mirrors CASA imsmooth: 2% on axes, 1° on BPA.
    def _beams_match(b1, b2, frac_tol=0.02, bpa_tol=1.0):
        bm1, bn1, bp1 = b1
        bm2, bn2, bp2 = b2
        return (abs(bm1 - bm2) / max(bm1, bm2) <= frac_tol and
                abs(bn1 - bn2) / max(bn1, bn2) <= frac_tol and
                abs(bp1 - bp2) <= bpa_tol)

    beam_list  = list(beams.values())
    ref_beam   = beam_list[0]
    mismatched = {lbl: b for lbl, b in beams.items()
                  if not _beams_match(b, ref_beam)}

    if mismatched:
        all_beams = {**{list(beams.keys())[0]: ref_beam}, **mismatched}
        detail = "\n".join(
            f"  {lbl}: BMAJ={bm:.4f}\", BMIN={bn:.4f}\", BPA={bp:.2f}°"
            for lbl, (bm, bn, bp) in beams.items()
        )
        QMessageBox.critical(
            parent, "Beam Mismatch",
            "Beam information differs between cubes beyond tolerance "
            "(2% on axes, 1° on BPA):\n\n"
            + detail +
            "\n\nCubes with mismatched beams cannot be directly compared.\n"
            "Please re-image using a common restoring beam before proceeding."
        )
        return False, None

    # Case C: beam found in some but not all → warn, continue
    missing = [lbl for lbl in headers if lbl not in beams]
    first_lbl  = next(iter(beams))
    bmaj, bmin, bpa = beams[first_lbl]

    if missing:
        QMessageBox.warning(
            parent, "Missing Beam Info",
            f"Beam information is absent from: {', '.join(missing)}.\n\n"
            f"The beam from {first_lbl} will be used for aperture calculations:\n"
            f"  BMAJ = {bmaj:.2f}\"  BMIN = {bmin:.2f}\"  BPA = {bpa:.1f}°"
        )

    return _confirm_resolution(
        parent, headers,
        dict(bmaj=bmaj, bmin=bmin, bpa=bpa,
             pix_scale=pix_scale, source=first_lbl,
             per_channel=per_ch_beams.get(first_lbl))
    )


def _confirm_resolution(parent, headers, beam_info):
    """Show resolution-assumption confirmation — skipped when CASA BEAMS tables cover all Stokes cubes."""
    stokes_loaded = [lbl for lbl in ("Stokes I", "Stokes Q", "Stokes U", "Full Stokes")
                     if lbl in headers]
    if not stokes_loaded:
        return True, beam_info

    # CASA per-channel beam table already encodes per-slice resolution — no assumption needed
    if beam_info.get("per_channel") is not None:
        return True, beam_info

    msg = QMessageBox(parent)
    msg.setWindowTitle("Resolution Assumption")
    msg.setIcon(QMessageBox.Information)
    msg.setText("<b>Assumption: uniform angular resolution</b>")
    msg.setInformativeText(
        "It is assumed that all frequency slices in the Stokes "
        f"{', '.join(s.replace('Stokes ', '') for s in stokes_loaded)} "
        "cubes have been imaged or smoothed to the same angular resolution.\n\n"
        "If this is not the case, aperture-averaged fractional polarisation "
        "values (q = Q/I, u = U/I) will be unreliable."
    )
    msg.setStandardButtons(QMessageBox.Cancel)
    proceed = msg.addButton("Proceed", QMessageBox.AcceptRole)
    msg.setDefaultButton(proceed)
    msg.exec_()
    if msg.clickedButton() is not proceed:
        return False, None
    return True, beam_info


# ── Opening splash ────────────────────────────────────────────────────────────

class VideoSplash(QSplashScreen):
    """Two-phase animated splash screen using ffmpeg pipe decoding.

    Phase 1 — branding (splash.mp4):  fade in → play → fade out
    Phase 2 — app title (splash_app.mp4): fade in → play → hold 1 s → finished

    No GStreamer dependency. Falls back to static PNG if both videos are absent.
    """

    finished = pyqtSignal()

    _FADE_STEPS = 20   # steps for each fade (20 × 16 ms ≈ 0.32 s)

    def __init__(self):
        # Pre-load both video frame sequences
        self._v1, self._fps1 = self._load(SPLASH_VIDEO_1)
        self._v2, self._fps2 = self._load(SPLASH_VIDEO_2)

        # Initial pixmap — try in order: video frame → splash_frame.png →
        # FEIcon.png → tiny solid colour pixmap (guaranteed non-null).
        first = (self._v1 or self._v2)
        pixmap = first[0] if first else QPixmap()
        if pixmap.isNull() and os.path.exists(SPLASH_IMAGE):
            pixmap = QPixmap(SPLASH_IMAGE)
        if pixmap.isNull():
            icon_path = os.path.join(_HERE, "FEIcon.png")
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path).scaledToWidth(SPLASH_WIDTH,
                                                          Qt.SmoothTransformation)
        if pixmap.isNull():
            # Ultimate fallback: build a 500×216 dark pixmap so something shows
            from PyQt5.QtGui import QColor
            pixmap = QPixmap(SPLASH_WIDTH, 216)
            pixmap.fill(QColor(20, 20, 30))

        super().__init__(pixmap, Qt.WindowStaysOnTopHint)
        self.setWindowOpacity(0.0)

        self._phase      = 1      # 1 = branding, 2 = app title
        self._idx        = 0
        self._fade_step  = 0

        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._next_frame)

        self._hold_timer = QTimer(self, singleShot=True)
        self._hold_timer.timeout.connect(self.finished)

    # ── public ────────────────────────────────────────────────────────────────
    def start(self):
        self.show()
        QApplication.processEvents()
        self._begin_phase(1)

    # ── phase control ─────────────────────────────────────────────────────────
    def _begin_phase(self, phase):
        self._phase     = phase
        self._idx       = 0
        self._fade_step = 0
        frames = self._v1 if phase == 1 else self._v2
        if frames:
            self.setPixmap(frames[0])
            self.repaint()
        self._fade_in()

    def _fade_in(self):
        self._fade_step += 1
        opacity = min(1.0, self._fade_step / self._FADE_STEPS)
        self.setWindowOpacity(opacity)
        QApplication.processEvents()
        if opacity < 1.0:
            QTimer.singleShot(16, self._fade_in)
        else:
            frames = self._v1 if self._phase == 1 else self._v2
            if frames:
                fps = self._fps1 if self._phase == 1 else self._fps2
                self._frame_timer.setInterval(max(16, int(1000.0 / (fps * 2))))  # 2x faster
                self._frame_timer.start()
            else:
                self._on_video_done()

    def _fade_out(self):
        self._fade_step -= 1
        opacity = max(0.0, self._fade_step / self._FADE_STEPS)
        self.setWindowOpacity(opacity)
        QApplication.processEvents()
        if opacity > 0.0:
            QTimer.singleShot(16, self._fade_out)
        else:
            self._begin_phase(2)

    # ── frame playback ────────────────────────────────────────────────────────
    def _next_frame(self):
        self._idx += 1
        frames = self._v1 if self._phase == 1 else self._v2
        if self._idx >= len(frames):
            self._frame_timer.stop()
            self._on_video_done()
            return
        self.setPixmap(frames[self._idx])
        self.repaint()

    def _on_video_done(self):
        if self._phase == 1:
            # Fade out branding, then start app-title video
            self._fade_step = self._FADE_STEPS
            self._fade_out()
        else:
            # Hold last frame then signal done
            self._hold_timer.start(SPLASH_EXTRA_MS)

    # ── ffmpeg helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _load(path):
        """Return (frames, fps) for a video file, or ([], 25.0) on failure."""
        if not os.path.exists(path):
            return [], 25.0
        try:
            raw = subprocess.check_output(
                [_FFPROBE, '-v', 'quiet', '-print_format', 'json',
                 '-show_streams', path],
                stderr=subprocess.DEVNULL
            )
            info = None
            for s in json.loads(raw).get('streams', []):
                if s.get('codec_type') == 'video':
                    w, h = s['width'], s['height']
                    num, den = s.get('r_frame_rate', '25/1').split('/')
                    info = (w, h, float(num) / float(den))
                    break
            if not info:
                return [], 25.0
            src_w, src_h, fps = info
            dst_w = SPLASH_WIDTH
            dst_h = int(src_h * dst_w / src_w)
            if dst_h % 2:
                dst_h += 1
            proc = subprocess.Popen(
                [_FFMPEG, '-i', path,
                 '-vf', f'scale={dst_w}:{dst_h}:flags=lanczos',
                 '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            frame_bytes = dst_w * dst_h * 3
            frames = []
            while True:
                chunk = proc.stdout.read(frame_bytes)
                if len(chunk) < frame_bytes:
                    break
                arr = np.frombuffer(chunk, dtype=np.uint8).reshape((dst_h, dst_w, 3))
                img = QImage(arr.tobytes(), dst_w, dst_h,
                             dst_w * 3, QImage.Format_RGB888)
                frames.append(QPixmap.fromImage(img))
            proc.stdout.close()
            proc.wait()
            return frames, fps
        except Exception:
            return [], 25.0


# ── Full-Stokes cube extraction ───────────────────────────────────────────────

def _extract_stokes_iqu(path):
    """Return (i_data, q_data, u_data) as 3-D (freq, dec, ra) arrays
    extracted from a 4-D FITS cube that has a STOKES axis."""
    from astropy.io import fits as _fits
    hdul  = _fits.open(path, memmap=True)
    data  = hdul[0].data
    h     = hdul[0].header
    naxis = h["NAXIS"]

    stokes_fits_ax = None
    for ax in range(1, naxis + 1):
        if "STOKES" in h.get(f"CTYPE{ax}", "").upper():
            stokes_fits_ax = ax
            break
    if stokes_fits_ax is None:
        raise ValueError("No STOKES axis found in the cube header.")

    stokes_np_ax = naxis - stokes_fits_ax   # FITS↔numpy axis reversal
    n_stokes = h[f"NAXIS{stokes_fits_ax}"]
    crval    = h.get(f"CRVAL{stokes_fits_ax}", 1.0)
    cdelt    = h.get(f"CDELT{stokes_fits_ax}", 1.0)
    crpix    = h.get(f"CRPIX{stokes_fits_ax}", 1.0)
    vals     = np.round(crval + (np.arange(1, n_stokes + 1) - crpix) * cdelt).astype(int)

    def _take(stokes_val, name):
        idx = np.where(vals == stokes_val)[0]
        if not len(idx):
            raise ValueError(
                f"Stokes {name} (code {stokes_val}) not found in cube. "
                f"Available codes: {vals.tolist()}"
            )
        return np.take(data, int(idx[0]), axis=stokes_np_ax)

    return _take(1, "I"), _take(2, "Q"), _take(3, "U")


# ── Startup file-picker dialog ────────────────────────────────────────────────

class LaunchDialog(QDialog):
    """Shown at startup (and via File > Open) to select all input files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Faraday Explorer — Open Files")
        self.setMinimumWidth(600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._cfg      = QSettings("FaradayExplorer", "FaradayExplorer")
        self._last_dir = self._cfg.value("last_dir", os.path.expanduser("~"))
        self.paths     = {}   # populated when user clicks Open

        self._setup_ui()
        self._check_ready()   # enable/disable Open based on restored paths

    def showEvent(self, event):
        super().showEvent(event)
        # On macOS, launchd-started apps are not automatically frontmost.
        # A deferred activateWindow() after the event loop paints the window
        # reliably brings it to front without needing any private APIs.
        QTimer.singleShot(0, self.raise_)
        QTimer.singleShot(0, self.activateWindow)

    def _setup_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setSpacing(10)

        # Header
        hdr = QLabel(
            "<h2 style='margin:0;'>Faraday Explorer</h2>"
            "<p style='color:#666; margin:2px 0 0;'>"
            "Interactive polarisation model viewer — MeerKAT</p>"
        )
        vbox.addWidget(hdr)

        # ── Required files ────────────────────────────────────────────────────
        req = QGroupBox("Required")
        rf  = QFormLayout(req)
        rf.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self._fdf_edit  = self._file_row(rf, "FDF cube",        "*.fits *.FITS", "fdf")
        self._freq_edit = self._file_row(rf, "Frequency file",  "*.dat *.txt",   "freq")
        vbox.addWidget(req)

        # ── Optional Stokes cubes ────────────────────────────────────────────
        opt = QGroupBox("Stokes cubes  (optional — enables real Q/U scatter)")
        ov  = QVBoxLayout(opt)
        ov.setSpacing(6)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Input type:"))
        self._stokes_mode = QComboBox()
        self._stokes_mode.addItem("Separate Stokes continuum cubes", "separate")
        self._stokes_mode.addItem("Full Stokes full frequency cube",  "full")
        saved_mode = self._cfg.value("stokes_mode", "separate")
        self._stokes_mode.setCurrentIndex(0 if saved_mode != "full" else 1)
        mode_row.addWidget(self._stokes_mode)
        mode_row.addStretch()
        ov.addLayout(mode_row)

        self._stokes_stack = QStackedWidget()

        # Page 0 — separate I, Q, U files
        sep_w = QWidget()
        sep_f = QFormLayout(sep_w)
        sep_f.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self._i_edit = self._file_row(sep_f, "Stokes I", "*.fits *.FITS", "i")
        self._q_edit = self._file_row(sep_f, "Stokes Q", "*.fits *.FITS", "q")
        self._u_edit = self._file_row(sep_f, "Stokes U", "*.fits *.FITS", "u")
        self._stokes_stack.addWidget(sep_w)

        # Page 1 — single full-Stokes cube
        full_w = QWidget()
        full_f = QFormLayout(full_w)
        full_f.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self._full_edit = self._file_row(full_f, "Full Stokes cube", "*.fits *.FITS",
                                          "full_stokes")
        self._stokes_stack.addWidget(full_w)

        self._stokes_stack.setCurrentIndex(0 if saved_mode != "full" else 1)
        ov.addWidget(self._stokes_stack)

        self._stokes_mode.currentIndexChanged.connect(self._stokes_stack.setCurrentIndex)
        self._stokes_mode.currentIndexChanged.connect(self._on_stokes_mode_changed)
        vbox.addWidget(opt)

        # ── Phi axis override ─────────────────────────────────────────────────
        phi_box = QGroupBox("Phi axis (Faraday depth)")
        phi_vb  = QVBoxLayout(phi_box)
        phi_vb.setSpacing(4)
        self._phi_override_cb = QCheckBox(
            "Override phi axis from FITS header  "
            "(use when FITS writes FREQ instead of FDEP)"
        )
        phi_note = QLabel(
            "Some RM-synthesis tools write incorrect WCS for the phi axis. "
            "Tick this if the channel display shows Hz/GHz values instead of rad/m²."
        )
        phi_note.setStyleSheet("color: #888; font-size: 9pt;")
        phi_note.setWordWrap(True)
        phi_vb.addWidget(self._phi_override_cb)
        phi_vb.addWidget(phi_note)

        self._phi_ctrl = QWidget()
        phi_row = QHBoxLayout(self._phi_ctrl)
        phi_row.setContentsMargins(0, 2, 0, 0)
        phi_row.addWidget(QLabel("φ min:"))
        self._phi_min_spin = QDoubleSpinBox()
        self._phi_min_spin.setRange(-100000, 0)
        self._phi_min_spin.setDecimals(1)
        self._phi_min_spin.setValue(float(self._cfg.value("phi_min", -1000.0)))
        self._phi_min_spin.setSuffix(" rad/m²")
        self._phi_min_spin.setFixedWidth(130)
        phi_row.addWidget(self._phi_min_spin)
        phi_row.addSpacing(12)
        phi_row.addWidget(QLabel("φ max:"))
        self._phi_max_spin = QDoubleSpinBox()
        self._phi_max_spin.setRange(0, 100000)
        self._phi_max_spin.setDecimals(1)
        self._phi_max_spin.setValue(float(self._cfg.value("phi_max", 1000.0)))
        self._phi_max_spin.setSuffix(" rad/m²")
        self._phi_max_spin.setFixedWidth(130)
        phi_row.addWidget(self._phi_max_spin)
        phi_row.addStretch()
        phi_vb.addWidget(self._phi_ctrl)

        phi_on = self._cfg.value("phi_override", False, type=bool)
        self._phi_override_cb.setChecked(phi_on)
        self._phi_ctrl.setVisible(phi_on)
        self._phi_override_cb.toggled.connect(self._phi_ctrl.setVisible)
        vbox.addWidget(phi_box)

        # ── Downsampling ──────────────────────────────────────────────────────
        ds_box    = QGroupBox("Spatial downsampling")
        ds_layout = QVBoxLayout(ds_box)
        ds_layout.setSpacing(4)

        self._ds_check = QCheckBox("Enable downsampling")
        rec = QLabel(
            "Recommended — greatly reduces load time and memory for large cubes."
        )
        rec.setStyleSheet("color: #888; font-size: 9pt;")
        rec.setWordWrap(True)

        self._ds_ctrl = QWidget()
        ctrl_row = QHBoxLayout(self._ds_ctrl)
        ctrl_row.setContentsMargins(0, 2, 0, 0)
        ctrl_row.addWidget(QLabel("Resolution:"))
        self._ds_spin = QSpinBox()
        self._ds_spin.setRange(1, 100)
        self._ds_spin.setSuffix(" %")
        self._ds_spin.setFixedWidth(75)
        self._ds_spin.setValue(int(self._cfg.value("ds_pct", 4)))
        self._ds_step_lbl = QLabel()
        self._ds_step_lbl.setStyleSheet("color: #555; font-size: 9pt;")
        ctrl_row.addWidget(self._ds_spin)
        ctrl_row.addWidget(self._ds_step_lbl)
        ctrl_row.addStretch()

        ds_layout.addWidget(self._ds_check)
        ds_layout.addWidget(rec)
        ds_layout.addWidget(self._ds_ctrl)
        vbox.addWidget(ds_box)

        # restore saved toggle state
        ds_on = self._cfg.value("ds_enabled", True, type=bool)
        self._ds_check.setChecked(ds_on)
        self._ds_ctrl.setVisible(ds_on)
        self._update_ds_label()

        self._ds_check.toggled.connect(self._ds_ctrl.setVisible)
        self._ds_check.toggled.connect(self._update_ds_label)
        self._ds_spin.valueChanged.connect(self._update_ds_label)

        # Status line
        self._status = QLabel()
        self._status.setStyleSheet("color: #888;")
        vbox.addWidget(self._status)

        # Buttons
        btn_row = QHBoxLayout()
        cancel  = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self._open_btn = QPushButton("Open Viewer")
        self._open_btn.setEnabled(False)
        self._open_btn.setDefault(True)
        self._open_btn.setMinimumWidth(140)
        self._open_btn.setStyleSheet(
            "QPushButton:enabled{background:#1a7abf;color:white;"
            "font-weight:bold;padding:4px 24px;border-radius:3px;}"
        )
        self._open_btn.clicked.connect(self._accept)
        btn_row.addWidget(cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._open_btn)
        vbox.addLayout(btn_row)

    def _file_row(self, form, label, ffilter, key):
        """Add one labelled path row; returns the QLineEdit."""
        w    = QWidget()
        hbox = QHBoxLayout(w)
        hbox.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setPlaceholderText("not selected")
        # Restore previously saved path if file still exists
        saved = self._cfg.value(f"path_{key}", "")
        if saved and os.path.exists(saved):
            edit.setText(saved)
        btn = QPushButton("Browse…")
        btn.setFixedWidth(82)
        btn.clicked.connect(lambda _, k=key, e=edit, f=ffilter: self._browse(k, e, f))
        hbox.addWidget(edit)
        hbox.addWidget(btn)
        form.addRow(f"{label}:", w)
        edit.textChanged.connect(self._check_ready)
        return edit

    def _update_ds_label(self):
        pct  = self._ds_spin.value()
        step = max(1, round(100 / pct))
        self._ds_step_lbl.setText(f"→ every {step}th pixel")
        self._cfg.setValue("ds_pct",     pct)
        self._cfg.setValue("ds_enabled", self._ds_check.isChecked())

    def _on_stokes_mode_changed(self, _idx):
        self._cfg.setValue("stokes_mode", self._stokes_mode.currentData())
        self._check_ready()

    def _browse(self, key, edit, ffilter):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select {key} file", self._last_dir,
            f"Data files ({ffilter});;All files (*)"
        )
        if path:
            edit.setText(path)
            self._last_dir = os.path.dirname(path)
            self._cfg.setValue("last_dir",       self._last_dir)
            self._cfg.setValue(f"path_{key}",    path)

    def _check_ready(self):
        ready = bool(self._fdf_edit.text() and self._freq_edit.text())
        self._open_btn.setEnabled(ready)
        if ready:
            mode = self._stokes_mode.currentData()
            if mode == "full":
                have_iqu = bool(self._full_edit.text())
            else:
                have_iqu = all([self._i_edit.text(),
                                self._q_edit.text(),
                                self._u_edit.text()])
            if have_iqu:
                self._status.setText("All files set — full mode (QU scatter enabled).")
                self._status.setStyleSheet("color: green;")
            else:
                self._status.setText("Required files set — FDF-only mode.")
                self._status.setStyleSheet("color: #1a7abf;")
        else:
            self._status.setText("Select the FDF cube and frequency file to continue.")
            self._status.setStyleSheet("color: #888;")

    def _accept(self):
        if self._ds_check.isChecked():
            map_step = max(1, round(100 / self._ds_spin.value()))
        else:
            map_step = 1
        mode = self._stokes_mode.currentData()
        if mode == "full":
            i = q = u = None
            full_stokes = self._full_edit.text() or None
        else:
            i    = self._i_edit.text()    or None
            q    = self._q_edit.text()    or None
            u    = self._u_edit.text()    or None
            full_stokes = None
        phi_override = None
        if self._phi_override_cb.isChecked():
            phi_override = {
                "min": self._phi_min_spin.value(),
                "max": self._phi_max_spin.value(),
            }
            self._cfg.setValue("phi_override", True)
            self._cfg.setValue("phi_min", self._phi_min_spin.value())
            self._cfg.setValue("phi_max", self._phi_max_spin.value())
        else:
            self._cfg.setValue("phi_override", False)
        self.paths = {
            "fdf":          self._fdf_edit.text(),
            "freq":         self._freq_edit.text(),
            "i":            i,
            "q":            q,
            "u":            u,
            "full_stokes":  full_stokes,
            "map_step":     map_step,
            "phi_override": phi_override,
        }
        self.accept()


# ── Loading progress dialog ───────────────────────────────────────────────────

# ── Workspace management ──────────────────────────────────────────────────────

class Workspace:
    """Saves and loads analysis state (model, parameters, settings)."""

    @staticmethod
    def get_workspace_dir(fdf_path):
        """Return workspace directory for a FDF file."""
        ws_dir = fdf_path + ".workspaces"
        return ws_dir

    @staticmethod
    def list_workspaces(fdf_path):
        """List all saved workspaces for a FDF file."""
        ws_dir = Workspace.get_workspace_dir(fdf_path)
        if not os.path.exists(ws_dir):
            return []
        return sorted([f for f in os.listdir(ws_dir) if f.endswith('.json')])

    @staticmethod
    def save_workspace(fdf_path, name, model, params, settings):
        """Save current workspace."""
        ws_dir = Workspace.get_workspace_dir(fdf_path)
        os.makedirs(ws_dir, exist_ok=True)

        ws_file = os.path.join(ws_dir, f"{name}.json")
        data = {
            "name": name,
            "model": model,
            "params": params,
            "settings": settings,
        }
        try:
            with open(ws_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True, f"Workspace '{name}' saved."
        except Exception as e:
            return False, f"Error saving workspace: {e}"

    @staticmethod
    def load_workspace(fdf_path, name):
        """Load a saved workspace."""
        ws_dir = Workspace.get_workspace_dir(fdf_path)
        ws_file = os.path.join(ws_dir, f"{name}.json")
        try:
            with open(ws_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            return None

    @staticmethod
    def delete_workspace(fdf_path, name):
        """Delete a saved workspace."""
        ws_dir = Workspace.get_workspace_dir(fdf_path)
        ws_file = os.path.join(ws_dir, f"{name}.json")
        try:
            os.remove(ws_file)
            return True
        except Exception:
            return False


# ── Model file save/load (.mod format) ────────────────────────────────────────

def _label_to_key(label):
    """
    Convert fancy display label to plain ASCII key for .mod files.
    Examples:
      "p₀" → "p_0"
      "χ₀  [°]" → "chi_0_deg"
      "RM  [rad/m²]" → "RM_rad_m2"
      "σ_RM₁[rad/m²]" → "sigma_RM_1_rad_m2"
      "RM₂ [rad/m²]" → "RM_2_rad_m2"
    """
    # Replace Greek letters with ASCII equivalents
    key = label.replace("χ", "chi").replace("σ", "sigma")
    # Remove subscript/superscript numbers and replace with underscore + number
    key = key.replace("₀", "_0").replace("₁", "_1").replace("₂", "_2").replace("₃", "_3")
    # Replace degree symbol and brackets
    key = key.replace("°", "deg").replace("[", "").replace("]", "")
    # Replace squared notation
    key = key.replace("m²", "m2")
    # Clean up extra spaces and brackets
    key = key.strip()
    # Replace remaining spaces with underscores
    key = key.replace("  ", "_").replace(" ", "_")
    return key

def _key_to_label(key, model):
    """
    Reverse mapping: convert ASCII key back to fancy label.
    Used when loading .mod files to display in UI.
    """
    # This is a fallback mapping for known patterns
    # The primary method is to match by order in MODEL_PARAMS
    return key

def save_model_file(path, model, params):
    """
    Save model and parameters to a .mod file (JSON format).
    Parameters are stored with plain ASCII keys (keyboard-friendly, no special chars).
    Users can edit these files by hand.
    """
    if model not in MODEL_PARAMS:
        return False, f"Unknown model: {model}"

    # Get parameter specs for this model
    param_specs = MODEL_PARAMS[model]

    # Create parameter dictionary with plain ASCII keys
    param_dict = {}
    for i, (label, vmin, vmax, vinit) in enumerate(param_specs):
        if i < len(params):
            key = _label_to_key(label)
            param_dict[key] = round(float(params[i]), 6)  # Round to 6 decimals for readability

    data = {
        "model": model,
        "description": f"FaradayExplorer model file for {model}. Edit 'params' values to customize.",
        "params": param_dict,
    }
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return True, f"Model saved to {os.path.basename(path)}"
    except Exception as e:
        return False, f"Error saving model: {e}"

def load_model_file(path):
    """
    Load model and parameters from a .mod file.
    Handles plain ASCII keys (new format).
    Returns (model, params_list, error_msg) where params_list is ordered for widget assignment.
    """
    try:
        with open(path, 'r') as f:
            data = json.load(f)

        model = data.get("model")
        if model not in MODEL_PARAMS:
            return None, None, f"Unknown model: {model}"

        # Get parameter specs to reconstruct ordered list
        param_specs = MODEL_PARAMS[model]
        params_data = data.get("params", {})

        # Convert dict with ASCII keys back to ordered list
        params_list = []
        for label, vmin, vmax, vinit in param_specs:
            key = _label_to_key(label)
            if key in params_data:
                params_list.append(float(params_data[key]))
            else:
                # Fallback to default if key missing
                params_list.append(vinit)

        return model, params_list, None
    except Exception as e:
        return None, None, f"Error loading model: {e}"


# ── Peak map caching ──────────────────────────────────────────────────────────

def _get_peak_cache_path(fdf_path):
    """Return the cache file path for a FDF cube's peak map."""
    return fdf_path + ".peak.npy"

def _load_peak_cache(fdf_path):
    """Try to load cached peak map; return None if not available or stale."""
    cache_path = _get_peak_cache_path(fdf_path)
    if not os.path.exists(cache_path):
        return None
    try:
        # Check if cache is newer than FDF file
        fdf_mtime = os.path.getmtime(fdf_path)
        cache_mtime = os.path.getmtime(cache_path)
        if cache_mtime < fdf_mtime:
            return None  # Cache is stale
        return np.load(cache_path)
    except Exception:
        return None

def _save_peak_cache(fdf_path, peak_map):
    """Save peak map to cache file."""
    cache_path = _get_peak_cache_path(fdf_path)
    try:
        np.save(cache_path, peak_map)
    except Exception:
        pass  # Silently fail if we can't write cache


class LoadingDialog(QDialog):
    """Modal progress dialog — loads cubes synchronously with processEvents()
    between steps so the bar stays live without needing a background thread."""

    def __init__(self, paths, map_step, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Faraday Explorer")
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setMinimumWidth(420)
        self.setModal(True)
        self.result_data = None
        self.error_msg   = None
        self._paths      = paths
        self._map_step   = map_step

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 22, 28, 22)

        title = QLabel("Loading…")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 13pt; font-weight: bold;")
        layout.addWidget(title)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setMinimumHeight(18)
        layout.addWidget(self._bar)

        self._lbl = QLabel("Starting…")
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(self._lbl)

        # Give the dialog one event-loop tick to paint before loading starts
        QTimer.singleShot(80, self._do_load)

    def _step(self, pct, msg):
        self._bar.setValue(pct)
        self._lbl.setText(msg)
        QApplication.processEvents()

    def _do_load(self):
        try:
            from astropy.io import fits as _fits
            result = {"has_data": False, "has_qu": False}

            fdf_path = self._paths["fdf"]
            if not os.path.exists(fdf_path):
                raise FileNotFoundError(f"FDF cube not found: {fdf_path}")

            self._step(5,  "Opening FDF cube…")
            hdu  = _fits.open(fdf_path, memmap=True)
            data = hdu[0].data
            h    = hdu[0].header

            # Squeeze any size-1 axes (e.g. a Stokes axis in a 4D FDF cube)
            # so downstream code always sees a 3-D (phi/freq, DEC, RA) array.
            data = data.squeeze()
            if data.ndim != 3:
                raise ValueError(
                    f"FDF cube has {data.ndim} non-trivial axes after squeezing "
                    f"(expected 3: phi × DEC × RA).  Shape: {data.shape}"
                )

            n3 = data.shape[0]
            result["fdf_data"] = data
            phi_ov = self._paths.get("phi_override")
            if phi_ov:
                # User explicitly set a phi range in the launch dialog.
                result["phi_data"] = np.linspace(
                    phi_ov["min"], phi_ov["max"], n3, dtype=np.float64
                )
            else:
                cr  = float(h.get("CRVAL3", 0.0))
                cd  = float(h.get("CDELT3", 1.0))
                cp  = float(h.get("CRPIX3", 1.0))
                phi = cr + (np.arange(1, n3 + 1) - cp) * cd
                # If the axis looks like Hz (CRVAL3 >> typical rad/m² range),
                # the FITS header is mislabeled — silently remap to a sensible
                # default phi range rather than displaying nonsense GHz values.
                if abs(cr) > 1e5 or abs(cr + (n3 - cp) * cd) > 1e5:
                    phi = np.linspace(-1000.0, 1000.0, n3, dtype=np.float64)
                result["phi_data"] = phi

            self._step(15, "Reading WCS…")
            try:
                from astropy.wcs import WCS
                result["wcs2d"] = WCS(h, naxis=2)
            except Exception:
                result["wcs2d"] = None

            # Peak map: try cache first, then compute and cache
            self._step(15, "Loading peak map…")
            peak = _load_peak_cache(fdf_path)
            if peak is not None:
                self._step(50, "Peak map loaded from cache.")
                result["peak_map"] = peak
            else:
                # Compute and cache: iterate over phi slabs so processEvents() fires
                # between each slab and macOS doesn't kill an unresponsive process.
                n_phi   = data.shape[0]
                step    = self._map_step
                n_slabs = max(1, min(20, n_phi))  # up to 20 progress ticks
                slab_sz = max(1, (n_phi + n_slabs - 1) // n_slabs)
                peak    = None
                for slab_start in range(0, n_phi, slab_sz):
                    slab_end  = min(slab_start + slab_sz, n_phi)
                    chunk     = data[slab_start:slab_end, ::step, ::step]
                    chunk_max = np.asarray(chunk).max(axis=0)
                    peak = chunk_max if peak is None else np.maximum(peak, chunk_max)
                    pct  = 15 + int(35 * slab_end / n_phi)   # 15 → 50 %
                    self._step(pct, f"Computing peak map… {slab_end}/{n_phi} planes")
                result["peak_map"] = peak
                _save_peak_cache(fdf_path, peak)
            result["has_data"] = True

            fs  = self._paths.get("full_stokes")
            i_p = self._paths.get("i")
            q_p = self._paths.get("q")
            u_p = self._paths.get("u")

            if fs and os.path.exists(fs):
                self._step(55, "Opening full Stokes cube…")
                i_d, q_d, u_d = _extract_stokes_iqu(fs)
                self._step(90, "Extracting I / Q / U planes…")
                result["i_data"] = i_d
                result["q_data"] = q_d
                result["u_data"] = u_d
                result["has_qu"] = True
            elif all(p and os.path.exists(p) for p in [i_p, q_p, u_p]):
                self._step(55, "Loading Stokes I…")
                result["i_data"] = _fits.open(i_p, memmap=True)[0].data
                self._step(70, "Loading Stokes Q…")
                result["q_data"] = _fits.open(q_p, memmap=True)[0].data
                self._step(85, "Loading Stokes U…")
                result["u_data"] = _fits.open(u_p, memmap=True)[0].data
                result["has_qu"] = True

            self._step(100, "Done.")
            self.result_data = result
            self.accept()

        except Exception as exc:
            import traceback
            self.error_msg = f"{exc}\n\n{traceback.format_exc()}"
            self.reject()


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self, fits_path, i_path, q_path, u_path, freqs,
                 map_step=MAP_STEP, beam_info=None, full_stokes_path=None,
                 _preloaded=None):
        super().__init__()
        self.setWindowTitle("Faraday Explorer  —  Polarisation Model Viewer")
        self.resize(1400, 800)

        # ── Theme setup ───────────────────────────────────────────────────────
        self.settings = QSettings("amani", "FaradayExplorer")
        self.theme = self.settings.value("theme", "dark")  # default to dark

        # ── Physics setup ─────────────────────────────────────────────────────
        self.freqs  = freqs
        self.lam2   = make_lambda2(freqs)
        self.n_chan  = len(freqs)
        self.phi     = np.linspace(PHI_MIN, PHI_MAX, N_PHI)
        self.rmsf    = np.abs(rm_synthesis(
            np.ones(self.n_chan, dtype=complex), self.lam2, self.phi))
        self.model   = "m1"

        self.real_fdf   = None
        self.real_q     = None
        self.real_u     = None
        self.real_label = None

        # FDF overlay visibility flags (toggled via the Display menu)
        self._show_peak_lines  = True
        self._show_peak_labels = True
        self._show_rmsf        = True

        # Track if parameters have changed since last save/load
        self._workspace_dirty = False

        # ── Load data ─────────────────────────────────────────────────────────
        self.has_data = self.has_qu = False
        self.map_step  = map_step
        self.beam_info = beam_info  # dict or None
        self._fdf_path = fits_path  # Store for workspace management
        if _preloaded is not None:
            self._inject_data(_preloaded)
        else:
            self._load_cubes(fits_path, i_path, q_path, u_path, full_stokes_path)

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_ui()

        # ── Apply theme ───────────────────────────────────────────────────────
        theme_dict = Theme.get_theme(self.theme)
        QApplication.instance().setStyleSheet(theme_dict["stylesheet"])

        # ── Update once to initialise plots ──────────────────────────────────
        self._update()

    # ── Data loading ──────────────────────────────────────────────────────────

    def _sync_phi_grid(self):
        """Extend the model phi grid and RMSF to cover the loaded phi_data range.

        Called after phi_data is populated so that the blue model FDF and
        the grey RMSF shading always span the full data extent.
        """
        if self.phi_data is not None and len(self.phi_data) > 1:
            lo = min(PHI_MIN, float(self.phi_data.min()))
            hi = max(PHI_MAX, float(self.phi_data.max()))
        else:
            lo, hi = PHI_MIN, PHI_MAX
        self.phi  = np.linspace(lo, hi, N_PHI)
        self.rmsf = np.abs(rm_synthesis(
            np.ones(self.n_chan, dtype=complex), self.lam2, self.phi))

    def _inject_data(self, d):
        """Populate data attributes from a dict produced by _DataLoader."""
        self.fdf_data = d.get("fdf_data")
        self.phi_data = d.get("phi_data")
        self.wcs2d    = d.get("wcs2d")
        self.peak_map = d.get("peak_map")
        self.has_data = d.get("has_data", False)
        self.has_qu   = d.get("has_qu",   False)
        if self.has_qu:
            self.i_data = d.get("i_data")
            self.q_data = d.get("q_data")
            self.u_data = d.get("u_data")
        self._sync_phi_grid()
        if self.has_data:
            print(f"  FDF: {self.fdf_data.shape}  φ: {self.phi_data[0]:.1f}…{self.phi_data[-1]:.1f}")
        if self.has_qu:
            print(f"  I/Q/U: {self.i_data.shape}")

    def _load_cubes(self, fits_path, i_path, q_path, u_path, full_stokes_path=None):
        if not os.path.exists(fits_path):
            print(f"[WARN] FDF cube not found: {fits_path}")
            return
        from astropy.io import fits as _fits
        print("Loading FDF cube…")
        hdu = _fits.open(fits_path, memmap=True)
        self.fdf_data = hdu[0].data
        h = hdu[0].header
        n3, cr, cd, cp = h["NAXIS3"], h["CRVAL3"], h["CDELT3"], h["CRPIX3"]
        phi = cr + (np.arange(1, n3+1) - cp) * cd
        if abs(cr) > 1e5 or abs(phi[-1]) > 1e5:
            phi = np.linspace(-1000.0, 1000.0, n3, dtype=np.float64)
        self.phi_data = phi
        self._sync_phi_grid()

        # Build a 2-D celestial WCS from the FDF header for pixel → RA/Dec
        self.wcs2d = None
        try:
            from astropy.wcs import WCS
            self.wcs2d = WCS(h, naxis=2)
        except Exception as e:
            print(f"[WARN] Could not build celestial WCS: {e}")

        print(f"Computing peak map…  (map_step={self.map_step})")
        self.peak_map = self.fdf_data[:, ::self.map_step, ::self.map_step].max(axis=0)
        self.has_data = True
        print(f"  FDF: {self.fdf_data.shape}  φ: {self.phi_data[0]:.1f}…{self.phi_data[-1]:.1f}")

        if full_stokes_path and os.path.exists(full_stokes_path):
            print("Loading full Stokes cube (extracting I/Q/U)…")
            try:
                self.i_data, self.q_data, self.u_data = _extract_stokes_iqu(full_stokes_path)
                self.has_qu = True
                print(f"  Full Stokes → I/Q/U: {self.i_data.shape}")
            except Exception as e:
                QMessageBox.warning(
                    None, "Full Stokes Extraction Failed",
                    f"Could not extract I/Q/U from full Stokes cube:\n{e}\n\n"
                    "Continuing without Stokes data."
                )
        elif all(p and os.path.exists(p) for p in [i_path, q_path, u_path]):
            print("Loading I/Q/U cubes…")
            self.i_data = _fits.open(i_path, memmap=True)[0].data
            self.q_data = _fits.open(q_path, memmap=True)[0].data
            self.u_data = _fits.open(u_path, memmap=True)[0].data
            self.has_qu = True
            print(f"  I/Q/U: {self.i_data.shape}")
        else:
            print("[INFO] No I/Q/U cubes — QU scatter will be model-only.")

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Need a central widget for QMainWindow even when everything is in docks
        self.setCentralWidget(QWidget())   # empty placeholder
        self.centralWidget().setMaximumSize(0, 0)

        dock_features = (QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable |
                         QDockWidget.DockWidgetClosable)

        # ── Controls dock (top-left) ──────────────────────────────────────────
        self._ctrl_dock = QDockWidget("Model & Parameters", self)
        self._ctrl_dock.setWidget(self._build_controls())
        self._ctrl_dock.setFeatures(dock_features)
        self._ctrl_dock.topLevelChanged.connect(
            lambda floating: self._ctrl_dock.resize(480, 750) if floating else None
        )
        self.addDockWidget(Qt.LeftDockWidgetArea, self._ctrl_dock)

        # ── Map dock (bottom-left, stacked under controls) ────────────────────
        if self.has_data:
            self.map_canvas = MapCanvas(self.peak_map)
            self.map_canvas.aperture_ready.connect(self._on_aperture)
            self.map_canvas.aperture_cleared.connect(self._on_aperture_cleared)
            bi = self.beam_info
            if bi and bi.get("pix_scale"):
                self.map_canvas.set_pixel_scale(bi["pix_scale"] * self.map_step)
            self._map_dock = QDockWidget("Peak |FDF| Map", self)
            self._map_dock.setWidget(self._build_map_panel())
            self._map_dock.setFeatures(dock_features)
            self.addDockWidget(Qt.LeftDockWidgetArea, self._map_dock)
            self.splitDockWidget(self._ctrl_dock, self._map_dock, Qt.Vertical)

        # ── QU plot dock (top-right) ──────────────────────────────────────────
        self._qu_dock = QDockWidget("q & u vs Frequency", self)
        self._qu_dock.setWidget(self._build_qu_panel())
        self._qu_dock.setFeatures(dock_features)
        self.addDockWidget(Qt.RightDockWidgetArea, self._qu_dock)

        # ── FDF plot dock (bottom-right, stacked under QU) ────────────────────
        self._fdf_dock = QDockWidget("FDF Comparison", self)
        self._fdf_dock.setWidget(self._build_fdf_panel())
        self._fdf_dock.setFeatures(dock_features)
        self.addDockWidget(Qt.RightDockWidgetArea, self._fdf_dock)
        self.splitDockWidget(self._qu_dock, self._fdf_dock, Qt.Vertical)

        QTimer.singleShot(0, self._apply_default_sizes)

        # ── File menu ─────────────────────────────────────────────────────────
        fmenu = self.menuBar().addMenu("&File")
        open_act = fmenu.addAction("Open new dataset…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_new)
        fmenu.addSeparator()

        # Workspace submenu
        ws_menu = fmenu.addMenu("Workspaces")
        save_ws_act = ws_menu.addAction("Save workspace…")
        save_ws_act.triggered.connect(self._save_workspace_dialog)

        # Load workspace submenu with available workspaces
        load_menu = ws_menu.addMenu("Load workspace")
        self._load_menu = load_menu  # Keep reference for dynamic updates
        self._populate_load_workspace_menu()

        ws_menu.addSeparator()
        manage_ws_act = ws_menu.addAction("Manage workspaces…")
        manage_ws_act.triggered.connect(self._manage_workspaces_dialog)

        fmenu.addSeparator()
        fmenu.addAction("Quit").triggered.connect(self.close)

        # ── View menu — lets user reopen any closed panel ─────────────────────
        view = self.menuBar().addMenu("&View")
        view.addAction(self._ctrl_dock.toggleViewAction())
        if self.has_data:
            view.addAction(self._map_dock.toggleViewAction())
        view.addAction(self._qu_dock.toggleViewAction())
        view.addAction(self._fdf_dock.toggleViewAction())
        view.addSeparator()

        # Theme submenu with mutually exclusive actions
        theme_menu = view.addMenu("Theme")
        self._theme_action_group = QActionGroup(theme_menu)
        self._theme_action_group.setExclusive(True)

        dark_act = theme_menu.addAction("Dark")
        dark_act.setCheckable(True)
        dark_act.setChecked(self.theme == "dark")
        dark_act.triggered.connect(lambda: self.set_theme("dark"))
        self._theme_action_group.addAction(dark_act)

        light_act = theme_menu.addAction("Light")
        light_act.setCheckable(True)
        light_act.setChecked(self.theme == "light")
        light_act.triggered.connect(lambda: self.set_theme("light"))
        self._theme_action_group.addAction(light_act)

        view.addSeparator()
        restore = view.addAction("Restore default layout")
        restore.triggered.connect(self._restore_layout)

        # ── Help menu ─────────────────────────────────────────────────────────
        help_menu = self.menuBar().addMenu("&Help")
        controls_act = help_menu.addAction("Map controls…")
        controls_act.triggered.connect(self._show_help_controls)
        help_menu.addSeparator()
        about_act = help_menu.addAction("About Faraday Explorer…")
        about_act.triggered.connect(self._show_about)

        # ── Status bar ────────────────────────────────────────────────────────
        self.statusBar().showMessage("Ready — draw an aperture on the map to load real data.")

    def _show_help_controls(self):
        QMessageBox.information(
            self, "Map Controls",
            "<b>Map navigation</b>"
            "<table cellpadding='3'>"
            "<tr><td><b>Left-drag</b></td><td>— pan the image</td></tr>"
            "<tr><td><b>Scroll wheel</b></td><td>— zoom in/out toward the cursor</td></tr>"
            "<tr><td><b>Middle-click</b></td><td>— centre the view on the click point</td></tr>"
            "</table>"
            "<br><b>Aperture drawing</b>"
            "<table cellpadding='3'>"
            "<tr><td><b>Double-click</b></td><td>— place the aperture centre</td></tr>"
            "<tr><td><b>Double-click + hold + drag</b></td><td>— draw the ellipse in one motion</td></tr>"
            "<tr><td><b>Double-click then click + drag</b></td><td>— alternative two-step draw</td></tr>"
            "<tr><td><b>Double-click inside aperture</b></td><td>— edit semi-axes &amp; position angle</td></tr>"
            "<tr><td><b>Double-click outside aperture</b></td><td>— clear it</td></tr>"
            "</table>"
            "<br>Drag horizontally for a wide ellipse, vertically for a tall one, "
            "or diagonally for both axes set independently."
        )

    def _show_about(self):
        QMessageBox.about(
            self, "About Faraday Explorer",
            "<h3>Faraday Explorer</h3>"
            "<p>Interactive Faraday depth polarisation model viewer "
            "for radio astronomy.</p>"
            "<p>Compares the ten polarisation models defined by "
            "<b>RM-Tools</b> against real Faraday Dispersion Function "
            "data extracted from FITS image cubes.</p>"
            "<p><b>Faraday Explorer:</b><br>"
            "<a href='https://github.com/NJRSAM003/FaradayExplorer'>"
            "github.com/NJRSAM003/FaradayExplorer</a></p>"
            "<p><b>RM-Tools</b> (model definitions and RM-synthesis reference):<br>"
            "<a href='https://github.com/CIRADA-Tools/RM-Tools'>"
            "github.com/CIRADA-Tools/RM-Tools</a></p>"
        )

    def _apply_default_sizes(self):
        """Left column = 1/3 width (ctrl:map = 1:2 vertically), right column = 2/3 (QU:FDF = 1:1)."""
        w = self.width()
        h = self.height()
        left_w  = w // 3
        right_w = w - left_w
        if self.has_data:
            self.resizeDocks([self._ctrl_dock, self._map_dock],
                             [h // 3, (h * 2) // 3], Qt.Vertical)
            self.resizeDocks([self._map_dock], [left_w], Qt.Horizontal)
        else:
            self.resizeDocks([self._ctrl_dock], [left_w], Qt.Horizontal)
        self.resizeDocks([self._qu_dock, self._fdf_dock],
                         [h // 2, h // 2], Qt.Vertical)
        self.resizeDocks([self._qu_dock], [right_w], Qt.Horizontal)

    def _open_new(self):
        """Show the file-picker dialog and reopen with new data."""
        dlg = LaunchDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        p = dlg.paths
        ok, beam_info = validate_inputs(p)
        if not ok:
            return
        ms = p.get("map_step", MAP_STEP)
        loading = LoadingDialog(p, ms, self)
        if loading.exec_() != QDialog.Accepted:
            if loading.error_msg:
                QMessageBox.critical(self, "Load Failed", loading.error_msg)
            return
        freqs = np.loadtxt(p["freq"])
        win = MainWindow(p["fdf"], p["i"], p["q"], p["u"], freqs,
                         map_step=ms, beam_info=beam_info,
                         full_stokes_path=p.get("full_stokes"),
                         _preloaded=loading.result_data)
        win.show()
        self.close()

    def _restore_layout(self):
        """Bring all dock panels back to their default docked positions."""
        for d in (self._ctrl_dock, self._qu_dock, self._fdf_dock,
                  getattr(self, '_map_dock', None)):
            if d is not None:
                d.setFloating(False)
                d.setVisible(True)

        self.addDockWidget(Qt.LeftDockWidgetArea,  self._ctrl_dock)
        if self.has_data:
            self.addDockWidget(Qt.LeftDockWidgetArea, self._map_dock)
            self.splitDockWidget(self._ctrl_dock, self._map_dock, Qt.Vertical)
        self.addDockWidget(Qt.RightDockWidgetArea, self._qu_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self._fdf_dock)
        self.splitDockWidget(self._qu_dock, self._fdf_dock, Qt.Vertical)

        QTimer.singleShot(0, self._apply_default_sizes)

    def _get_current_workspace_data(self):
        """Capture complete application state: model, parameters, aperture, zoom, clipping, display settings."""
        n = len(MODEL_PARAMS[self.model])
        params = [self._param_widgets[i].value() for i in range(n)]

        # Aperture state
        aperture_data = None
        if self.map_canvas and hasattr(self.map_canvas, '_patch') and self.map_canvas._patch is not None:
            patch = self.map_canvas._patch
            cx, cy = patch.center
            aperture_data = {
                "cx": float(cx),
                "cy": float(cy),
                "semi_major": float(patch.width / 2),
                "semi_minor": float(patch.height / 2),
                "angle": float(patch.angle),
            }

        # Image zoom/pan state
        image_zoom = None
        if self.map_canvas:
            xlim = self.map_canvas.ax.get_xlim()
            ylim = self.map_canvas.ax.get_ylim()
            image_zoom = {
                "xlim": [float(xlim[0]), float(xlim[1])],
                "ylim": [float(ylim[0]), float(ylim[1])],
            }

        # Image clipping and colormap settings
        image_settings = {
            "colormap": self._map_cmap_cb.currentText(),
            "clipping_pct": float(self._map_clip_cb.currentData()),
        }

        # Pane layout state (QMainWindow dock/toolbar configuration)
        import base64
        layout_state_bytes = self.saveState()
        layout_state_b64 = base64.b64encode(layout_state_bytes).decode('ascii')

        return {
            "model": self.model,
            "params": params,
            "normalise": self._normalise_cb.isChecked(),
            "convolve": self._convolve_cb.isChecked(),
            "model_scale": self._model_scale_spin.value(),
            "reveal_hidden": self._reveal_hidden_cb.isChecked(),
            "show_total_model": self._show_total_model_cb.isChecked(),
            "show_peak_lines": self._show_peak_lines,
            "show_peak_labels": self._show_peak_labels,
            "show_rmsf": self._show_rmsf,
            "fix_ymax": self._fix_ymax_cb.isChecked(),
            "ymax_value": self._ymax_spin.value(),
            "aperture": aperture_data,
            "image_zoom": image_zoom,
            "image_settings": image_settings,
            "layout_state": layout_state_b64,
        }

    def _apply_workspace_data(self, ws_data):
        """Restore complete application state from workspace: model, parameters, aperture, zoom, clipping, display."""
        if not ws_data:
            return

        # Restore model and parameters
        self._on_model(ws_data.get("model", "m1"))
        params = ws_data.get("params", [])
        for i, val in enumerate(params):
            if i < len(self._param_widgets):
                self._param_widgets[i].spin.setValue(float(val))

        # Restore FDF display settings
        self._normalise_cb.setChecked(ws_data.get("normalise", True))
        self._convolve_cb.setChecked(ws_data.get("convolve", True))
        self._model_scale_spin.setValue(ws_data.get("model_scale", 1.0))
        self._reveal_hidden_cb.setChecked(ws_data.get("reveal_hidden", False))
        self._show_total_model_cb.setChecked(ws_data.get("show_total_model", True))
        self._show_peak_lines = ws_data.get("show_peak_lines", True)
        self._show_peak_labels = ws_data.get("show_peak_labels", True)
        self._show_rmsf = ws_data.get("show_rmsf", True)
        self._fix_ymax_cb.setChecked(ws_data.get("fix_ymax", False))
        self._ymax_spin.setValue(ws_data.get("ymax_value", 0.010))

        # Restore image settings (colormap, clipping)
        image_settings = ws_data.get("image_settings", {})
        if image_settings:
            colormap = image_settings.get("colormap")
            clipping_pct = image_settings.get("clipping_pct")
            if colormap:
                idx = self._map_cmap_cb.findText(colormap)
                if idx >= 0:
                    self._map_cmap_cb.setCurrentIndex(idx)
            if clipping_pct:
                idx = self._map_clip_cb.findData(clipping_pct)
                if idx >= 0:
                    self._map_clip_cb.setCurrentIndex(idx)

        # Restore aperture if it was saved
        aperture_data = ws_data.get("aperture")
        if aperture_data and self.map_canvas:
            cx = aperture_data.get("cx")
            cy = aperture_data.get("cy")
            semi_major = aperture_data.get("semi_major")
            semi_minor = aperture_data.get("semi_minor")
            angle = aperture_data.get("angle")
            if all(v is not None for v in [cx, cy, semi_major, semi_minor, angle]):
                # Create and set the aperture patch
                import matplotlib.patches as mpatches
                patch = mpatches.Ellipse(
                    (cx, cy), 2 * semi_major, 2 * semi_minor,
                    angle=angle, fill=False, edgecolor="cyan", lw=1.5
                )
                if self.map_canvas._patch:
                    self.map_canvas._patch.remove()
                self.map_canvas.ax.add_patch(patch)
                self.map_canvas._patch = patch
                self.map_canvas._aperture_finalised = True

        # Restore image zoom/pan
        image_zoom = ws_data.get("image_zoom")
        if image_zoom and self.map_canvas:
            xlim = image_zoom.get("xlim")
            ylim = image_zoom.get("ylim")
            if xlim and ylim:
                self.map_canvas.ax.set_xlim(xlim)
                self.map_canvas.ax.set_ylim(ylim)

        # Restore pane layout (dock widgets, toolbars, pane positions/sizes)
        layout_state = ws_data.get("layout_state")
        if layout_state:
            import base64
            try:
                layout_state_bytes = base64.b64decode(layout_state.encode('ascii'))
                self.restoreState(layout_state_bytes)
            except Exception as e:
                print(f"[WARN] Failed to restore layout state: {e}")

        self._update()

    def _save_workspace_dialog(self):
        """Show dialog to save current workspace."""
        if not self.has_data:
            QMessageBox.warning(self, "No Data", "Load a dataset first.")
            return

        name, ok = QInputDialog.getText(
            self, "Save Workspace", "Enter workspace name:", QLineEdit.Normal
        )
        if not ok or not name.strip():
            return

        name = name.strip()
        ws_data = self._get_current_workspace_data()
        success, msg = Workspace.save_workspace(
            self._fdf_path, name, ws_data["model"], ws_data["params"],
            {k: v for k, v in ws_data.items() if k not in ["model", "params"]}
        )
        if success:
            self._workspace_dirty = False  # Mark as saved
            self._populate_load_workspace_menu()  # Refresh the Load Workspace submenu
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Error", msg)

    def _load_workspace_dialog(self):
        """Show dialog to load a saved workspace."""
        if not self.has_data:
            QMessageBox.warning(self, "No Data", "Load a dataset first.")
            return

        workspaces = Workspace.list_workspaces(self._fdf_path)
        if not workspaces:
            QMessageBox.information(self, "No Workspaces",
                                  "No saved workspaces for this dataset.")
            return

        ws_names = [w.replace('.json', '') for w in workspaces]
        name, ok = QInputDialog.getItem(
            self, "Load Workspace", "Select workspace:", ws_names, 0, False
        )
        if not ok:
            return

        ws_data = Workspace.load_workspace(self._fdf_path, name)
        if ws_data:
            self._apply_workspace_data(ws_data)
            self._workspace_dirty = False  # Mark as clean after loading
            QMessageBox.information(self, "Success", f"Workspace '{name}' loaded.")
        else:
            QMessageBox.critical(self, "Error", "Failed to load workspace.")

    def _populate_load_workspace_menu(self):
        """Populate Load Workspace submenu with available workspaces."""
        if not self.has_data:
            return

        self._load_menu.clear()

        workspaces = Workspace.list_workspaces(self._fdf_path)
        if not workspaces:
            self._load_menu.addAction("(No workspaces)").setEnabled(False)
            return

        ws_names = [w.replace('.json', '') for w in workspaces]
        for ws_name in ws_names:
            action = self._load_menu.addAction(ws_name)
            # Use lambda with default argument to capture current ws_name
            action.triggered.connect(lambda checked, name=ws_name: self._load_workspace_by_name(name))

    def _load_workspace_by_name(self, name):
        """Load a workspace by name."""
        ws_data = Workspace.load_workspace(self._fdf_path, name)
        if ws_data:
            self._apply_workspace_data(ws_data)
            self._workspace_dirty = False  # Mark as clean after loading
        else:
            QMessageBox.critical(self, "Error", f"Failed to load workspace '{name}'.")

    def _manage_workspaces_dialog(self):
        """Show dialog to manage (delete) workspaces."""
        if not self.has_data:
            QMessageBox.warning(self, "No Data", "Load a dataset first.")
            return

        workspaces = Workspace.list_workspaces(self._fdf_path)
        if not workspaces:
            QMessageBox.information(self, "No Workspaces",
                                  "No saved workspaces for this dataset.")
            return

        ws_names = [w.replace('.json', '') for w in workspaces]
        name, ok = QInputDialog.getItem(
            self, "Delete Workspace", "Select workspace to delete:", ws_names, 0, False
        )
        if not ok:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete", f"Delete workspace '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if Workspace.delete_workspace(self._fdf_path, name):
                QMessageBox.information(self, "Success", f"Workspace '{name}' deleted.")
            else:
                QMessageBox.critical(self, "Error", "Failed to delete workspace.")

    def _load_model_dialog(self):
        """Open file dialog to load a .mod file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Model File",
            os.path.expanduser("~"),
            "Model Files (*.mod);;All Files (*.*)"
        )
        if not path:
            return

        model, params, error = load_model_file(path)
        if error:
            QMessageBox.critical(self, "Error", error)
            return

        # Set the model and parameters
        self.model_combo.setCurrentText(model)
        self._on_model(model)  # Reconfigure param widgets

        # Load parameter values
        for i, val in enumerate(params):
            if i < len(self._param_widgets):
                self._param_widgets[i].spin.setValue(float(val))

        QMessageBox.information(
            self,
            "Success",
            f"Model '{model}' loaded from {os.path.basename(path)}"
        )

    def _save_model_dialog(self):
        """Open file dialog to save current model as .mod file."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Model File",
            os.path.expanduser("~"),
            "Model Files (*.mod);;All Files (*.*)"
        )
        if not path:
            return

        # Ensure .mod extension
        if not path.endswith('.mod'):
            path += '.mod'

        params = self._get_vals()
        success, msg = save_model_file(path, self.model, params)

        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Error", msg)

    def closeEvent(self, event):
        """Prompt to save workspace before closing if parameters have changed."""
        if self.has_data and self._workspace_dirty:
            reply = QMessageBox.question(
                self, "Save Workspace?",
                "You have unsaved parameter changes.\n\nWould you like to save this as a workspace?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.Save:
                # Show save dialog
                name, ok = QInputDialog.getText(
                    self, "Save Workspace", "Enter workspace name:",
                    QLineEdit.Normal, ""
                )
                if ok and name.strip():
                    name = name.strip()
                    ws_data = self._get_current_workspace_data()
                    success, msg = Workspace.save_workspace(
                        self._fdf_path, name, ws_data["model"], ws_data["params"],
                        {k: v for k, v in ws_data.items() if k not in ["model", "params"]}
                    )
                    if success:
                        self._workspace_dirty = False
                else:
                    if QMessageBox.question(self, "Close Without Saving",
                                          "Close without saving?",
                                          QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                        event.ignore()
                        return

        event.accept()

    def _build_controls(self):
        panel = QWidget()
        panel.setMinimumWidth(340)
        vbox  = QVBoxLayout(panel)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(6)

        # Model selector
        grp = QGroupBox("Model")
        grp.setFont(QFont("", 9, QFont.Bold))
        g = QVBoxLayout(grp)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(80)
        self.model_combo.addItems(list(MODEL_PARAMS.keys()))
        self.model_combo.currentTextChanged.connect(self._on_model)
        g.addWidget(self.model_combo)

        # Load/Save model buttons
        btn_layout = QHBoxLayout()
        self.load_model_btn = QPushButton("Load .mod")
        self.load_model_btn.setMaximumWidth(120)
        self.load_model_btn.clicked.connect(self._load_model_dialog)
        self.load_model_btn.setToolTip("Load model parameters from a .mod file")
        btn_layout.addWidget(self.load_model_btn)

        self.save_model_btn = QPushButton("Save .mod")
        self.save_model_btn.setMaximumWidth(120)
        self.save_model_btn.clicked.connect(self._save_model_dialog)
        self.save_model_btn.setToolTip("Save current model and parameters to a .mod file")
        btn_layout.addWidget(self.save_model_btn)
        btn_layout.addStretch()
        g.addLayout(btn_layout)

        vbox.addWidget(grp)

        # Parameters
        param_grp = QGroupBox("Parameters   [ min ←slider→ max ]")
        param_grp.setFont(QFont("", 9, QFont.Bold))
        pv = QVBoxLayout(param_grp)
        pv.setSpacing(3)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self._param_layout = QVBoxLayout(inner)
        self._param_layout.setSpacing(3)
        self._param_layout.setContentsMargins(2, 2, 2, 2)
        scroll.setWidget(inner)
        pv.addWidget(scroll)
        vbox.addWidget(param_grp, stretch=1)

        # Pre-create MAX_SLIDERS param widgets
        MAX = max(len(v) for v in MODEL_PARAMS.values())
        self._param_widgets = []
        for i in range(MAX):
            lbl, vmin, vmax, vinit = ("—", 0, 1, 0)
            pw = ParamWidget(lbl, vmin, vmax, vinit)
            pw.valueChanged.connect(self._schedule_update)
            # Connect slider/spinbox interactions to highlight
            pw.slider.sliderPressed.connect(lambda idx=i: self._highlight_param(idx))
            pw.spin.focusInEvent = lambda ev, idx=i, pw=pw: self._on_param_focus(idx, pw, ev)
            self._param_layout.addWidget(pw)
            self._param_widgets.append(pw)
        self._param_layout.addStretch()

        self._configure_params()

        # ── FDF display options ───────────────────────────────────────────────
        disp_grp = QGroupBox("FDF Display")
        disp_layout = QVBoxLayout(disp_grp)

        self._convolve_cb = QCheckBox("Convolve model with Faraday beam (RMSF)")
        self._convolve_cb.setChecked(True)
        self._convolve_cb.setToolTip(
            "ON  — model is convolved with the real RMSF (as observed)\n"
            "OFF — intrinsic Faraday spectrum: thin screens → narrow spike,\n"
            "       dispersed screens → Gaussian in φ, Burn slabs → tophat.\n"
            "       Use this to compare the ideal model shape with the data."
        )
        self._convolve_cb.toggled.connect(self._schedule_update)
        disp_layout.addWidget(self._convolve_cb)

        self._normalise_cb = QCheckBox("Normalise model to data peak")
        self._normalise_cb.setChecked(True)
        self._normalise_cb.setToolTip(
            "ON  — model FDF scaled so its peak matches the data peak\n"
            "       (model shown in Jy/beam/RMSF units;  RMSF at 0.5 × data peak)\n"
            "OFF — model shown in fractional polarisation (0–1)\n"
            "       (manual RMSF scale control appears below)"
        )
        self._normalise_cb.toggled.connect(self._on_normalise_toggled)
        disp_layout.addWidget(self._normalise_cb)

        self._reveal_hidden_cb = QCheckBox("Reveal hidden")
        self._reveal_hidden_cb.setChecked(False)
        self._reveal_hidden_cb.setToolTip(
            "Show individual component peaks overlaid with different colors.\n"
            "Useful for multi-component models (M3, M4, M111) where peaks may overlap.\n"
            "The combined total is rendered above individual components so both are visible."
        )
        self._reveal_hidden_cb.toggled.connect(self._schedule_update)
        disp_layout.addWidget(self._reveal_hidden_cb)

        self._show_total_model_cb = QCheckBox("Show total model")
        self._show_total_model_cb.setChecked(True)
        self._show_total_model_cb.setEnabled(False)  # Only enable when reveal_hidden is ON
        self._show_total_model_cb.setToolTip(
            "Display the combined total model line (black).\n"
            "Only visible when 'Reveal hidden' is enabled.\n"
            "Toggle to show/hide the combined model envelope."
        )
        self._show_total_model_cb.toggled.connect(self._schedule_update)
        disp_layout.addWidget(self._show_total_model_cb)

        # Connect reveal_hidden to enable/disable show_total_model checkbox
        self._reveal_hidden_cb.toggled.connect(self._show_total_model_cb.setEnabled)

        # Y-axis scaling for FDF plot
        self._fix_ymax_cb = QCheckBox("Fix y-axis max")
        self._fix_ymax_cb.setChecked(False)
        self._fix_ymax_cb.setToolTip("Lock the y-axis maximum to a fixed value for consistent scaling across plots")
        self._fix_ymax_cb.toggled.connect(self._schedule_update)
        disp_layout.addWidget(self._fix_ymax_cb)

        ymax_hbox = QHBoxLayout()
        ymax_hbox.setContentsMargins(20, 0, 0, 0)  # Indent under checkbox
        ymax_hbox.addWidget(QLabel("Max value:"))
        self._ymax_spin = QDoubleSpinBox()
        self._ymax_spin.setRange(0.001, 1e6)
        self._ymax_spin.setDecimals(4)
        self._ymax_spin.setSingleStep(0.01)
        self._ymax_spin.setValue(0.010)
        self._ymax_spin.setEnabled(False)  # Only enable when fix_ymax is checked
        self._ymax_spin.valueChanged.connect(self._schedule_update)
        ymax_hbox.addWidget(self._ymax_spin)
        ymax_hbox.addStretch()

        ymax_widget = QWidget()
        ymax_widget.setLayout(ymax_hbox)
        disp_layout.addWidget(ymax_widget)

        # Connect fix_ymax checkbox to enable/disable spinbox
        self._fix_ymax_cb.toggled.connect(self._ymax_spin.setEnabled)

        # Manual model scale — visible only when normalise=OFF
        self._model_scale_row = QWidget()
        ms_hbox = QHBoxLayout(self._model_scale_row)
        ms_hbox.setContentsMargins(0, 0, 0, 0)
        ms_hbox.addWidget(QLabel("Model scale:"))
        self._model_scale_spin = QDoubleSpinBox()
        self._model_scale_spin.setRange(0, 1e12)
        self._model_scale_spin.setDecimals(6)
        self._model_scale_spin.setSingleStep(0.0001)
        self._model_scale_spin.setValue(1.0)
        self._model_scale_spin.setSuffix("")
        self._model_scale_spin.setToolTip(
            "Manually scale the model FDF amplitude to match the data.\n"
            "RMSF is always shown normalised (peak = 1) on the right y-axis."
        )
        self._model_scale_spin.valueChanged.connect(self._schedule_update)
        ms_hbox.addWidget(self._model_scale_spin)
        self._model_scale_row.setVisible(False)
        disp_layout.addWidget(self._model_scale_row)

        vbox.addWidget(disp_grp)

        # Defer timer for batching rapid slider moves
        self._update_timer = QTimer(singleShot=True)
        self._update_timer.timeout.connect(self._update)

        return panel

    def _build_qu_panel(self):
        holder = QWidget()
        v = QVBoxLayout(holder)
        v.setContentsMargins(0, 0, 0, 0)
        self.qu_fig    = Figure(facecolor="#fafafa")
        self.qu_canvas = FigureCanvas(self.qu_fig)
        self.qu_ax     = self.qu_fig.add_subplot(111)
        # Skip toolbar due to matplotlib icon rendering issues on macOS
        # Users can zoom/pan with scroll wheel and spacebar-drag
        v.addWidget(self.qu_canvas)
        return holder

    def _build_fdf_panel(self):
        holder = QWidget()
        v = QVBoxLayout(holder)
        v.setContentsMargins(0, 0, 0, 0)
        self.fdf_fig    = Figure(facecolor="#fafafa")
        self.fdf_canvas = FigureCanvas(self.fdf_fig)
        self.fdf_ax     = self.fdf_fig.add_subplot(111)

        # Display controls row (toolbar removed due to matplotlib icon rendering issues on macOS)
        # Users can zoom/pan with scroll wheel and spacebar-drag
        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(4)
        toolbar_row.addStretch()

        display_btn = QToolButton()
        display_btn.setText("Display ▾")
        display_btn.setPopupMode(QToolButton.InstantPopup)
        display_btn.setStyleSheet(
            "QToolButton { padding: 3px 8px; font-size: 9pt; }"
            "QToolButton::menu-indicator { image: none; }"
        )
        menu = QMenu(display_btn)

        act_lines  = QAction("Peak lines",  menu, checkable=True, checked=True)
        act_labels = QAction("Peak labels", menu, checkable=True, checked=True)
        act_rmsf   = QAction("RMSF shading", menu, checkable=True, checked=True)
        menu.addAction(act_lines)
        menu.addAction(act_labels)
        menu.addAction(act_rmsf)

        def _toggle_lines(on):
            self._show_peak_lines = on
            self._update()
        def _toggle_labels(on):
            self._show_peak_labels = on
            self._update()
        def _toggle_rmsf(on):
            self._show_rmsf = on
            self._update()

        act_lines.toggled.connect(_toggle_lines)
        act_labels.toggled.connect(_toggle_labels)
        act_rmsf.toggled.connect(_toggle_rmsf)

        display_btn.setMenu(menu)
        toolbar_row.addWidget(display_btn)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_row)
        v.addWidget(toolbar_widget)
        v.addWidget(self.fdf_canvas)
        return holder

    def _build_map_panel(self):
        """Wrap MapCanvas with cube-selector dropdown and channel slider."""
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(2)

        # ── Controls row ──────────────────────────────────────────────────────
        ctrl = QWidget()
        hbox = QHBoxLayout(ctrl)
        hbox.setContentsMargins(0, 0, 0, 0)

        hbox.addWidget(QLabel("Display:"))
        self._map_cube_cb = QComboBox()
        self._map_cube_cb.addItem("FDF — peak map",   "fdf_peak")
        self._map_cube_cb.addItem("FDF — φ slice",    "fdf_slice")
        if self.has_qu:
            self._map_cube_cb.addItem("Stokes I",     "stokes_i")
            self._map_cube_cb.addItem("Stokes Q",     "stokes_q")
            self._map_cube_cb.addItem("Stokes U",     "stokes_u")
        hbox.addWidget(self._map_cube_cb)

        hbox.addWidget(QLabel(" Ch:"))
        self._map_ch_slider = QSlider(Qt.Horizontal)
        self._map_ch_slider.setMinimum(0)
        self._map_ch_slider.setMaximum(0)
        self._map_ch_slider.setValue(0)
        self._map_ch_slider.setEnabled(False)
        self._map_ch_slider.setFixedWidth(90)
        hbox.addWidget(self._map_ch_slider)

        self._map_ch_lbl = QLabel("—")
        self._map_ch_lbl.setFixedWidth(80)
        hbox.addWidget(self._map_ch_lbl)
        hbox.addStretch()

        vbox.addWidget(ctrl)

        # ── Second control row: axes / colormap / clipping ───────────────────
        ctrl2 = QWidget()
        hbox2 = QHBoxLayout(ctrl2)
        hbox2.setContentsMargins(0, 0, 0, 0)

        hbox2.addWidget(QLabel("Axes:"))
        self._map_axes_cb = QComboBox()
        self._map_axes_cb.setMinimumWidth(100)
        self._map_axes_cb.addItem("Pixel",     "pixel")
        self._map_axes_cb.addItem("WCS (deg)", "wcs_deg")
        self._map_axes_cb.addItem("WCS (hms)", "wcs_hms")
        if self.wcs2d is None:
            self._map_axes_cb.setEnabled(False)
            self._map_axes_cb.setToolTip("No WCS in FDF header")
        hbox2.addWidget(self._map_axes_cb)

        hbox2.addWidget(QLabel("Cmap:"))
        self._map_cmap_cb = QComboBox()
        self._map_cmap_cb.setMinimumWidth(100)
        for cm in ("inferno", "viridis", "plasma", "magma",
                   "cividis", "gray", "hot", "RdBu_r"):
            self._map_cmap_cb.addItem(cm)
        hbox2.addWidget(self._map_cmap_cb)

        hbox2.addWidget(QLabel("Clip:"))
        self._map_clip_cb = QComboBox()
        self._map_clip_cb.setMinimumWidth(80)  # Ensure full text visibility
        for pct in (99.5, 99.0, 95.0, 99.9, 99.95, 99.99, 100.0):
            self._map_clip_cb.addItem(f"{pct}%", pct)
        hbox2.addWidget(self._map_clip_cb)
        hbox2.addStretch()

        vbox.addWidget(ctrl2)

        # ── Third control row: aperture tools ──────────────────────────────
        ctrl3 = QWidget()
        hbox3 = QHBoxLayout(ctrl3)
        hbox3.setContentsMargins(0, 0, 0, 0)

        hbox3.addWidget(QLabel("Aperture:"))
        coord_btn = QPushButton("By Coordinates…")
        coord_btn.setToolTip("Enter aperture center and dimensions via coordinates")
        coord_btn.clicked.connect(self._open_coordinate_aperture)
        hbox3.addWidget(coord_btn)

        self._aperture_lock_btn = QPushButton("🔓")
        self._aperture_lock_btn.setFixedWidth(40)
        self._aperture_lock_btn.setToolTip("Lock/unlock aperture for dragging (click to toggle)\n🔓 = Unlocked (can drag), 🔒 = Locked (fixed)")
        self._aperture_lock_btn.setEnabled(False)
        self._aperture_lock_btn.clicked.connect(self._toggle_aperture_lock)
        hbox3.addWidget(self._aperture_lock_btn)
        hbox3.addStretch()

        vbox.addWidget(ctrl3)
        vbox.addWidget(self.map_canvas, stretch=1)

        self._map_cube_cb.currentIndexChanged.connect(self._on_map_cube_changed)
        self._map_ch_slider.valueChanged.connect(self._on_map_channel_changed)
        self._map_axes_cb.currentIndexChanged.connect(self._apply_axes_format)
        self._map_cmap_cb.currentIndexChanged.connect(self._on_cmap_changed)
        self._map_clip_cb.currentIndexChanged.connect(self._update_map_image)

        return container

    def _on_cmap_changed(self, _idx):
        self.map_canvas.ax.images[0].set_cmap(self._map_cmap_cb.currentText())
        self.map_canvas.draw_idle()

    def _apply_axes_format(self, _idx=None):
        """Switch the map x/y tick labels between pixel and WCS coordinates."""
        from matplotlib.ticker import FuncFormatter, ScalarFormatter
        ax   = self.map_canvas.ax
        mode = self._map_axes_cb.currentData()
        ms   = self.map_step
        if mode == "pixel" or self.wcs2d is None:
            ax.xaxis.set_major_formatter(ScalarFormatter())
            ax.yaxis.set_major_formatter(ScalarFormatter())
            ax.set_xlabel("RA pixel (downsampled)",  fontsize=7, color="white")
            ax.set_ylabel("Dec pixel (downsampled)", fontsize=7, color="white")
        else:
            wcs = self.wcs2d
            if mode == "wcs_deg":
                def fx(x, p):
                    ra, _ = wcs.all_pix2world(x * ms, 0, 0)
                    return f"{float(ra):.4f}°"
                def fy(y, p):
                    _, dec = wcs.all_pix2world(0, y * ms, 0)
                    return f"{float(dec):+.4f}°"
            else:  # wcs_hms
                from astropy.coordinates import Angle
                import astropy.units as u
                def fx(x, p):
                    ra, _ = wcs.all_pix2world(x * ms, 0, 0)
                    return Angle(float(ra), unit=u.deg).to_string(
                        unit=u.hour, sep=":", precision=1, pad=True)
                def fy(y, p):
                    _, dec = wcs.all_pix2world(0, y * ms, 0)
                    return Angle(float(dec), unit=u.deg).to_string(
                        sep=":", precision=1, alwayssign=True, pad=True)
            ax.xaxis.set_major_formatter(FuncFormatter(fx))
            ax.yaxis.set_major_formatter(FuncFormatter(fy))
            ax.set_xlabel("RA",  fontsize=7, color="white")
            ax.set_ylabel("Dec", fontsize=7, color="white")
        self.map_canvas.draw_idle()

    def _on_map_cube_changed(self, _idx):
        key = self._map_cube_cb.currentData()
        if key == "fdf_peak":
            self._map_ch_slider.setEnabled(False)
            self._map_ch_lbl.setText("—")
        elif key == "fdf_slice":
            n = self.fdf_data.shape[0]
            self._map_ch_slider.setMaximum(n - 1)
            self._map_ch_slider.setValue(n // 2)
            self._map_ch_slider.setEnabled(True)
        else:  # Stokes
            n = self.i_data.shape[0]
            self._map_ch_slider.setMaximum(n - 1)
            self._map_ch_slider.setValue(0)
            self._map_ch_slider.setEnabled(True)
        self._update_map_image()

    @staticmethod
    def _fmt_phi(val):
        """Format a phi value with appropriate units based on its magnitude."""
        mag = abs(val)
        if mag >= 1e8:
            return f"{val/1e9:.3f} GHz"
        if mag >= 1e5:
            return f"{val/1e6:.3f} MHz"
        return f"{val:.1f} rad/m²"

    def _on_map_channel_changed(self, ch):
        key = self._map_cube_cb.currentData()
        if key == "fdf_slice":
            self._map_ch_lbl.setText(self._fmt_phi(float(self.phi_data[ch])))
        else:
            self._map_ch_lbl.setText(f"{self.freqs[ch]/1e9:.3f} GHz")
        self._update_map_image()

    def _update_map_image(self, *_):
        key = self._map_cube_cb.currentData()
        ch  = self._map_ch_slider.value()
        ms  = self.map_step
        if key == "fdf_peak":
            img = self.peak_map   # already computed during load — never recompute
        elif key == "fdf_slice":
            img = np.abs(self.fdf_data[ch, ::ms, ::ms])
        elif key == "stokes_i":
            img = self.i_data[ch, ::ms, ::ms]
        elif key == "stokes_q":
            img = self.q_data[ch, ::ms, ::ms]
        else:
            img = self.u_data[ch, ::ms, ::ms]

        pct_hi = float(self._map_clip_cb.currentData())
        # Symmetric "lower tail" — drop the same fraction off the bottom
        pct_lo = max(0.0, 100.0 - pct_hi)
        vlo = float(np.nanpercentile(img, pct_lo))
        vhi = float(np.nanpercentile(img, pct_hi))
        if vhi <= vlo:
            vhi = vlo + 1e-12

        im = self.map_canvas.ax.images[0]
        im.set_data(img)
        im.set_clim(vlo, vhi)
        im.set_cmap(self._map_cmap_cb.currentText())
        self.map_canvas.draw_idle()

    # ── Parameter widget management ───────────────────────────────────────────

    def _configure_params(self):
        params = MODEL_PARAMS[self.model]
        n = len(params)
        for i, pw in enumerate(self._param_widgets):
            if i < n:
                lbl, vmin, vmax, vinit = params[i]
                pw.reconfigure(lbl, vmin, vmax, vinit)
                pw.setVisible(True)
            else:
                pw.setVisible(False)
        # Clear any highlighted parameter
        self._unhighlight_all_params()

    def _highlight_param(self, idx):
        """Highlight a parameter when user interacts with its slider."""
        self._unhighlight_all_params()
        if idx < len(self._param_widgets):
            self._param_widgets[idx].set_highlighted(True, theme=self.theme)

    def _on_param_focus(self, idx, pw, event):
        """Handle focus in on parameter spinbox."""
        self._unhighlight_all_params()
        pw.set_highlighted(True, theme=self.theme)
        # Call original focusInEvent
        pw.spin.focusInEvent.__wrapped__(event) if hasattr(pw.spin.focusInEvent, '__wrapped__') else None

    def _unhighlight_all_params(self):
        """Remove highlighting from all parameters."""
        for pw in self._param_widgets:
            pw.set_highlighted(False)

    def set_theme(self, theme_name):
        """Change the application theme and apply stylesheet."""
        self.theme = theme_name
        self.settings.setValue("theme", theme_name)

        # Apply stylesheet to entire app
        theme_dict = Theme.get_theme(theme_name)
        QApplication.instance().setStyleSheet(theme_dict["stylesheet"])

        # Update theme menu checkmarks
        if hasattr(self, "_theme_action_group"):
            for action in self._theme_action_group.actions():
                action.setChecked(action.text().lower() == theme_name.lower())

    def _get_vals(self):
        n = len(MODEL_PARAMS[self.model])
        return [self._param_widgets[i].value() for i in range(n)]

    def _rm_vals(self):
        vals = self._get_vals()
        return [vals[i] for i in RM_INDICES[self.model]]

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_model(self, label):
        self.model = label
        self._configure_params()
        self._update()

    def _on_normalise_toggled(self, checked):
        self._model_scale_row.setVisible(not checked)
        if not checked and self.real_fdf is not None:
            self._model_scale_spin.setValue(float(self.real_fdf.max()) /
                                            max(float(self._last_amax), 1e-30))
        self._schedule_update()

    def _open_coordinate_aperture(self):
        """Open non-modal coordinate aperture dialog for live adjustment.

        Dialog stays open so you can zoom/pan map while adjusting parameters.
        """
        if hasattr(self, '_coord_dialog') and self._coord_dialog is not None:
            self._coord_dialog.raise_()
            self._coord_dialog.activateWindow()
            return

        ms = self.map_step
        dlg = CoordinateApertureDialog(
            wcs_2d=self.wcs2d,
            map_canvas=self.map_canvas,
            pix_scale_ds=self.beam_info.get("pix_scale") * ms if self.beam_info else None,
            map_shape=self.peak_map.shape if hasattr(self, 'peak_map') else None,
            map_step=ms,
            parent=self
        )
        # Connect signals instead of using exec_()
        dlg.accepted.connect(self._finalize_coordinate_aperture)
        dlg.rejected.connect(lambda: self._cleanup_coord_dialog())

        self._coord_dialog = dlg
        dlg.show()  # Non-modal display

    def _finalize_coordinate_aperture(self):
        """Finalize aperture from non-modal dialog."""
        dlg = self._coord_dialog
        if dlg is None:
            return

        cx_px, cy_px, a_px, b_px, pa_deg = dlg.values()
        if cx_px is None or cy_px is None:
            self._cleanup_coord_dialog()
            return

        # Create mask and emit aperture
        ny, nx = self.peak_map.shape
        ys, xs = np.ogrid[0:ny, 0:nx]
        pa_rad = np.deg2rad(pa_deg)
        cos_a, sin_a = np.cos(pa_rad), np.sin(pa_rad)
        dx, dy = xs - cx_px, ys - cy_px
        x_rot = dx * cos_a + dy * sin_a
        y_rot = -dx * sin_a + dy * cos_a
        mask = (x_rot / a_px) ** 2 + (y_rot / b_px) ** 2 <= 1.0

        if mask.sum() > 0:
            # Update the map canvas patch to match the finalized aperture
            if self.map_canvas._patch:
                self.map_canvas._patch.remove()
            patch = mpatches.Ellipse(
                (cx_px, cy_px), width=2*a_px, height=2*b_px, angle=pa_deg,
                fill=False, edgecolor="cyan", lw=2.0, zorder=5)
            self.map_canvas.ax.add_patch(patch)
            self.map_canvas._patch = patch
            self.map_canvas._aperture_finalised = True
            self.map_canvas.draw_idle()

            # Process aperture as normal
            self._on_aperture(mask, float(cx_px), float(cy_px),
                            float(a_px), float(b_px), float(pa_deg))

        self._cleanup_coord_dialog()

    def _cleanup_coord_dialog(self):
        """Clean up the coordinate dialog."""
        if hasattr(self, '_coord_dialog') and self._coord_dialog is not None:
            self._coord_dialog.close()
            self._coord_dialog = None

    def _toggle_aperture_lock(self):
        """Toggle aperture lock state and update UI."""
        locked = self.map_canvas.toggle_aperture_lock()
        emoji = "🔒" if locked else "🔓"
        self._aperture_lock_btn.setText(emoji)

    def _on_aperture_cleared(self):
        self.real_fdf   = None
        self.real_q     = None
        self.real_u     = None
        self.real_label = None
        self._aperture_lock_btn.setEnabled(False)
        self._aperture_lock_btn.setText("🔓")
        self._update()

    def _schedule_update(self):
        self._workspace_dirty = True  # Mark workspace as unsaved
        self._update_timer.start(40)

    def _on_aperture(self, mask, cx, cy, a, b, pa):
        n_pix = int(mask.sum())
        ms    = self.map_step

        # Enable the lock/unlock button now that an aperture exists
        self._aperture_lock_btn.setEnabled(True)
        self._aperture_lock_btn.setText("🔓")

        # Show "computing…" in status bar immediately so the UI looks responsive.
        self.statusBar().showMessage("Computing aperture FDF…")
        QApplication.processEvents()

        # FDF extraction — chunked over phi slabs so the main thread yields
        # periodically on large cubes rather than blocking for seconds at a time.
        ds     = self.fdf_data[:, ::ms, ::ms]
        n_phi  = ds.shape[0]
        slab   = max(1, min(20, n_phi))
        sz     = max(1, (n_phi + slab - 1) // slab)
        accum  = None
        for s in range(0, n_phi, sz):
            chunk = np.asarray(ds[s:s+sz, ...])[:, mask].sum(axis=1)
            accum = chunk if accum is None else np.concatenate([accum, chunk])
            QApplication.processEvents()
        self.real_fdf = accum.astype(np.float64)

        pa_str = f"  PA={pa:.1f}°" if abs(pa) > 0.05 else ""
        bi = self.beam_info
        if bi and bi.get("pix_scale"):
            ps    = bi["pix_scale"] * ms
            a_arc = a * ps
            b_arc = b * ps
            bmaj  = bi.get("bmaj", 0)
            per_ch = bi.get("per_channel")
            beam_note = " [per-ch beams]" if per_ch is not None else ""
            if bmaj > 0:
                self.real_label = (f"aperture  {a_arc:.1f}\" × {b_arc:.1f}\"{pa_str}"
                                   f" ({a_arc/bmaj:.2f} × {b_arc/bmaj:.2f} beams{beam_note})")
                status_r = (f"{a_arc:.1f}\" × {b_arc:.1f}\"{pa_str}"
                            f" ({a_arc/bmaj:.2f} × {b_arc/bmaj:.2f} beams{beam_note})")
            else:
                self.real_label = f"aperture  {a_arc:.1f}\" × {b_arc:.1f}\"{pa_str}{beam_note}"
                status_r = f"{a_arc:.1f}\" × {b_arc:.1f}\"{pa_str}{beam_note}"
        else:
            self.real_label = f"aperture  {a:.1f} × {b:.1f} ds-px{pa_str}  ({n_pix} px)"
            status_r = f"{a:.1f} × {b:.1f} ds-px{pa_str}"

        # Pre-fill model scale spinbox when data arrives (used when normalise=OFF)
        if not self._normalise_cb.isChecked() and hasattr(self, '_last_amax'):
            self._model_scale_spin.blockSignals(True)
            self._model_scale_spin.setValue(
                float(self.real_fdf.max()) / max(float(self._last_amax), 1e-30))
            self._model_scale_spin.blockSignals(False)

        if self.has_qu:
            # Stokes extractions — each one a potentially large memmap read;
            # call processEvents() between them so the UI stays alive.
            QApplication.processEvents()
            I_sum = np.asarray(self.i_data[:, ::ms, ::ms])[:, mask].sum(axis=1).astype(np.float64)
            QApplication.processEvents()
            Q_sum = np.asarray(self.q_data[:, ::ms, ::ms])[:, mask].sum(axis=1).astype(np.float64)
            QApplication.processEvents()
            U_sum = np.asarray(self.u_data[:, ::ms, ::ms])[:, mask].sum(axis=1).astype(np.float64)
            QApplication.processEvents()
            safe = np.abs(I_sum) > 1e-10 * np.abs(I_sum).max()
            self.real_q = np.where(safe, Q_sum / I_sum, np.nan)
            self.real_u = np.where(safe, U_sum / I_sum, np.nan)

        # ── Sky coordinates of aperture centre via WCS ────────────────────────
        coord_str = ""
        if self.wcs2d is not None:
            try:
                native_x = float(cx) * self.map_step
                native_y = float(cy) * self.map_step
                ra_deg, dec_deg = self.wcs2d.all_pix2world(native_x, native_y, 0)
                # Format RA as hh:mm:ss, Dec as ±dd:mm:ss
                from astropy.coordinates import SkyCoord
                import astropy.units as u
                sc  = SkyCoord(ra=float(ra_deg)*u.deg, dec=float(dec_deg)*u.deg)
                ra_hms  = sc.ra.to_string(unit=u.hour, sep=":", precision=1, pad=True)
                dec_dms = sc.dec.to_string(sep=":", precision=1, alwayssign=True, pad=True)
                coord_str = f"  |  centre RA={ra_hms}  Dec={dec_dms}"
            except Exception:
                pass

        self.statusBar().showMessage(
            f"Aperture: {status_r}, {n_pix} pixels{coord_str}  |  model: {self.model}")
        self._update()

    # ── Plot update ───────────────────────────────────────────────────────────

    def _update(self):
        vals    = self._get_vals()
        P       = model_P(self.model, vals, self.lam2)
        freqs_G = self.freqs / 1e9

        if self._convolve_cb.isChecked():
            fdf  = rm_synthesis(P, self.lam2, self.phi)
            amp  = np.abs(fdf)
        else:
            intrinsic = model_fdf_clean(self.model, vals, self.phi, self.lam2)
            amp       = _gaussian_restore(intrinsic, self.phi, self.rmsf)
        amax = amp.max() if amp.max() > 0 else 1.0

        self._draw_qu(P, freqs_G)
        self._draw_fdf(amp, amax)

    def _draw_qu(self, P, freqs_G):
        ax = self.qu_ax
        ax.cla()
        ax.set_facecolor("#fdfdfd")
        ax.plot(freqs_G, P.real, color="royalblue",  lw=1.5, label="q model")
        ax.plot(freqs_G, P.imag, color="darkorange", lw=1.5, label="u model")
        ax.axhline(0, color="k", lw=0.5, ls=":", alpha=0.5)

        if self.has_qu and self.real_q is not None:
            ax.scatter(freqs_G, self.real_q, color="royalblue",  s=55,
                       marker="o", zorder=5, label="q data (Q/I)")
            ax.scatter(freqs_G, self.real_u, color="darkorange", s=55,
                       marker="s", zorder=5, label="u data (U/I)")

        ax.set_xlabel("Frequency  [GHz]")
        ax.set_ylabel("Fractional polarisation  (Q/I,  U/I)")
        ax.set_title(f"q & u vs Frequency  |  model {self.model}", loc="left", pad=8)
        # Place legend at top right above plot, horizontal orientation (multiple columns)
        ax.legend(fontsize=8, loc="upper right", bbox_to_anchor=(1.0, 1.15),
                 ncol=4, framealpha=0.9, frameon=True, borderpad=0.8)
        ax.grid(True, alpha=0.2)
        self.qu_fig.subplots_adjust(top=0.80)  # Make room for legend at top
        self.qu_canvas.draw_idle()

    def _draw_fdf(self, amp, amax):
        self._last_amax = amax   # cache for _on_normalise_toggled
        ax        = self.fdf_ax
        normalise = self._normalise_cb.isChecked()
        convolved = self._convolve_cb.isChecked()
        # Remove any stale twin axes from prior calls (prevents RMSF shade stacking)
        for axis in list(self.fdf_fig.axes):
            if axis is not ax:
                axis.remove()
        ax.cla()
        ax.set_facecolor("#fdfdfd")

        # ── Model amplitude: scale to data peak (ON) or manual spinbox (OFF) ──
        has_data = self.real_fdf is not None and self.real_fdf.max() > 0
        real_max = float(self.real_fdf.max()) if has_data else None

        beam_tag  = "" if convolved else "  [no RMSF]"
        if has_data and normalise and amax > 0:
            model_scale = real_max / amax
            model_lbl   = f"|FDF| model  (scaled to data peak){beam_tag}"
        elif not normalise:
            model_scale = self._model_scale_spin.value()
            model_lbl   = f"|FDF| model  (×{model_scale:.3g}){beam_tag}"
        else:
            model_scale = 1.0
            model_lbl   = f"|FDF| model{beam_tag}"

        model_amp  = amp * model_scale
        model_peak = amax * model_scale

        # ── Primary y-axis limits ─────────────────────────────────────────────
        ymax = max(model_peak, real_max) if has_data else model_peak
        if ymax <= 0:
            ymax = 1.0

        # ── Secondary (right) y-axis for normalised RMSF ─────────────────────
        # RMSF always plotted on ax2 with its natural 0–1 normalisation.
        # We set ax2 ylim so RMSF peak (1.0) appears at 50 % of plot height.
        ax2 = ax.twinx()
        ax2.set_ylim(0, 1.25)   # RMSF peak=1.0 at RM=0 with 0.25 headroom
        ax2.tick_params(axis='y', labelcolor="gray", labelsize=6)
        if self._show_rmsf:
            ax2.set_ylabel("RMSF  (normalised)", fontsize=7, color="gray")
            ax2.fill_between(self.phi, self.rmsf, alpha=0.15, color="gray", zorder=1)
            ax2.plot(self.phi, self.rmsf, color="gray", lw=0.8,
                     ls="--", alpha=0.55, label="RMSF (norm.)", zorder=1)
        # Draw RMSF behind the main data lines
        ax2.set_zorder(ax.get_zorder() - 1)
        ax.patch.set_visible(False)   # make ax background transparent so ax2 fill shows

        # ── RM reference lines ────────────────────────────────────────────────
        sub = "₁₂₃"
        for j, rm in enumerate(self._rm_vals()):
            ax.axvline(rm, color=RM_COLOURS[j % 3], lw=0.9, ls=":", alpha=0.65,
                       label=f"RM{sub[j]} input = {rm:+.2f}")

        # ── Model FDF with optional component decomposition ───────────────────
        reveal_hidden = self._reveal_hidden_cb.isChecked()

        if reveal_hidden:
            # Compute individual component FDFs
            vals = self._get_vals()
            component_colors = ["#d62728", "#2ca02c", "#ff7f0e"]  # Red, Green, Orange
            component_labels = ["Component 1", "Component 2", "Component 3"]

            try:
                P_components = model_P_components(self.model, vals, self.lam2)

                # For intrinsic mode: compute each component WITHOUT restoration first
                # so they can be displayed individually, then show the restored sum
                component_amps_restored = []

                # Plot each component with a different color
                for i, P_comp in enumerate(P_components):
                    if convolved:
                        comp_fdf = rm_synthesis(P_comp, self.lam2, self.phi)
                        comp_amp = np.abs(comp_fdf) * model_scale
                    else:
                        # For intrinsic: compute component intrinsic FDF with restoration
                        comp_amp_raw = model_fdf_clean_component(self.model, vals, self.phi, self.lam2, comp_idx=i)
                        comp_amp = _gaussian_restore(comp_amp_raw, self.phi, self.rmsf) * model_scale

                    component_amps_restored.append(comp_amp)
                    color = component_colors[i % len(component_colors)]
                    label = component_labels[i] if i < len(component_labels) else f"Comp {i+1}"
                    ax.plot(self.phi, comp_amp, color=color, lw=1.2, alpha=0.7, label=label)

                # Plot combined model (conditionally, when show_total_model is enabled)
                # This uses the correctly-computed model_amp from the _update method
                if self._show_total_model_cb.isChecked():
                    ax.plot(self.phi, model_amp, color="black", lw=2.0,
                            label=f"{model_lbl}", linestyle="-", zorder=10)

            except Exception as e:
                # Fallback: just plot the combined model if decomposition fails
                ax.plot(self.phi, model_amp, color="steelblue", lw=1.8, label=model_lbl)
        else:
            # Standard: just plot combined model
            ax.plot(self.phi, model_amp, color="steelblue", lw=1.8, label=model_lbl)

        dphi    = abs(self.phi[1] - self.phi[0]) if len(self.phi) > 1 else 0.5
        min_sep = max(1, int(15.0 / dphi))
        if model_peak > 0 and self._show_peak_lines:
            peaks, _ = find_peaks(model_amp, height=0.05*model_peak,
                                  prominence=0.20*model_peak, distance=min_sep)
            for pk in peaks:
                phi_pk, a_pk = self.phi[pk], model_amp[pk]
                ax.axvline(phi_pk, color="steelblue", lw=0.9, ls="--", alpha=0.7)
                ax.scatter([phi_pk], [a_pk], color="steelblue", s=40, zorder=6,
                           edgecolors="navy", lw=0.5)
                if self._show_peak_labels:
                    ax.annotate(f"φ={phi_pk:+.1f}", xy=(phi_pk, a_pk),
                                xytext=(5, 3), textcoords="offset points",
                                fontsize=7, color="steelblue",
                                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                          ec="steelblue", alpha=0.85, lw=0.5))

        # ── Real FDF overlay ──────────────────────────────────────────────────
        if has_data:
            real_amp = self.real_fdf
            data_lbl = "|FDF| data (Jy/RMSF)"
            ax.plot(self.phi_data, real_amp, color="darkorange", lw=1.5,
                    alpha=0.85, label=data_lbl)

            dphi_r = abs(self.phi_data[1] - self.phi_data[0])
            sep_r  = max(1, int(15.0 / dphi_r))
            rp, _  = find_peaks(real_amp, height=0.05*real_max,
                                 prominence=0.10*real_max, distance=sep_r)
            if self._show_peak_lines:
                for pk in rp:
                    phi_pk = self.phi_data[pk]
                    a_pk   = real_amp[pk]
                    ax.axvline(phi_pk, color="darkorange", lw=0.9, ls="-.", alpha=0.7)
                    ax.scatter([phi_pk], [a_pk], color="darkorange", s=35, zorder=6,
                               edgecolors="saddlebrown", lw=0.5)
                    if self._show_peak_labels:
                        ax.annotate(f"φ={phi_pk:+.0f}", xy=(phi_pk, a_pk),
                                    xytext=(-4, 8), textcoords="offset points",
                                    fontsize=7, color="darkorange",
                                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                              ec="darkorange", alpha=0.85, lw=0.5))

        norm_note = ("model scaled to data peak" if (has_data and normalise)
                     else f"model ×{model_scale:.3g}" if not normalise
                     else "model: fractional pol.")
        beam_note = "RMSF-convolved" if convolved else "intrinsic — no RMSF"
        ax.set_xlabel("Faraday Depth  φ  [rad m⁻²]")
        ax.set_ylabel(f"|FDF(φ)|  ({norm_note};  data: Jy/RMSF)")
        ax.set_title(f"FDF Comparison  |  model {self.model}  |  {beam_note}")

        # Combined legend from both axes
        lines1, labs1 = ax.get_legend_handles_labels()
        lines2, labs2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labs1 + labs2,
                  fontsize=7.5, loc="upper right", framealpha=0.85)

        ax.grid(True, alpha=0.2)
        # Auto-extend x-axis to include real data range.  If phi_data values
        # look like frequencies (> 1e5) rather than rad/m² the data is likely
        # from a frequency cube — warn once and use its range so at least the
        # profile is visible.
        if has_data and self.phi_data is not None:
            dlo = float(np.nanmin(self.phi_data))
            dhi = float(np.nanmax(self.phi_data))
            ax.set_xlim(min(PHI_MIN, dlo), max(PHI_MAX, dhi))
        else:
            ax.set_xlim(PHI_MIN, PHI_MAX)

        # Set y-axis limits (fixed or auto)
        if self._fix_ymax_cb.isChecked():
            ax.set_ylim(0, self._ymax_spin.value())
        else:
            ax.set_ylim(0, 1.20 * ymax)

        self.fdf_fig.tight_layout()
        self.fdf_canvas.draw_idle()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Faraday Explorer")
    app.setOrganizationName("AmaniAstro")
    app.setStyle("Fusion")

    # ── Parse optional CLI flags (consumed before the positional args) ────────
    HELP = (
        "Faraday Explorer — interactive Faraday-depth polarisation viewer\n"
        "\n"
        "Usage:\n"
        "  faraday_explorer.py                                          (GUI: file picker)\n"
        "  faraday_explorer.py FDF.fits freqFile.dat                   (FDF-only CLI)\n"
        "  faraday_explorer.py FDF.fits I.fits Q.fits U.fits freq.dat  (full CLI)\n"
        "\n"
        "Optional flags:\n"
        "  --ds <pct>    Spatial downsampling: percent of resolution to keep (1–100).\n"
        "                Default = 4 (every 25th pixel). Use 100 for full resolution.\n"
        "  -h, --help    Show this help and exit.\n"
        "\n"
        "Launcher-only flags (handled by launch_faraday_explorer.sh):\n"
        "  --env <name>  Use a non-default conda environment.\n"
    )
    cli_ds_pct = 4   # default: 4% (matches the GUI default → MAP_STEP=25)
    args = sys.argv[1:]
    cleaned = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-h", "--help"):
            print(HELP)
            sys.exit(0)
        if a in ("--ds", "--ds-pct"):
            if i + 1 >= len(args):
                print("ERROR: --ds requires a value between 1 and 100", file=sys.stderr)
                sys.exit(1)
            try:
                val = float(args[i + 1])
            except ValueError:
                print(f"ERROR: --ds value '{args[i+1]}' is not a number", file=sys.stderr)
                sys.exit(1)
            if not (1 <= val <= 100):
                print(f"ERROR: --ds must be between 1 and 100 (got {val})", file=sys.stderr)
                sys.exit(1)
            cli_ds_pct = int(round(val))
            i += 2
        else:
            cleaned.append(a)
            i += 1
    sys.argv = [sys.argv[0]] + cleaned

    # ── Opening splash — always shown, regardless of CLI/GUI mode ─────────────
    splash = VideoSplash()
    loop   = QEventLoop()
    splash.finished.connect(loop.quit)
    splash.start()
    loop.exec_()
    splash.close()

    # ── Resolve file paths ────────────────────────────────────────────────────
    preloaded        = None
    full_stokes_path = None

    if len(sys.argv) >= 3:
        if len(sys.argv) == 3:
            fdf_path, freq_file = sys.argv[1], sys.argv[2]
            i_path = q_path = u_path = None
        else:
            fdf_path, i_path, q_path, u_path, freq_file = sys.argv[1:6]
        map_step = max(1, round(100 / cli_ds_pct))
        freqs    = np.loadtxt(freq_file)
        paths    = dict(fdf=fdf_path, i=i_path, q=q_path, u=u_path)
        _, beam_info = validate_inputs(paths)
        print(f"CLI mode — {len(freqs)} frequencies from {freq_file}, "
              f"downsample = {cli_ds_pct}% (map_step={map_step})")
    else:
        while True:
            dlg = LaunchDialog()
            if dlg.exec_() != QDialog.Accepted:
                sys.exit(0)
            p = dlg.paths
            ok, beam_info = validate_inputs(p)
            if ok:
                break
        fdf_path, freq_file    = p["fdf"], p["freq"]
        i_path, q_path, u_path = p["i"],   p["q"],   p["u"]
        full_stokes_path       = p.get("full_stokes")
        map_step               = p["map_step"]
        freqs = np.loadtxt(freq_file)
        print(f"GUI mode — {len(freqs)} frequencies from {freq_file}")

        loading = LoadingDialog(p, map_step)
        if loading.exec_() != QDialog.Accepted:
            if loading.error_msg:
                QMessageBox.critical(None, "Load Failed", loading.error_msg)
            sys.exit(1)
        preloaded = loading.result_data

    win = MainWindow(fdf_path, i_path, q_path, u_path, freqs, map_step, beam_info,
                     full_stokes_path=full_stokes_path, _preloaded=preloaded)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
