# gaussian_fitting.py

import numpy as np
from scipy.optimize import curve_fit
from modules.utilities import logger

def gaussian(x, A, mu, sigma):
    """
    Gaussian function used for fitting.

    Parameters:
        x (array): Independent variable.
        A (float): Amplitude.
        mu (float): Mean.
        sigma (float): Standard deviation.

    Returns:
        array: Gaussian function evaluated at x.
    """
    return A * np.exp(-((x - mu) ** 2) / (2 * sigma ** 2))

def fit_gaussian_and_collect_params(pixel_counts, egain):
    """
    Fits a Gaussian function to the pixel count data and collects fit parameters.

    Parameters:
        pixel_counts (array): Array of cumulative pixel counts.
        egain (float): Average EGAIN value.

    Returns:
        fit_params (dict): Dictionary containing fit parameters and related data.
    """
    if pixel_counts is None or np.sum(pixel_counts) == 0:
        logger.warning("No pixel counts to process.")
        return None

    # Calculate electron counts
    intensities = np.arange(len(pixel_counts))
    electron_counts = intensities * egain
    frequencies = pixel_counts

    # Filter out zero frequencies
    mask = frequencies > 0
    electron_counts = electron_counts[mask]
    frequencies = frequencies[mask]

    # Check if data is sufficient for fitting
    if len(electron_counts) < 3:
        logger.warning("Not enough data points for fitting.")
        return None

    # Initial guesses for Gaussian fit
    p0 = [np.max(frequencies), np.mean(electron_counts), np.std(electron_counts)]

    # Fit the histogram data to the Gaussian function
    try:
        popt, pcov = curve_fit(gaussian, electron_counts, frequencies, p0=p0)
        A_fit, mu_fit, sigma_fit = popt
        perr = np.sqrt(np.diag(pcov))  # Standard errors
        amplitude_err, mean_err, sigma_err = perr

        # Calculate goodness-of-fit measure (R-squared)
        fitted_frequencies = gaussian(electron_counts, *popt)
        residuals = frequencies - fitted_frequencies
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((frequencies - np.mean(frequencies)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)

        # Store fit parameters
        fit_params = {
            'Amplitude': A_fit,
            'Amplitude Error': amplitude_err,
            'Mean': mu_fit,
            'Mean Error': mean_err,
            'Sigma': sigma_fit,
            'Sigma Error': sigma_err,
            'R-squared': r_squared,
            'Degrees of Freedom': len(frequencies) - len(popt),
            'Electron Counts': electron_counts,
            'Frequencies': frequencies,
            'Fitted Frequencies': fitted_frequencies
        }

        return fit_params

    except RuntimeError as e:
        logger.error(f"Gaussian fit did not converge: {e}")
        return None
