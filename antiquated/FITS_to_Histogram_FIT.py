import numpy as np
from astropy.io import fits
import csv
import os
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

# Step 1: Function to Group FITS Files
def group_fits_files_by_parameters(directory_path, exptime_value):
    # Dictionary to hold groups: {(GAIN, SET-TEMP): [file1, file2, ...]}
    groups = {}

    # List all FITS files in the directory
    fits_files = [f for f in os.listdir(directory_path) if f.endswith('.fits')]

    # Process each FITS file to group them
    for filename in fits_files:
        file_path = os.path.join(directory_path, filename)
        try:
            # Open FITS file and read header
            with fits.open(file_path) as hdul:
                header = hdul[0].header
                exptime = header.get('EXPTIME')
                gain = header.get('GAIN')
                set_temp = header.get('SET-TEMP')

                # Check if EXPTIME matches the specified value
                if exptime == exptime_value:
                    key = (gain, set_temp)
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(file_path)

        except Exception as e:
            print(f"Error processing file {filename}: {e}")

    return groups

# Step 2: Process Each Group
def process_group(file_list):
    cumulative_pixel_counts = {}
    egain_values = []

    for file_path in file_list:
        filename = os.path.basename(file_path)
        try:
            # Open FITS file and read header
            with fits.open(file_path) as hdul:
                header = hdul[0].header
                egain = header.get('EGAIN')

                if egain is None:
                    raise ValueError(f"EGAIN not found in FITS header of file {filename}.")

                # Read image data
                data = hdul[0].data

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
        raise ValueError("No EGAIN values found in the group.")

    # Use the average EGAIN value (assuming it's consistent across files)
    average_egain = np.mean(egain_values)

    return cumulative_pixel_counts, average_egain

# Step 3: Fit Gaussian and Collect Parameters
def fit_gaussian_and_collect_params(pixel_counts, egain):
    # Calculate electron counts for each pixel intensity
    electron_counts = {intensity: intensity * egain for intensity in pixel_counts.keys()}

    # Prepare data for fitting
    electron_counts_list = np.array(list(electron_counts.values()))
    frequencies = np.array([pixel_counts[intensity] for intensity in pixel_counts.keys()])

    # Filter out zero frequencies for fitting
    mask = frequencies > 0
    electron_counts_list = electron_counts_list[mask]
    frequencies = frequencies[mask]

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

        # Calculate goodness-of-fit measures
        fitted_frequencies = gaussian(electron_counts_list, *popt)
        residuals = frequencies - fitted_frequencies
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((frequencies - np.mean(frequencies))**2)
        r_squared = 1 - (ss_res / ss_tot)

        # Chi-Squared and Reduced Chi-Squared
        sigma_i = np.sqrt(fitted_frequencies)
        sigma_i[sigma_i == 0] = 1e-8  # Prevent division by zero
        chi_squared = np.sum(((frequencies - fitted_frequencies) ** 2) / sigma_i**2)
        degrees_of_freedom = len(frequencies) - len(popt)
        reduced_chi_squared = chi_squared / degrees_of_freedom

        # Store fit parameters in a dictionary
        fit_params = {
            'Amplitude': A_fit,
            'Amplitude Error': amplitude_err,
            'Mean': mu_fit,
            'Mean Error': mean_err,
            'Sigma': sigma_fit,
            'Sigma Error': sigma_err,
            'R-squared': r_squared,
            'Chi-Squared': chi_squared,
            'Reduced Chi-Squared': reduced_chi_squared,
            'Degrees of Freedom': degrees_of_freedom,
            'Electron Counts': electron_counts_list,
            'Frequencies': frequencies,
            'Fitted Frequencies': fitted_frequencies
        }

        return fit_params

    except RuntimeError:
        print("Error: Gaussian fit did not converge.")
        return None

# Step 5: Main Function
if __name__ == "__main__":
    # Specify the directory containing your FITS files
    directory_path = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\FITS_Files'

    # Specify the EXPTIME value to match
    exptime_value = 0.0001  # Exposure time

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

        # Process each group
        for (gain, set_temp), file_list in groups.items():
            print(f"\nProcessing group: GAIN={gain}, SET-TEMP={set_temp}, Number of files={len(file_list)}")

            try:
                # Process the group to get cumulative pixel counts and average EGAIN
                pixel_counts, average_egain = process_group(file_list)
                print(f"Average EGAIN value: {average_egain} e-/ADU")

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

                    # Save the plot to a file
                    plot_filename = f"GaussianFit_GAIN_{gain}_SETTEMP_{set_temp}.png"
                    plot_path = os.path.join(plots_directory, plot_filename)
                    plt.savefig(plot_path)
                    plt.close()
                    print(f"Plot saved to {plot_path}")

                else:
                    print(f"Skipping group GAIN={gain}, SET-TEMP={set_temp} due to fitting issues.")

            except Exception as e:
                print(f"Error processing group GAIN={gain}, SET-TEMP={set_temp}: {e}")

        # Save the summary data to CSV
        if summary_data:
            print("\nSaving Gaussian fit parameters summary to CSV...")
            with open(summary_csv_path, mode='w', newline='') as file:
                writer = csv.writer(file)
                # Write header
                headers = ['GAIN', 'SET-TEMP', 'Amplitude', 'Amplitude Error', 'Mean', 'Mean Error',
                           'Sigma', 'Sigma Error', 'R-squared', 'Chi-Squared', 'Reduced Chi-Squared',
                           'Degrees of Freedom']
                writer.writerow(headers)

                # Write data
                for data in summary_data:
                    row = [data['GAIN'], data['SET-TEMP'], data['Amplitude'], data['Amplitude Error'],
                           data['Mean'], data['Mean Error'], data['Sigma'], data['Sigma Error'],
                           data['R-squared'], data['Chi-Squared'], data['Reduced Chi-Squared'],
                           data['Degrees of Freedom']]
                    writer.writerow(row)

            print(f"Summary saved to {summary_csv_path}")

        else:
            print("No data to save.")

    except Exception as e:
        print(f"An error occurred: {e}")