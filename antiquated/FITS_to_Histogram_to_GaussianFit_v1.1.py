import numpy as np
from astropy.io import fits
import csv
import os
import sys
import time
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# Function to get header value with multiple possible keys
def get_header_value(header, keys):
    """
    Retrieves the value from a FITS header given a list of possible keys.

    Parameters:
        header (fits.Header): FITS file header.
        keys (list of str): Possible keys to search for in the header.

    Returns:
        value (str or None): The value associated with the first found key, or None if not found.
    """
    for key in keys:
        value = header.get(key)
        if value is not None:
            return value
    return None

# Function to group FITS files by parameters
def group_fits_files_by_parameters(directory_path, exptime_value):
    """
    Groups FITS files based on GAIN and SET-TEMP parameters for a given EXPTIME.

    Parameters:
        directory_path (str): Path to the directory containing FITS files.
        exptime_value (float): The exposure time value to filter FITS files.

    Returns:
        dict: A dictionary where keys are (GAIN, SET-TEMP) tuples and values are lists of file paths.
    """
    groups = {}
    fits_files = [f for f in os.listdir(directory_path) if f.lower().endswith('.fits')]
    logger.info(f"FITS files found: {fits_files}")

    for filename in fits_files:
        file_path = os.path.join(directory_path, filename)
        try:
            with fits.open(file_path) as hdul:
                header = hdul[0].header

                # Extract header values
                exptime = get_header_value(header, ['EXPTIME', 'EXPTIME ', 'exptime'])
                gain = get_header_value(header, ['GAIN', 'GAIN ', 'gain'])
                set_temp = get_header_value(header, ['SET-TEMP', 'SET-TEMP ', 'set-temp'])

                # Convert to appropriate types
                exptime = float(str(exptime).strip())
                gain = float(str(gain).strip())
                set_temp = float(str(set_temp).strip())

                logger.info(f"Processing file: {filename}, EXPTIME={exptime}, GAIN={gain}, SET-TEMP={set_temp}")

                # Use a tolerance when comparing floating point numbers
                if abs(exptime - exptime_value) < 1e-6:
                    key = (gain, set_temp)
                    groups.setdefault(key, []).append(file_path)

        except (TypeError, ValueError) as e:
            logger.error(f"Error converting header values in file {filename}: {e}")
            continue  # Skip this file
        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}")

    logger.info(f"Groups formed: {list(groups.keys())}")
    return groups

# Process each group
def process_group(file_list):
    """
    Processes a group of FITS files to compute cumulative pixel counts and average EGAIN.

    Parameters:
        file_list (list of str): List of FITS file paths in the group.

    Returns:
        cumulative_pixel_counts (dict): Dictionary of cumulative pixel counts.
        average_egain (float): Average EGAIN value across files.
    """
    cumulative_pixel_counts = {}
    egain_values = []

    logger.info(f"Processing group with {len(file_list)} files.")

    for file_path in file_list:
        filename = os.path.basename(file_path)
        try:
            with fits.open(file_path) as hdul:
                header = hdul[0].header
                egain = get_header_value(header, ['EGAIN', 'EGAIN ', 'egain'])
                if egain is None:
                    logger.warning(f"EGAIN not found in FITS header of file {filename}.")
                    continue  # Skip this file

                egain = float(str(egain).strip())

                # Read image data
                data = hdul[0].data
                if data is None:
                    logger.warning(f"No image data found in file {filename}.")
                    continue  # Skip this file

                # Convert from 16-bit to 12-bit space
                pixel_values = data.flatten() >> 4  # Efficient bit-shift operation

                # Update cumulative pixel counts using numpy bincount
                counts = np.bincount(pixel_values, minlength=4096)
                if not cumulative_pixel_counts:
                    cumulative_pixel_counts = counts
                else:
                    cumulative_pixel_counts += counts

                egain_values.append(egain)

        except (TypeError, ValueError) as e:
            logger.error(f"Error processing file {filename}: {e}")
            continue  # Skip this file
        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}")

    if not egain_values:
        logger.warning("No EGAIN values found in the group.")
        return None, None

    # Use the average EGAIN value
    average_egain = np.mean(egain_values)
    logger.info(f"Average EGAIN value: {average_egain} e-/ADU")

    return cumulative_pixel_counts, average_egain

# Fit Gaussian and collect parameters
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

    # Define Gaussian function
    def gaussian(x, A, mu, sigma):
        return A * np.exp(-((x - mu) ** 2) / (2 * sigma ** 2))

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

def main():
    """
    Main function to process FITS files, perform Gaussian fitting, and generate outputs.
    """
    start_time = time.time()  # Start timer

    # Specify the directory containing your FITS files
    directory_path = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\FITS_Files'

    # Specify the EXPTIME value to match
    exptime_value = 0.0001  # Update as needed

    # Output path for the summary CSV file
    summary_csv_path = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\gaussian_fit_summary.csv'

    # Directory to save plots
    plots_directory = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\Plots'
    os.makedirs(plots_directory, exist_ok=True)

    try:
        # Group FITS files by GAIN and SET-TEMP
        logger.info("Grouping FITS files by GAIN and SET-TEMP...")
        groups = group_fits_files_by_parameters(directory_path, exptime_value)

        # List to store summary of fit parameters for each group
        summary_data = []

        # Initialize lists to store combined data for overlay plot
        overlay_data = []

        # Process each group
        for (gain, set_temp), file_list in groups.items():
            logger.info(f"\nProcessing group: GAIN={gain}, SET-TEMP={set_temp}, Number of files={len(file_list)}")

            # Process the group to get cumulative pixel counts and average EGAIN
            pixel_counts, average_egain = process_group(file_list)
            if pixel_counts is None:
                logger.warning(f"Skipping group GAIN={gain}, SET-TEMP={set_temp} due to missing EGAIN.")
                continue

            # Fit Gaussian and collect parameters
            fit_params = fit_gaussian_and_collect_params(pixel_counts, average_egain)
            if fit_params:
                # Add group info to fit parameters
                fit_params['GAIN'] = gain
                fit_params['SET-TEMP'] = set_temp

                summary_data.append(fit_params)

                # Plot the results and save the plot
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

                # Collect data for overlay plot
                overlay_data.append({
                    'Electron Counts': fit_params['Electron Counts'],
                    'Frequencies': fit_params['Frequencies'],
                    'Fitted Frequencies': fit_params['Fitted Frequencies'],
                    'Label': f"GAIN={gain}, SET-TEMP={set_temp}°C"
                })

            else:
                logger.warning(f"Skipping group GAIN={gain}, SET-TEMP={set_temp} due to fitting issues.")

        # Generate overlay plot of all Gaussian fits
        if overlay_data:
            logger.info("\nGenerating overlay plot of all Gaussian fits...")

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
        else:
            logger.info("No data available for overlay plot.")

        # Save the summary data to CSV
        if summary_data:
            logger.info("\nSaving Gaussian fit parameters summary to CSV...")
            with open(summary_csv_path, mode='w', newline='') as file:
                writer = csv.writer(file)
                headers = ['GAIN', 'SET-TEMP', 'Amplitude', 'Amplitude Error', 'Mean', 'Mean Error',
                           'Sigma', 'Sigma Error', 'R-squared', 'Degrees of Freedom']
                writer.writerow(headers)

                for data in summary_data:
                    row = [data['GAIN'], data['SET-TEMP'], data['Amplitude'], data['Amplitude Error'],
                           data['Mean'], data['Mean Error'], data['Sigma'], data['Sigma Error'],
                           data['R-squared'], data['Degrees of Freedom']]
                    writer.writerow(row)

            logger.info(f"Summary saved to {summary_csv_path}")

        else:
            logger.info("No data to save.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

    end_time = time.time()  # End timer
    total_time = end_time - start_time
    logger.info(f"\nTotal run time: {total_time:.2f} seconds")

if __name__ == "__main__":
    main()