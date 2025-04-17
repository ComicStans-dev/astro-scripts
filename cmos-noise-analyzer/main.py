import os
import csv
import time
from modules.utilities import logger
from modules.file_grouping import group_fits_files_by_parameters
from modules.data_processing import process_group
from modules.histogram_metrics import collect_histogram_metrics
from modules import config  # Importing the configuration module


def main():
    """
    Main function to process FITS files, compute histogram metrics, and generate outputs.
    """
    start_time = time.time()  # Start timer

    try:
        # Group FITS files by GAIN and SET-TEMP
        logger.info("Grouping FITS files by GAIN and SET-TEMP...")
        groups = group_fits_files_by_parameters(config.DIRECTORY_PATH, config.EXPTIME_VALUE)

        # List to store summary of metrics for each group
        summary_data = []

        # Process each group
        for (gain, set_temp), file_list in groups.items():
            logger.info(f"\nProcessing group: GAIN={gain}, SET-TEMP={set_temp}, Number of files={len(file_list)}")

            # Process the group to get cumulative pixel counts and average EGAIN
            pixel_counts, average_egain = process_group(file_list)
            if pixel_counts is None:
                logger.warning(f"Skipping group GAIN={gain}, SET-TEMP={set_temp} due to missing EGAIN.")
                continue

            # Collect histogram metrics
            metrics = collect_histogram_metrics(pixel_counts, average_egain)
            if metrics is not None:
                # Add group info to the metrics
                metrics['GAIN'] = gain
                metrics['SET-TEMP'] = set_temp
                summary_data.append(metrics)
            else:
                logger.warning(f"Skipping group GAIN={gain}, SET-TEMP={set_temp} due to insufficient data.")

        # Save the summary data to CSV
        if summary_data:
            logger.info("\nSaving histogram metrics summary to CSV...")
            with open(config.SUMMARY_CSV_PATH, mode='w', newline='') as file:
                writer = csv.writer(file)
                headers = [
                    'GAIN',
                    'SET-TEMP',
                    'Peak Frequency',
                    'Peak Electron Count',
                    'FWHM',
                    'Mean Electron Count',
                    'Median Electron Count',
                    'Std Electron Count'
                ]
                writer.writerow(headers)

                for data in summary_data:
                    row = [
                        data['GAIN'],
                        data['SET-TEMP'],
                        data['Peak Frequency'],
                        data['Peak Electron Count'],
                        data['FWHM'],
                        data['Mean Electron Count'],
                        data['Median Electron Count'],
                        data['Std Electron Count']
                    ]
                    writer.writerow(row)

            logger.info(f"Summary saved to {config.SUMMARY_CSV_PATH}")

        else:
            logger.info("No data to save.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

    end_time = time.time()  # End timer
    total_time = end_time - start_time
    logger.info(f"\nTotal run time: {total_time:.2f} seconds")


if __name__ == "__main__":
    main()