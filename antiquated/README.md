# Antiquated Scripts

This directory contains older, likely superseded versions of scripts primarily focused on analyzing FITS files (likely dark or bias frames) to understand sensor characteristics, plus one unrelated script for statistical modeling.

These scripts are kept for historical reference but are **not actively maintained** and may not work correctly with current library versions, data formats, or file structures. They often rely on hardcoded file paths that will need modification.

Refer to the newer `cmos-noise-analyzer` project for the most current version of the FITS analysis functionality.

## Contents Detailed

### 1. FITS Histogram & Gaussian Fit Scripts

These scripts share a common core purpose: read FITS files (typically filtered by `EXPTIME` and grouped by `GAIN` and `SET-TEMP`), generate a combined histogram of pixel values for each group, convert ADU to electrons using the `EGAIN` header value, fit a Gaussian function to the resulting electron histogram, and output results.

**Common Inputs:**
*   Directory containing FITS files (hardcoded path, needs changing).
*   Specific `EXPTIME` value to filter files (hardcoded, needs changing).
*   FITS files are expected to have `EXPTIME`, `GAIN`, `SET-TEMP`, and `EGAIN` in their headers (scripts have varying levels of tolerance for key name variations like `GAIN` vs `GAIN `).
*   Pixel data is often assumed to be 16-bit, then bit-shifted or divided to approximate 12-bit values before histogramming.

**Common Outputs:**
*   Console output logging progress and errors.
*   Individual PNG plots for each group's histogram and Gaussian fit (saved to a hardcoded directory).
*   Some versions generate an overlay plot combining all fits.
*   A summary CSV file containing fitted Gaussian parameters (Amplitude, Mean, Sigma, errors, R-squared, etc.) for each group (saved to a hardcoded path).

**Specific Script Notes:**

*   **`FITS_to_Histogram_FIT.py` / `FITS_to_Histogram_e-.py`:**
    *   Appear to be earlier versions.
    *   Use `np.unique` to generate histograms, which might be less efficient than `np.bincount` for this purpose.
    *   Calculate Chi-Squared and Reduced Chi-Squared for the fit.
    *   Plot individual group fits and an overlay plot.
    *   Save fit parameters to CSV.
*   **`FITS_to_Histogram_e-_v2.py`:**
    *   An evolution of the `_e-` script.
    *   Improves header key reading (handles variations like `GAIN` vs `GAIN `).
    *   Adds more detailed debug printing during execution.
    *   Uses rounding for GAIN/SET-TEMP keys to potentially avoid floating-point grouping issues.
    *   Still uses `np.unique` for histograms.
    *   Outputs plots and CSV summary.
*   **`FITS_to_Histogram_to_GaussianFit_v1.py`:**
    *   Very similar structure and functionality to `FITS_to_Histogram_e-_v2.py`.
    *   Outputs plots (individual and overlay) and CSV summary.
    *   Hardcoded paths and `EXPTIME` need adjustment.
*   **`FITS_to_Histogram_to_GaussianFit_v1.1.py`:**
    *   Appears to be the most refined version within this `antiquated` set, closely resembling the structure later adopted in `cmos-noise-analyzer`.
    *   Uses helper functions for `get_header_value`, `group_fits_files_by_parameters`, `process_group`, and `fit_gaussian_and_collect_params`.
    *   Uses the more efficient `np.bincount` for histogram generation.
    *   Includes basic logging setup.
    *   Still has hardcoded paths and `EXPTIME`.
    *   Outputs plots (individual and overlay) and CSV summary.

### 2. Statistical Modelling Script

*   **`CLT_Modelling.py`:**
    *   **Purpose:** Simulates and visualizes the Central Limit Theorem (CLT).
    *   **Functionality:** Generates random samples from a uniform distribution, calculates the mean of each sample, and plots histograms of these sample means for different numbers of samples. This demonstrates that the distribution of sample means tends towards a normal distribution as the number of samples increases, regardless of the underlying distribution (uniform, in this case).
    *   **Inputs:** None (parameters like the number of samples and sample size are hardcoded).
    *   **Outputs:** Displays a Matplotlib plot showing the histograms of sample means.
    *   **Libraries:** `numpy`, `matplotlib`. 