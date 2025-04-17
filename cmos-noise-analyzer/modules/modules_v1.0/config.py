import os

# Directory containing your FITS files
DIRECTORY_PATH = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\FITS_Files'

# EXPTIME value to match
EXPTIME_VALUE = 0.0001  # Update as needed

# Output path for the summary CSV file
SUMMARY_CSV_PATH = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\gaussian_fit_summary.csv'

# Directory to save plots
PLOTS_DIRECTORY = r'C:\Users\Dane\Documents\N.I.N.A\Python Scripts\Plots'

# Ensure the plots directory exists
os.makedirs(PLOTS_DIRECTORY, exist_ok=True)