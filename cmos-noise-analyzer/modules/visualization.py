# visualization.py

import os
import matplotlib.pyplot as plt
import numpy as np
from modules.utilities import logger

def plot_fit_results(fit_params, gain, set_temp, plots_directory):
    """
    Plots the observed frequencies and fitted Gaussian, and saves the plot.

    Parameters:
        fit_params (dict): Fit parameters and data.
        gain (float): GAIN value.
        set_temp (float): SET-TEMP value.
        plots_directory (str): Directory to save plots.

    Returns:
        str: Path to the saved plot.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(fit_params['Electron Counts'], fit_params['Frequencies'],
                color='blue', label='Observed Frequency')
    plt.plot(fit_params['Electron Counts'], fit_params['Fitted Frequencies'],
             color='red', linestyle='--', label='Fitted Gaussian')
    plt.xlabel('Electron Count (e-)')
    plt.ylabel('Frequency Count')
    plt.title(f'Electron Count Distribution\nGAIN={gain}, SET-TEMP={set_temp}°C')
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # Save the plot
    plot_filename = f"GaussianFit_GAIN_{gain}_SETTEMP_{set_temp}.png"
    plot_path = os.path.join(plots_directory, plot_filename)
    plt.savefig(plot_path, dpi=300)
    plt.close()
    logger.info(f"Plot saved to {plot_path}")

    return plot_path

def plot_overlay(overlay_data, plots_directory):
    """
    Generates an overlay plot of all Gaussian fits.

    Parameters:
        overlay_data (list of dict): List containing data for each group.
        plots_directory (str): Directory to save the overlay plot.

    Returns:
        str: Path to the saved overlay plot.
    """
    if not overlay_data:
        logger.info("No data available for overlay plot.")
        return None

    plt.figure(figsize=(12, 8))
    num_groups = len(overlay_data)
    colors = plt.cm.rainbow(np.linspace(0, 1, num_groups))

    for idx, data in enumerate(overlay_data):
        plt.scatter(data['Electron Counts'], data['Frequencies'], color=colors[idx],
                    alpha=0.5, label=f"Data {data['Label']}")
        plt.plot(data['Electron Counts'], data['Fitted Frequencies'], color=colors[idx],
                 linestyle='--', label=f"Fit {data['Label']}")

    plt.xlabel('Electron Count (e-)')
    plt.ylabel('Frequency Count')
    plt.title('Overlay of Electron Count Distributions and Gaussian Fits')
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xlim(8, 16)

    # Save the overlay plot
    overlay_plot_path = os.path.join(plots_directory, "Overlay_Gaussian_Fits.png")
    plt.savefig(overlay_plot_path, dpi=300)
    plt.close()
    logger.info(f"Overlay plot saved to {overlay_plot_path}")

    return overlay_plot_path
