import numpy as np
from astropy.io import fits
import csv
import os
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

# Function to Group FITS Files
def group_fits_files_by_parameters(directory_path, exptime_value):
    # Dictionary to hold groups: {(GAIN, SET-TEMP): [file1, file2, ...]}
    groups = {}

    # List all FITS files in the directory
    fits_files = [f for f in os.listdir(directory_path) if f.lower().endswith('.fits')]
    print(f"FITS files found: {fits_files}")

    # Process each FITS file to group them
    for filename in fits_files:
        file_path = os.path.join(directory_path, filename)
        try:
            # Open FITS file and read header
            with fits.open(file_path) as hdul:
                header = hdul[0].header

                # Extract header values, handling possible trailing spaces or different cases
                exptime = header.get('EXPTIME') or header.get('EXPTIME ') or header.get('exptime')
                gain = header.get('GAIN') or header.get('GAIN ') or header.get('gain')
                set_temp = header.get('SET-TEMP') or header.get('SET-TEMP ') or header.get('set-temp')

                # Convert to appropriate types
                try:
                    exptime = float(str(exptime).strip())
                    gain = float(str(gain).strip())
                    set_temp = float(str(set_temp).strip())
                except (TypeError, ValueError) as e:
                    print(f"Error converting header values in file {filename}: {e}")
                    continue  # Skip this file

                # Detailed debugging statements
                print(f"Processing file: {filename}")
                print(f"EXPTIME from header: {exptime} ({type(exptime)})")
                print(f"EXPTIME value to match: {exptime_value} ({type(exptime_value)})")
                print(f"Difference: {exptime - exptime_value}")
                print(f"GAIN: {gain} ({type(gain)})")
                print(f"SET-TEMP: {set_temp} ({type(set_temp)})")

                # Use a tolerance when comparing floating point numbers
                if abs(exptime - exptime_value) < 1e-6:
                    # Round GAIN and SET-TEMP to avoid floating-point issues
                    key = (round(gain, 2), round(set_temp, 2))
                    print(f"Forming key: {key}")
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(file_path)
                else:
                    print(f"File {filename} skipped due to EXPTIME mismatch.")
        except Exception as e:
            print(f"Error processing file {filename}: {e}")

    print(f"Groups formed: {groups.keys()}")
    return groups

# Process Each Group
def process_group(file_list):
    cumulative_pixel_counts = {}
    egain_values = []

    print(f"Processing group with {len(file_list)} files.")

    for file_path in file_list:
        filename = os.path.basename(file_path)
        try:
            # Open FITS file and read header
            with fits.open(file_path) as hdul:
                header = hdul[0].header
                egain = header.get('EGAIN') or header.get('EGAIN ') or header.get('egain')
                if egain is None:
                    print(f"EGAIN not found in FITS header of file {filename}.")
                    continue  # Skip this file
                else:
                    try:
                        egain = float(str(egain).strip())
                    except (TypeError, ValueError) as e:
                        print(f"Error converting EGAIN in file {filename}: {e}")
                        continue  # Skip this file

                # Read image data
                data = hdul[0].data

                # Ensure data is not None
                if data is None:
                    print(f"No image data found in file {filename}.")
                    continue  # Skip this file

                # Convert from 16-bit to 12-bit space
                pixel_values = data.flatten() // 16

                # Update cumulative pixel counts
                unique_values, counts = np.unique(pixel_values, return_counts=True)
                for intensity, count in zip(unique_values, counts):
                    cumulative_pixel_counts[intensity] = cumulative_pixel_counts.get(intensity, 0) + count

                egain_values.append(egain)

        except Exception as e:
            print(f"Error processing file {filename}: {e}")

    if not egain_values:
        print("No EGAIN values found in the group.")
        return None, None

    # Use the average EGAIN value (assuming it's consistent across files)
    average_egain = np.mean(egain_values)
    print(f"Average EGAIN value: {average_egain} e-/ADU")

    return cumulative_pixel_counts, average_egain

# Fit Gaussian and Collect Parameters
def fit_gaussian_and_collect_params(pixel_counts, egain):
    if not pixel_counts:
        print("No pixel counts to process.")
        return None

    # Calculate electron counts for each pixel intensity
    electron_counts = {intensity: intensity * egain for intensity in pixel_counts.keys()}

    # Prepare data for fitting
    electron_counts_list = np.array(list(electron_counts.values()))
    frequencies = np.array([pixel_counts[intensity] for intensity in pixel_counts.keys()])

    # Filter out zero frequencies for fitting
    mask = frequencies > 0
    electron_counts_list = electron_counts_list[mask]
    frequencies = frequencies[mask]

    # Check if data is sufficient for fitting
    if len(electron_counts_list) < 3:
        print("Not enough data points for fitting.")
        return None

    # Sort the data for fitting
    sorted_indices = np.argsort(electron_counts_list)
    electron_counts_list = electron_counts_list[sorted_indices]
    frequencies = frequencies[sorted_indices]

    # Define Gaussian function
    def gaussian(x, A, mu, sigma):
        return A * np.exp(-((x - mu) ** 2) / (2 * sigma ** 2))

    # Initial guesses for Gaussian fit
    p0 = [np.max(frequencies), np.mean(electron_counts_list), np.std(electron_counts_list)]

    # Fit the histogram data to the Gaussian function
    try:
        popt, pcov = curve_fit(gaussian, electron_counts_list, frequencies, p0=p0)
        A_fit, mu_fit, sigma_fit = popt
        perr = np.sqrt(np.diag(pcov))  # Standard errors
        amplitude_err, mean_err, sigma_err = perr

        # Calculate goodness-of-fit measure (R-squared)
        fitted_frequencies = gaussian(electron_counts_list, *popt)
        residuals = frequencies - fitted_frequencies
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((frequencies - np.mean(frequencies))**2)
        r_squared = 1 - (ss_res / ss_tot)

        # Store fit parameters in a dictionary
        fit_params = {
            'Amplitude': A_fit,
            'Amplitude Error': amplitude_err,
            'Mean': mu_fit,
            'Mean Error': mean_err,
            'Sigma': sigma_fit,
            'Sigma Error': sigma_err,
            'R-squared': r_squared,
            'Degrees of Freedom': len(frequencies) - len(popt),
            'Electron Counts': electron_counts_list,
            'Frequencies': frequencies,
            'Fitted Frequencies': fitted_frequencies
        }

        return fit_params

    except RuntimeError:
        print("Error: Gaussian fit did not converge.")
        return None

# Main Function
if __name__ == "__main__":
    # Specify the directory containing your FITS files
    directory_path = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\FITS_Files'

    # Specify the EXPTIME value to match
    exptime_value = 0.0001  # Updated to match your FITS files' EXPTIME

    # Output path for the summary CSV file
    summary_csv_path = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\gaussian_fit_summary.csv'

    # Directory to save plots
    plots_directory = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\Plots'
    os.makedirs(plots_directory, exist_ok=True)

    try:
        # Group FITS files by GAIN and SET-TEMP
        print("Grouping FITS files by GAIN and SET-TEMP...")
        groups = group_fits_files_by_parameters(directory_path, exptime_value)

        # List to store summary of fit parameters for each group
        summary_data = []

        # Initialize lists to store combined data for overlay plot
        all_electron_counts = []
        all_frequencies = []
        all_fitted_frequencies = []
        all_labels = []

        # Process each group
        for (gain, set_temp), file_list in groups.items():
            print(f"\nProcessing group: GAIN={gain}, SET-TEMP={set_temp}, Number of files={len(file_list)}")

            try:
                # Process the group to get cumulative pixel counts and average EGAIN
                pixel_counts, average_egain = process_group(file_list)
                if pixel_counts is None:
                    print(f"Skipping group GAIN={gain}, SET-TEMP={set_temp} due to missing EGAIN.")
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

                    # Save the plot to a PNG file with increased DPI
                    plot_filename = f"GaussianFit_GAIN_{gain}_SETTEMP_{set_temp}.png"
                    plot_path = os.path.join(plots_directory, plot_filename)
                    plt.savefig(plot_path, dpi=300)  # Increased DPI for higher resolution
                    plt.close()
                    print(f"Plot saved to {plot_path}")

                    # Collect data for overlay plot
                    all_electron_counts.append(fit_params['Electron Counts'])
                    all_frequencies.append(fit_params['Frequencies'])
                    all_fitted_frequencies.append(fit_params['Fitted Frequencies'])
                    label = f"GAIN={gain}, SET-TEMP={set_temp}°C"
                    all_labels.append(label)

                else:
                    print(f"Skipping group GAIN={gain}, SET-TEMP={set_temp} due to fitting issues.")

            except Exception as e:
                print(f"Error processing group GAIN={gain}, SET-TEMP={set_temp}: {e}")

        # Generate overlay plot of all Gaussian fits
        if all_electron_counts:
            print("\nGenerating overlay plot of all Gaussian fits...")

            plt.figure(figsize=(12, 8))

            # Use a rainbow color scheme
            num_groups = len(all_electron_counts)
            colors = plt.cm.rainbow(np.linspace(0, 1, num_groups))

            for idx, (electron_counts, frequencies, fitted_frequencies, label) in enumerate(zip(
                    all_electron_counts, all_frequencies, all_fitted_frequencies, all_labels)):
                plt.scatter(electron_counts, frequencies, color=colors[idx], alpha=0.5, label=f'Data {label}')
                plt.plot(electron_counts, fitted_frequencies, color=colors[idx], linestyle='--', label=f'Fit {label}')

            plt.xlabel('Electron Count (e-)')
            plt.ylabel('Frequency Count')
            plt.title('Overlay of Electron Count Distributions and Gaussian Fits')
            plt.legend()
            plt.grid(axis='y', linestyle='--', alpha=0.7)

            # Adjust x-axis limits
            plt.xlim(8, 16)

            # Y-axis left to auto-scale

            # Save the overlay plot as a PNG file with increased DPI
            overlay_plot_path = os.path.join(plots_directory, "Overlay_Gaussian_Fits.png")
            plt.savefig(overlay_plot_path, dpi=300)  # Increased DPI for higher resolution
            plt.close()
            print(f"Overlay plot saved to {overlay_plot_path}")
        else:
            print("No data available for overlay plot.")

        # Save the summary data to CSV
        if summary_data:
            print("\nSaving Gaussian fit parameters summary to CSV...")
            with open(summary_csv_path, mode='w', newline='') as file:
                writer = csv.writer(file)
                # Write header
                headers = ['GAIN', 'SET-TEMP', 'Amplitude', 'Amplitude Error', 'Mean', 'Mean Error',
                           'Sigma', 'Sigma Error', 'R-squared', 'Degrees of Freedom']
                writer.writerow(headers)

                # Write data
                for data in summary_data:
                    row = [data['GAIN'], data['SET-TEMP'], data['Amplitude'], data['Amplitude Error'],
                           data['Mean'], data['Mean Error'], data['Sigma'], data['Sigma Error'],
                           data['R-squared'], data['Degrees of Freedom']]
                    writer.writerow(row)

            print(f"Summary saved to {summary_csv_path}")

        else:
            print("No data to save.")

    except Exception as e:
        print(f"An error occurred: {e}")
