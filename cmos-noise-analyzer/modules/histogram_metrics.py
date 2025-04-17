#histogram_metrics.py

import numpy as np
from modules.utilities import logger
import matplotlib.pyplot as plt


def collect_histogram_metrics(pixel_counts, egain):
    """
    Collects objective metrics from the histogram of pixel counts.
    Computes peak intensity, FWHM, and additional statistics.

    Parameters:
        pixel_counts (array): Array of cumulative pixel counts (histogram).
        egain (float): Average EGAIN value.

    Returns:
        metrics (dict): Dictionary containing computed metrics.
    """
    if pixel_counts is None or np.sum(pixel_counts) == 0:
        logger.warning("No pixel counts to process.")
        return None

    # Convert pixel intensities to electron counts
    intensities = np.arange(len(pixel_counts))
    electron_counts = intensities * egain
    frequencies = pixel_counts

    # Filter out zero frequencies to avoid issues with empty data
    mask = frequencies > 0
    electron_counts = electron_counts[mask]
    frequencies = frequencies[mask]

    # Check if we have enough data points
    if len(electron_counts) < 3:
        logger.warning("Not enough data points to compute meaningful metrics.")
        return None

    # Identify the peak frequency and corresponding electron count
    max_frequency = np.max(frequencies)
    peak_index = np.argmax(frequencies)
    peak_electron_count = electron_counts[peak_index]

    logger.info(f"Peak Frequency: {max_frequency}")
    logger.info(f"Peak Electron Count: {peak_electron_count}")

    # Compute the FWHM (Full Width at Half Maximum)
    half_max = max_frequency / 2.0

    # Find indices where frequencies cross the half_max level
    # We look for the first point from left that surpasses half_max
    # and the last point from right that is above half_max.
    above_half_mask = frequencies >= half_max

    # If we never cross half max, we can't compute FWHM
    if np.sum(above_half_mask) < 2:
        logger.warning("Unable to compute FWHM: Not enough data above half-maximum.")
        fwhm = None
    else:
        # The first and last points where frequencies are above half_max define the FWHM range
        indices_above_half = np.where(above_half_mask)[0]
        left_index = indices_above_half[0]
        right_index = indices_above_half[-1]
        fwhm = electron_counts[right_index] - electron_counts[left_index]
        logger.info(f"FWHM: {fwhm}")

    # Compute additional metrics from the data distribution
    mean_electrons = np.mean(electron_counts)
    median_electrons = np.median(electron_counts)
    std_electrons = np.std(electron_counts)

    logger.info(f"Mean Electron Count: {mean_electrons}")
    logger.info(f"Median Electron Count: {median_electrons}")
    logger.info(f"Standard Deviation (Electron Counts): {std_electrons}")

    # You may wish to plot the histogram for reference
    plt.figure(figsize=(10, 6))
    plt.scatter(electron_counts, frequencies, label="Data", color="blue", alpha=0.6)
    plt.title("Histogram of Electron Counts")
    plt.xlabel("Electron Counts (e-)")
    plt.ylabel("Frequency Count")
    plt.grid()
    plt.legend()
    plt.show()

    metrics = {
        'Peak Frequency': max_frequency,
        'Peak Electron Count': peak_electron_count,
        'FWHM': fwhm,
        'Mean Electron Count': mean_electrons,
        'Median Electron Count': median_electrons,
        'Std Electron Count': std_electrons,
        'Electron Counts': electron_counts,
        'Frequencies': frequencies
    }

    return metrics
