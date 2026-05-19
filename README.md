# QU Viewer

An interactive polarisation model viewer for radio astronomy QU-fitting. The tool
allows a researcher to visually compare RM-Tools polarisation models against real
Faraday Dispersion Function (FDF) data extracted from FITS image cubes. Parameter
exploration is done in real time via sliders and editable text fields, making it
practical to assess which RM-Tools model best reproduces the observed FDF and
fractional polarisation spectra at any chosen sky position.

---

## Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Interface Guide](#interface-guide)
4. [File Formats](#file-formats)
5. [Model Reference](#model-reference)
6. [Testing](#testing)
7. [Performance and Known Limitations](#performance-and-known-limitations)

---

## Installation

The tool requires a conda environment named `narnia` containing the following
packages:

```
numpy
scipy
matplotlib
astropy
PyQt5
```

To create the environment from scratch:

```bash
conda create -n narnia python=3.10 numpy scipy matplotlib astropy pyqt
conda activate narnia
```

---

## Quick Start

**Full mode** (FDF cube + Stokes I, Q, U cubes):

```bash
conda run -n narnia python3 qu_viewer.py FDF.fits I.fits Q.fits U.fits freqFile.dat
```

**FDF-only mode** (no Stokes cubes — model FDF comparison only, no QU scatter from data):

```bash
conda run -n narnia python3 qu_viewer.py FDF.fits freqFile.dat
```

A single application window opens. The FDF map and parameter panels are dockable
sub-windows that can be detached, floated, and repositioned independently.

---

## Interface Guide

### Panel 1 — Peak FDF Map  *(dockable, floatable)*

Displays a spatial image of the peak `|FDF(phi)|` value across the field, computed
by taking the maximum along the Faraday depth axis of the FDF cube. The image is
rendered on a downsampled grid (every 24th pixel; `MAP_STEP = 24`) using an
`inferno` colour scale clipped to the 2nd–99.5th percentile range.

**Zoom:** scroll the mouse wheel up to zoom in toward the cursor; scroll down to
zoom out. This operates on the matplotlib axes limits directly and does not affect
the aperture coordinates.

**Aperture selection workflow:**

1. Single left-click anywhere on the map to set the aperture centre. A cyan `+`
   marker appears at the chosen position.
2. Left-click again, hold the button down, and drag outward to define the aperture
   radius. A dashed cyan circle previews the aperture boundary as you drag.
3. Release the mouse button to finalise the aperture. The tool sums all downsampled
   pixels inside the circle, extracts the FDF spectrum and (if I/Q/U cubes are
   loaded) computes the aperture-averaged fractional polarisation `q = Q/I` and
   `u = U/I` per frequency channel. The science plots update immediately.

The map panel is a dockable widget. Drag its title bar to float it as a standalone
window or dock it to any edge of the main window.

### Panel 2 — Model & Parameters  *(dockable, floatable)*

Contains a drop-down model selector and a set of parameter widgets, one per model
parameter. Each parameter widget has:

- **Label** — parameter name and units.
- **Spinbox** — shows the current value. Type a number and press Enter or use the
  up/down arrows for precise increments. This is the recommended input method for
  exact values.
- **Slider** — drag left/right for rapid coarse exploration. The spinbox and slider
  are linked bidirectionally. Plot updates are debounced to 40 ms so rapid dragging
  does not stall the interface.
- **Min field** (left of slider) — type a new lower bound and press Enter to rescale
  the slider range without changing the current value.
- **Max field** (right of slider) — same for the upper bound.

For fine-grained slider control, float the panel by dragging its title bar away from
the main window. The panel automatically expands to 480 × 750 px when detached,
giving the sliders significantly more horizontal travel.

Selecting a different model resets all parameters to their defaults for that model.

### Panel 3 — Science Plots  *(central, resizable)*

Two stacked panels:

**Top panel — q & u vs Frequency**

Shows the model fractional polarisation `q = Re(P)` (blue line) and `u = Im(P)`
(orange line) as a function of frequency. If an aperture has been drawn and Stokes
I/Q/U cubes are loaded, the measured `q = Q/I` and `u = U/I` values from the
aperture are overlaid as scatter points (circles for q, squares for u) at the
corresponding SPW centre frequencies.

**Bottom panel — FDF Comparison**

Shows:
- **Model |FDF|** (blue line) — the amplitude of the Faraday Dispersion Function
  computed from the current model parameters by RM synthesis over the model
  Faraday depth grid (-600 to +600 rad/m²).
- **Real |FDF|** (orange line) — the aperture-summed FDF extracted from the FITS
  cube, normalised to the model peak amplitude for shape comparison.
- **RMSF** (grey shaded region and dashed line) — the dirty beam in Faraday space,
  scaled to the model peak, shown for reference.
- **RM reference lines** (green / red / purple dotted vertical lines) — the input
  RM parameter(s) of the current model, one colour per component.
- **Peak annotations** — detected peaks in both the model and data FDFs are marked
  with scatter points and labelled with their Faraday depth in rad/m².

---

## File Formats

### FDF FITS Cube

| Property | Value |
|---|---|
| Array shape | `(n_phi, n_dec, n_ra)` |
| Data type | `float32` |
| BUNIT | `Jy/beam/RMSF` |
| CTYPE3 | `FDEP` |
| Faraday depth axis | Reconstructed from `CRVAL3`, `CDELT3`, `CRPIX3` in the header |

The Faraday depth axis is read directly from the FITS WCS keywords; no external
frequency or phi-axis file is required.

### Stokes I, Q, U FITS Cubes

| Property | Value |
|---|---|
| Array shape | `(n_freq, n_dec, n_ra)` |
| Spatial dimensions | Must match the FDF cube (same `n_dec`, `n_ra`) |
| Units | Jy/beam (Q and U are divided by I to form fractional polarisation) |

All three cubes (I, Q, U) must be provided together. If any one is absent or the
paths are not given, the tool runs in FDF-only mode and the QU scatter panels
remain empty.

### freqFile.dat

Plain text, one frequency per line in Hz. Each line corresponds to one spectral
window (SPW) centre frequency used during imaging.

The 9 SPW centre frequencies used in this project are:

```
9.16272329e+08
9.88997329e+08
1.06172233e+09
1.13444733e+09
1.27989733e+09
1.35262233e+09
1.42534733e+09
1.49807233e+09
1.64352233e+09
```

(range: 916 MHz to 1644 MHz, MeerKAT L-band)

---

## Model Reference

All models follow the RM-Tools convention (VanEck 2026). The complex fractional
polarisation `P(lambda^2)` is synthesised analytically and transformed to the
Faraday depth domain via RM synthesis.

| Model | RM-Tools flag | Physics | Parameters |
|---|---|---|---|
| m1 | `m1` | Single Faraday-thin source. `P = p0 exp(2i(chi0 + RM lambda^2))` | p0, chi0, RM |
| m2 | `m2` | Thin source with external Faraday dispersion screen. `P = p0 exp(2i(...)) exp(-2 sigma_RM^2 lambda^4)` | p0, chi0, RM, sigma_RM |
| m5 | `m5` | Single Burn slab (uniform differential Faraday rotation). Top-hat FDF from RM to RM + dRM; FDF peak at RM + dRM/2. | p0, chi0, RM, dRM |
| m6 | `m6` | Double Burn slab — two independent differential-rotation components. FDF peaks at RM1 + dRM1/2 and RM2 + dRM2/2. | p1, chi1, RM1, dRM1, p2, chi2, RM2, dRM2 |
| m7 | `m7` | Internal Faraday dispersion + differential rotation. `P = p0 exp(2i(...)) * (1 - exp(-S))/S` where `S = 2 sigma^2 lambda^4 - 2i dRM lambda^2` | p0, chi0, RM, dRM, sigma_RM |
| m11 | `m11` | Two independent Faraday-thin sources. Sum of two m1 components. | p1, chi1, RM1, p2, chi2, RM2 |
| m3 | `m3` | Two thin sources with a shared external dispersion screen. | p1, chi1, RM1, p2, chi2, RM2, sigma_RM |
| m4 | `m4` | Two thin sources, each with its own external dispersion screen. | p1, chi1, RM1, sigma_RM1, p2, chi2, RM2, sigma_RM2 |
| m12 | `m12` | Internal Faraday dispersion + differential rotation inside source, plus a separate foreground external screen. | p0, chi0, RM_screen, dRM, sigma_RM_int, sigma_RM_fg |
| m111 | `m111` | Three independent Faraday-thin sources. Sum of three m1 components. | p1, chi1, RM1, p2, chi2, RM2, p3, chi3, RM3 |

**Parameter notation:**
- `p0`, `p1`, `p2`, `p3` — fractional polarisation amplitude (dimensionless, 0–1)
- `chi0`, `chi1`, ... — intrinsic polarisation angle (degrees)
- `RM`, `RM1`, `RM2`, `RM3` — rotation measure (rad/m²); for Burn slabs, this is the lower edge of the slab
- `dRM` — differential Faraday rotation across the source (rad/m²); the slab width
- `sigma_RM` — Faraday dispersion width (rad/m²)

---

## Testing

A diagnostic test suite verifies that all 10 models produce FDF peaks at
analytically-expected Faraday depths.

```bash
python3 test_models.py freqFile.dat
```

For each model, a synthetic `P(lambda^2)` spectrum is generated using parameters
whose FDF peak locations are known exactly. RM synthesis is applied and detected
peaks are compared against the expected positions. A peak is considered matched if
it falls within half the RMSF FWHM of the expected location (the Faraday resolution
limit).

The script prints a pass/fail table to stdout:

```
  Model       Expected peaks          Detected peaks        Max Δφ  Result
  ────────────────────────────────────────────────────────────────────────
  m1               ['+100']              ['+100.0']           0.0  PASS
  m2               ['+100']              ['+100.0']           0.0  PASS
  ...
  10/10 models PASSED
```

It also saves `model_diagnostics.png` in the same directory — a 2×5 grid of
normalised FDF plots with green dashed lines for expected peaks and red dotted
lines for detected peaks.

---

## Performance and Known Limitations

**9-channel RMSF sidelobe level.** With only 9 SPW centre frequencies, the
rotation measure spread function (RMSF) has a first sidelobe at approximately 58%
of the main lobe (compared to ~20% for the full 161-channel MeerKAT L-band cube).
This means that a single FDF peak can produce sidelobe artefacts that may be
mistaken for secondary components. Always inspect the RMSF overlay in the FDF
comparison panel before interpreting multi-peaked structures.

**Aperture extraction uses the downsampled cube.** The peak map and aperture
summation both operate on spatially downsampled data (every 24th pixel along each
spatial axis). The aperture radius and pixel coordinates displayed in the FDF panel
label refer to downsampled pixels, not native image pixels. For quantitative
analysis, extract spectra from the full-resolution cube using RM-Tools or CARTA.

**Faraday depth grid is fixed.** The model FDF is always computed on a fixed grid
of 2401 points from -600 to +600 rad/m², regardless of the range in the FITS cube.
Components with |RM| > 600 rad/m² will not be visible. The real FDF is plotted on
its native axis from the FITS header.

**Real and model FDF amplitudes are not on the same scale.** The aperture-summed
FDF from the FITS cube is normalised to the model peak amplitude for shape
comparison only. The model FDF is in units of fractional polarisation; the data FDF
is in Jy/beam/RMSF summed over aperture pixels. Amplitude fitting requires
dedicated least-squares optimisation outside this tool.

**Real Q and U are fractional polarisation.** When Stokes cubes are loaded, the
scatter points in the QU panel show `q = Q_sum / I_sum` and `u = U_sum / I_sum`
averaged over the aperture. Channels where the summed Stokes I falls below 1e-10
times the maximum I are masked and shown as gaps.
