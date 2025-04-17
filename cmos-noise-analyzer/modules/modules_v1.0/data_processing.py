# data_processing.py

import os
import numpy as np
from astropy.io import fits
from modules.utilities import get_header_value, logger

def process_group(file_list):
    """
    Processes a group of FITS files to compute cumulative pixel counts and average EGAIN.

    Parameters:
        file_list (list of str): List of FITS file paths in the group.

    Returns:
        cumulative_pixel_counts (array): Array of cumulative pixel counts.
        average_egain (float): Average EGAIN value across files.
    """
    cumulative_pixel_counts = None
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

                # Convert from 16-bit to 12-bit space using bit-shift
                pixel_values = data.flatten() >> 4  # Efficient bit-shift operation

                # Update cumulative pixel counts using numpy bincount
                counts = np.bincount(pixel_values, minlength=4096)
                if cumulative_pixel_counts is None:
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
