#!/usr/bin/env python3
"""
Faraday Explorer — Interactive Faraday depth polarisation model viewer.

PyQt5 application: native controls, embedded matplotlib canvases.
Run:  conda run -n narnia python3 qu_viewer.py FDF.fits I.fits Q.fits U.fits freqFile.dat
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
)
from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSettings, QEventLoop
from PyQt5.QtGui import QFont, QPixmap, QImage

# Two-phase splash: branding video → app-name video.
# Both decoded frame-by-frame via ffmpeg pipe — no GStreamer needed.
_HERE = os.path.dirname(os.path.abspath(__file__))
SPLASH_VIDEO_1  = os.path.join(_HERE, "splash.mp4")       # amani Astro branding
SPLASH_VIDEO_2  = os.path.join(_HERE, "splash_app.mp4")   # Faraday Explorer title
SPLASH_IMAGE    = os.path.join(_HERE, "splash_frame.png") # static fallback
SPLASH_WIDTH    = 500   # display width in pixels (height scaled proportionally)
SPLASH_EXTRA_MS = 1000  # ms to hold last frame of video 2 before closing


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


# ── MapCanvas: FDF peak map with aperture drawing ────────────────────────────

class MapCanvas(FigureCanvas):
    aperture_ready = pyqtSignal(np.ndarray, float, float, float)  # mask, cx, cy, r

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
        ax.set_title("Peak |FDF|  [Jy/beam/RMSF]\n"
                     "Click to set centre · hold+drag to set radius",
                     fontsize=8, color="white", pad=3)
        ax.set_xlabel("RA pixel (downsampled)", fontsize=7, color="white")
        ax.set_ylabel("Dec pixel (downsampled)", fontsize=7, color="white")
        ax.tick_params(colors="white", labelsize=6)
        for sp in ax.spines.values():
            sp.set_edgecolor("white")
        self.ax = ax
        self._ny, self._nx = peak_map.shape

        # Aperture drawing state
        self._state  = "idle"
        self._centre = None
        self._patch  = None
        self._marker = None

        # Middle-button pan state
        self._panning     = False
        self._pan_last_xy = None     # last (canvas_x, canvas_y) in display pixels

        self.mpl_connect("button_press_event",   self._on_press)
        self.mpl_connect("motion_notify_event",  self._on_drag)
        self.mpl_connect("button_release_event", self._on_release)
        self.mpl_connect("scroll_event",         self._on_scroll)

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

    # ── Middle-button pan ─────────────────────────────────────────────────────

    def _on_press(self, ev):
        if ev.button == 2:                       # middle click → start pan
            self._panning     = True
            self._pan_last_xy = (ev.x, ev.y)
            self.setCursor(Qt.ClosedHandCursor)
            return
        if ev.inaxes != self.ax: return
        if self._state == "center_set":          # left click → aperture draw
            self._state = "drawing"

    def _on_drag(self, ev):
        if self._panning and ev.x is not None:   # middle held → pan
            dx = ev.x - self._pan_last_xy[0]
            dy = ev.y - self._pan_last_xy[1]
            self._pan_last_xy = (ev.x, ev.y)
            bbox = self.ax.get_window_extent()
            xl, xr = self.ax.get_xlim()
            yb, yt = self.ax.get_ylim()
            sx = (xr - xl) / max(bbox.width,  1)
            sy = (yt - yb) / max(bbox.height, 1)
            self.ax.set_xlim(xl - dx * sx, xr - dx * sx)
            self.ax.set_ylim(yb - dy * sy, yt - dy * sy)
            self.draw_idle()
            return
        if self._state != "drawing" or ev.inaxes != self.ax: return
        cx, cy = self._centre
        r = np.hypot(ev.xdata - cx, ev.ydata - cy)
        if self._patch: self._patch.remove()
        self._patch = mpatches.Circle((cx, cy), r, fill=False,
                                       edgecolor="cyan", lw=1.4, ls="--", zorder=5)
        self.ax.add_patch(self._patch)
        self.draw_idle()

    def _on_release(self, ev):
        if ev.button == 2:                       # middle release → end pan
            self._panning     = False
            self._pan_last_xy = None
            self.unsetCursor()
            return
        if ev.inaxes != self.ax:
            if self._state == "drawing": self._state = "center_set"
            return
        if self._state == "idle":
            self._centre = (ev.xdata, ev.ydata)
            if self._marker: self._marker.remove()
            if self._patch:  self._patch.remove(); self._patch = None
            self._marker = self.ax.scatter(
                [ev.xdata], [ev.ydata], marker="+",
                color="cyan", s=140, lw=2, zorder=6)
            self._state = "center_set"
            self.draw_idle()
        elif self._state == "drawing":
            cx, cy = self._centre
            r = max(0.5, np.hypot(ev.xdata - cx, ev.ydata - cy))
            if self._patch: self._patch.remove()
            self._patch = mpatches.Circle((cx, cy), r, fill=False,
                                           edgecolor="cyan", lw=1.8, zorder=5)
            self.ax.add_patch(self._patch)
            if self._marker: self._marker.remove(); self._marker = None
            self.draw_idle()

            ys, xs = np.ogrid[0:self._ny, 0:self._nx]
            mask = (xs - cx)**2 + (ys - cy)**2 <= r**2
            if mask.sum() > 0:
                self.aperture_ready.emit(mask, float(cx), float(cy), float(r))

            self._state  = "idle"
            self._centre = None


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

        # Initial pixmap: first frame of whichever video loads first
        first = (self._v1 or self._v2)
        pixmap = first[0] if first else QPixmap()
        if pixmap.isNull() and os.path.exists(SPLASH_IMAGE):
            pixmap = QPixmap(SPLASH_IMAGE)

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
                self._frame_timer.setInterval(max(16, int(1000.0 / fps)))
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
                ['ffprobe', '-v', 'quiet', '-print_format', 'json',
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
                ['ffmpeg', '-i', path,
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


# ── Startup file-picker dialog ────────────────────────────────────────────────

class LaunchDialog(QDialog):
    """Shown at startup (and via File > Open) to select all input files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QU Viewer — Open Files")
        self.setMinimumWidth(600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._cfg      = QSettings("QUViewer", "QUViewer")
        self._last_dir = self._cfg.value("last_dir", os.path.expanduser("~"))
        self.paths     = {}   # populated when user clicks Open

        self._setup_ui()
        self._check_ready()   # enable/disable Open based on restored paths

    def _setup_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setSpacing(10)

        # Header
        hdr = QLabel(
            "<h2 style='margin:0;'>QU Viewer</h2>"
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
        of  = QFormLayout(opt)
        of.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self._i_edit = self._file_row(of, "Stokes I", "*.fits *.FITS", "i")
        self._q_edit = self._file_row(of, "Stokes Q", "*.fits *.FITS", "q")
        self._u_edit = self._file_row(of, "Stokes U", "*.fits *.FITS", "u")
        vbox.addWidget(opt)

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
        self._open_btn.setStyleSheet(
            "QPushButton:enabled{background:#1a7abf;color:white;"
            "font-weight:bold;padding:4px 18px;border-radius:3px;}"
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
        self.paths = {
            "fdf":  self._fdf_edit.text(),
            "freq": self._freq_edit.text(),
            "i":    self._i_edit.text() or None,
            "q":    self._q_edit.text() or None,
            "u":    self._u_edit.text() or None,
        }
        self.accept()


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self, fits_path, i_path, q_path, u_path, freqs):
        super().__init__()
        self.setWindowTitle("QU Viewer  —  Polarisation Model Viewer")
        self.resize(1400, 800)

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

        # ── Load data ─────────────────────────────────────────────────────────
        self.has_data = self.has_qu = False
        self._load_cubes(fits_path, i_path, q_path, u_path)

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_ui()

        # ── Update once to initialise plots ──────────────────────────────────
        self._update()

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_cubes(self, fits_path, i_path, q_path, u_path):
        if not os.path.exists(fits_path):
            print(f"[WARN] FDF cube not found: {fits_path}")
            return
        from astropy.io import fits as _fits
        print("Loading FDF cube…")
        hdu = _fits.open(fits_path, memmap=True)
        self.fdf_data = hdu[0].data
        h = hdu[0].header
        n3, cr, cd, cp = h["NAXIS3"], h["CRVAL3"], h["CDELT3"], h["CRPIX3"]
        self.phi_data = cr + (np.arange(1, n3+1) - cp) * cd
        self.map_step = MAP_STEP
        print("Computing peak map…")
        self.peak_map = self.fdf_data[:, ::MAP_STEP, ::MAP_STEP].max(axis=0)
        self.has_data = True
        print(f"  FDF: {self.fdf_data.shape}  φ: {self.phi_data[0]:.1f}…{self.phi_data[-1]:.1f}")

        if all(p and os.path.exists(p) for p in [i_path, q_path, u_path]):
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
        # ── Map dock (left, dockable / floatable) ─────────────────────────────
        if self.has_data:
            self.map_canvas = MapCanvas(self.peak_map)
            self.map_canvas.aperture_ready.connect(self._on_aperture)
            self._map_dock = QDockWidget("Peak |FDF| Map", self)
            self._map_dock.setWidget(self.map_canvas)
            self._map_dock.setFeatures(QDockWidget.DockWidgetMovable |
                                        QDockWidget.DockWidgetFloatable |
                                        QDockWidget.DockWidgetClosable)
            self.addDockWidget(Qt.LeftDockWidgetArea, self._map_dock)
            map_dock = self._map_dock   # alias for the View menu below

        # ── Controls dock (right, dockable / floatable) ───────────────────────
        ctrl_widget = self._build_controls()
        self._ctrl_dock = QDockWidget("Model & Parameters", self)
        self._ctrl_dock.setWidget(ctrl_widget)
        self._ctrl_dock.setFeatures(QDockWidget.DockWidgetMovable |
                                     QDockWidget.DockWidgetFloatable |
                                     QDockWidget.DockWidgetClosable)
        # When the panel detaches, give it a comfortable width for sliders
        self._ctrl_dock.topLevelChanged.connect(
            lambda floating: self._ctrl_dock.resize(480, 750) if floating else None
        )
        self.addDockWidget(Qt.RightDockWidgetArea, self._ctrl_dock)

        # ── Central widget: science plots only ───────────────────────────────
        self.setCentralWidget(self._build_plots())

        # ── File menu ─────────────────────────────────────────────────────────
        fmenu = self.menuBar().addMenu("&File")
        open_act = fmenu.addAction("Open new dataset…")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_new)
        fmenu.addSeparator()
        fmenu.addAction("Quit").triggered.connect(self.close)

        # ── View menu — lets user reopen any closed panel ─────────────────────
        view = self.menuBar().addMenu("&View")
        if self.has_data:
            view.addAction(map_dock.toggleViewAction())
        view.addAction(self._ctrl_dock.toggleViewAction())
        view.addSeparator()
        restore = view.addAction("Restore default layout")
        restore.triggered.connect(self._restore_layout)

        # ── Status bar ────────────────────────────────────────────────────────
        self.statusBar().showMessage("Ready — draw an aperture on the map to load real data.")

    def _open_new(self):
        """Show the file-picker dialog and reopen with new data."""
        dlg = LaunchDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            p     = dlg.paths
            freqs = np.loadtxt(p["freq"])
            win   = MainWindow(p["fdf"], p["i"], p["q"], p["u"], freqs)
            win.show()
            self.close()

    def _restore_layout(self):
        """Bring all dock panels back to their default docked positions."""
        if self.has_data:
            self._map_dock.setFloating(False)
            self._map_dock.setVisible(True)
            self.addDockWidget(Qt.LeftDockWidgetArea, self._map_dock)
        self._ctrl_dock.setFloating(False)
        self._ctrl_dock.setVisible(True)
        self.addDockWidget(Qt.RightDockWidgetArea, self._ctrl_dock)

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
        self.model_combo.addItems(list(MODEL_PARAMS.keys()))
        self.model_combo.currentTextChanged.connect(self._on_model)
        g.addWidget(self.model_combo)
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
            self._param_layout.addWidget(pw)
            self._param_widgets.append(pw)
        self._param_layout.addStretch()

        self._configure_params()

        # Defer timer for batching rapid slider moves
        self._update_timer = QTimer(singleShot=True)
        self._update_timer.timeout.connect(self._update)

        return panel

    def _build_plots(self):
        splitter = QSplitter(Qt.Vertical)

        # QU canvas (top)
        qu_holder = QWidget()
        qv = QVBoxLayout(qu_holder)
        qv.setContentsMargins(0, 0, 0, 0)
        self.qu_fig    = Figure(facecolor="#fafafa")
        self.qu_canvas = FigureCanvas(self.qu_fig)
        self.qu_ax     = self.qu_fig.add_subplot(111)
        qv.addWidget(NavToolbar(self.qu_canvas, qu_holder))
        qv.addWidget(self.qu_canvas)
        splitter.addWidget(qu_holder)

        # FDF canvas (bottom)
        fdf_holder = QWidget()
        fv = QVBoxLayout(fdf_holder)
        fv.setContentsMargins(0, 0, 0, 0)
        self.fdf_fig    = Figure(facecolor="#fafafa")
        self.fdf_canvas = FigureCanvas(self.fdf_fig)
        self.fdf_ax     = self.fdf_fig.add_subplot(111)
        fv.addWidget(NavToolbar(self.fdf_canvas, fdf_holder))
        fv.addWidget(self.fdf_canvas)
        splitter.addWidget(fdf_holder)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        return splitter

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

    def _schedule_update(self):
        self._update_timer.start(40)   # 40 ms debounce — batches rapid slider drags

    def _on_aperture(self, mask, cx, cy, r):
        n_pix = int(mask.sum())
        ds = self.fdf_data[:, ::self.map_step, ::self.map_step]
        self.real_fdf   = ds[:, mask].sum(axis=1).astype(np.float64)
        self.real_label = f"aperture  r={r:.1f} ds-px  ({n_pix} px)"

        if self.has_qu:
            I_sum = self.i_data[:, ::self.map_step, ::self.map_step][:, mask].sum(axis=1).astype(np.float64)
            Q_sum = self.q_data[:, ::self.map_step, ::self.map_step][:, mask].sum(axis=1).astype(np.float64)
            U_sum = self.u_data[:, ::self.map_step, ::self.map_step][:, mask].sum(axis=1).astype(np.float64)
            safe = np.abs(I_sum) > 1e-10 * np.abs(I_sum).max()
            self.real_q = np.where(safe, Q_sum / I_sum, np.nan)
            self.real_u = np.where(safe, U_sum / I_sum, np.nan)

        self.statusBar().showMessage(
            f"Aperture: r={r:.1f} ds-px, {n_pix} pixels summed  |  model: {self.model}")
        self._update()

    # ── Plot update ───────────────────────────────────────────────────────────

    def _update(self):
        vals    = self._get_vals()
        P       = model_P(self.model, vals, self.lam2)
        fdf     = rm_synthesis(P, self.lam2, self.phi)
        amp     = np.abs(fdf)
        amax    = amp.max() if amp.max() > 0 else 1.0
        freqs_G = self.freqs / 1e9

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
        ax.set_title(f"q & u vs Frequency  |  model {self.model}")
        ax.legend(fontsize=8, loc="upper right", framealpha=0.85)
        ax.grid(True, alpha=0.2)
        self.qu_fig.tight_layout()
        self.qu_canvas.draw_idle()

    def _draw_fdf(self, amp, amax):
        ax = self.fdf_ax
        ax.cla()
        ax.set_facecolor("#fdfdfd")

        ax.fill_between(self.phi, self.rmsf * amax, alpha=0.07, color="gray")
        ax.plot(self.phi, self.rmsf * amax, color="gray", lw=0.7,
                ls="--", alpha=0.4, label="RMSF (scaled)")

        sub = "₁₂₃"
        for j, rm in enumerate(self._rm_vals()):
            ax.axvline(rm, color=RM_COLOURS[j % 3], lw=0.9, ls=":", alpha=0.65,
                       label=f"RM{sub[j]} input = {rm:+.0f}")

        ax.plot(self.phi, amp, color="steelblue", lw=1.8, label="|FDF| model")

        # Peak detection on model FDF
        dphi    = (PHI_MAX - PHI_MIN) / (N_PHI - 1)
        min_sep = max(1, int(15.0 / dphi))
        if amax > 0:
            peaks, _ = find_peaks(amp, height=0.05*amax,
                                  prominence=0.20*amax, distance=min_sep)
            for pk in peaks:
                phi_pk, a_pk = self.phi[pk], amp[pk]
                ax.axvline(phi_pk, color="steelblue", lw=0.9, ls="--", alpha=0.7)
                ax.scatter([phi_pk], [a_pk], color="steelblue", s=40, zorder=6,
                           edgecolors="navy", lw=0.5)
                ax.annotate(f"φ={phi_pk:+.1f}", xy=(phi_pk, a_pk),
                            xytext=(5, 3), textcoords="offset points",
                            fontsize=7, color="steelblue",
                            bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                      ec="steelblue", alpha=0.85, lw=0.5))

        # Real FDF overlay
        if self.real_fdf is not None:
            real_amp = self.real_fdf
            real_max = real_amp.max()
            if real_max > 0:
                real_norm = real_amp / real_max * amax
                ax.plot(self.phi_data, real_norm, color="darkorange", lw=1.5,
                        alpha=0.85, label=f"|FDF| data  {self.real_label}")
                dphi_r = abs(self.phi_data[1] - self.phi_data[0])
                sep_r  = max(1, int(15.0 / dphi_r))
                rp, _  = find_peaks(real_amp, height=0.05*real_max,
                                    prominence=0.10*real_max, distance=sep_r)
                for pk in rp:
                    phi_pk = self.phi_data[pk]
                    a_pk   = real_norm[pk]
                    ax.axvline(phi_pk, color="darkorange", lw=0.9, ls="-.", alpha=0.7)
                    ax.scatter([phi_pk], [a_pk], color="darkorange", s=35, zorder=6,
                               edgecolors="saddlebrown", lw=0.5)
                    ax.annotate(f"φ={phi_pk:+.0f}", xy=(phi_pk, a_pk),
                                xytext=(-4, 8), textcoords="offset points",
                                fontsize=7, color="darkorange",
                                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                          ec="darkorange", alpha=0.85, lw=0.5))

        ax.set_xlabel("Faraday Depth  φ  [rad m⁻²]")
        ax.set_ylabel("|FDF(φ)|  (model: fractional; data: normalised)")
        ax.set_title(f"FDF Comparison  |  model {self.model}")
        ax.legend(fontsize=7.5, loc="upper right", framealpha=0.85)
        ax.grid(True, alpha=0.2)
        ax.set_xlim(PHI_MIN, PHI_MAX)
        ax.set_ylim(0, 1.20 * amax)
        self.fdf_fig.tight_layout()
        self.fdf_canvas.draw_idle()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QU Viewer")
    app.setOrganizationName("QUViewer")
    app.setStyle("Fusion")

    # ── Opening splash ───────────────────────────────────────────────────────
    splash = VideoSplash()
    if not splash.pixmap().isNull():
        loop = QEventLoop()
        splash.finished.connect(loop.quit)
        splash.start()
        loop.exec_()
        splash.close()

    # ── Resolve file paths ────────────────────────────────────────────────────
    if len(sys.argv) >= 3:
        if len(sys.argv) == 3:
            fdf_path, freq_file = sys.argv[1], sys.argv[2]
            i_path = q_path = u_path = None
        else:
            fdf_path, i_path, q_path, u_path, freq_file = sys.argv[1:6]
        freqs = np.loadtxt(freq_file)
        print(f"CLI mode — {len(freqs)} frequencies from {freq_file}")
    else:
        dlg = LaunchDialog()
        if dlg.exec_() != QDialog.Accepted:
            sys.exit(0)
        p                      = dlg.paths
        fdf_path, freq_file    = p["fdf"], p["freq"]
        i_path, q_path, u_path = p["i"],   p["q"],   p["u"]
        freqs = np.loadtxt(freq_file)
        print(f"GUI mode — {len(freqs)} frequencies from {freq_file}")

    win = MainWindow(fdf_path, i_path, q_path, u_path, freqs)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
