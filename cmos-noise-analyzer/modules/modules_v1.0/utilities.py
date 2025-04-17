# utilities.py

import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

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