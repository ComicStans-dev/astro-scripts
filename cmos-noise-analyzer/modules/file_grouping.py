# file_grouping.py

import os
from astropy.io import fits
from modules.utilities import get_header_value, logger

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