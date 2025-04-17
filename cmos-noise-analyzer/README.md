# CMOS Noise Analyzer 📷📉

This project analyzes sets of FITS files (typically dark frames) from a CMOS camera to characterize sensor noise properties under different conditions (GAIN, Temperature).

## Functionality 🛠️

The main script (`main.py`) performs the following steps:

1.  **Configuration:** Reads settings from `modules/config.py`, including the path to FITS files, the specific exposure time (`EXPTIME`) to analyze, the output path for the summary CSV, and the directory for saving plots.
2.  **File Discovery:** Scans the specified directory for `.fits` files.
3.  **Filtering & Grouping:** Filters files matching the configured `EXPTIME` and groups them based on unique combinations of `GAIN` and `SET-TEMP` values found in their FITS headers.
4.  **Data Processing:** For each group:
    *   Reads the image data from each FITS file.
    *   Extracts the `EGAIN` value from the header.
    *   Converts pixel values from 16-bit to 12-bit (assuming camera native bit depth).
    *   Calculates a cumulative histogram (pixel counts vs. intensity) for all files in the group.
    *   Calculates the average `EGAIN` for the group.
5.  **Metrics Calculation:** Calculates key metrics from the cumulative histogram for each group, using the average `EGAIN` to convert intensities to electron counts:
    *   Peak Frequency
    *   Peak Electron Count (location of the peak)
    *   Full Width at Half Maximum (FWHM) of the peak
    *   Mean Electron Count
    *   Median Electron Count
    *   Standard Deviation of Electron Counts
6.  **Output:**
    *   Saves the calculated metrics for all processed groups into a CSV file (path specified in `config.py`).
    *   Displays a plot of the histogram for each group (can be disabled in `histogram_metrics.py`).

## Project Structure 📁

```
cmos-noise-analyzer/
├── main.py                # Main execution script
├── README.md              # This file
├── modules/               # Core logic modules
│   ├── __init__.py
│   ├── config.py          # Configuration settings (paths, EXPTIME)
│   ├── data_processing.py # Handles FITS reading, data extraction, histogram accumulation
│   ├── file_grouping.py   # Groups FITS files by header parameters
│   ├── gaussian_fitting.py # Functions for Gaussian fitting (optional/future use)
│   ├── histogram_metrics.py # Calculates metrics from histograms
│   ├── utilities.py       # Helper functions (logging, header reading)
│   └── visualization.py   # Plotting functions (optional/future use)
├── plots/                 # Default directory for output plots
└── (output files like gaussian_fit_summary.csv) # Generated output
```

## Setup and Usage 🚀

1.  **Prerequisites:**
    *   Python 3.x
    *   Required libraries: `numpy`, `astropy`, `matplotlib` (and potentially `scipy` if using Gaussian fitting). It's highly recommended to use a virtual environment.
    ```bash
    # Assuming you are in the astro-scripts root directory
    python -m venv .venv
    source .venv/bin/activate # or .\.venv\Scripts\activate on Windows
    pip install numpy astropy matplotlib scipy
    # Consider creating a requirements.txt: pip freeze > requirements.txt
    ```
2.  **Configuration:**
    *   Edit `cmos-noise-analyzer/modules/config.py`.
    *   Set `DIRECTORY_PATH` to the folder containing your FITS dark frames.
    *   Set `EXPTIME_VALUE` to the specific exposure time (in seconds) you want to analyze (e.g., `0.0001` for bias frames, `300` for 5-min darks).
    *   Verify or change `SUMMARY_CSV_PATH` for the output CSV file.
    *   Verify or change `PLOTS_DIRECTORY` for output plots.
3.  **Run Analysis:**
    *   Navigate to the `astro-scripts` root directory in your terminal (or ensure the `cmos-noise-analyzer` directory is in your Python path).
    *   Execute the main script:
        ```bash
        python cmos-noise-analyzer/main.py
        ```
4.  **Output:**
    *   Check the terminal for log messages during processing.
    *   Find the summary results in the CSV file specified in `config.py`.
    *   Find any generated plots in the directory specified in `config.py`.

## Future Enhancements ✨

*   Integrate the `gaussian_fitting.py` module into the main workflow to calculate fit parameters alongside histogram metrics.
*   Utilize `visualization.py` to generate and save plots of the Gaussian fits and potentially overlay plots comparing different groups.
*   Add command-line arguments for configuration instead of solely relying on `config.py`. 