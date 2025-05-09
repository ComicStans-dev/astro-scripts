# Astro Session Reporter 🔭📝

This project is a modular Python toolkit for analyzing, synchronizing, and reporting on astrophotography session data. It fuses FITS headers, guiding logs (like those from PHD2, commonly used with systems such as ASIAIR), and acquisition logs (e.g., from N.I.N.A.) into unified, machine-readable outputs for deep session QA and science. The primary output is a comprehensive Excel file.

## Key Features 🛠️

- **Unified Excel Report:** Consolidates data from various sources into a single `.xlsx` file with multiple sheets:
    - **Alt/Az Stats**: Per-frame statistics including Altitude/Azimuth, mean/std dev of pixel values, **Mean Half-Flux Radius (HFR)**, **Standard Deviation of HFR**, **Number of Stars Detected**, **Moon Altitude**, **Moon Separation from Target**, and **Moon Illumination Percentage**.
    - **PHD2 Per-Image Stats**: Guiding performance (RMS error in RA/Dec in arcseconds and microns, star loss count) for each image exposure.
    - **PHD2 Overall Stats**: Session-wide guiding RMS error.
    - **PHD2 Header**: Detailed PHD2 guiding parameters and equipment configuration from the first PHD2 log, including **descriptions for each parameter**.
    - **FITS Header**: Full FITS header from the first image processed.
    - **Autofocus Log**: Data from N.I.N.A.'s autofocus routine logs (if present).
    - **Unified Log**: A combined, time-sorted log of guiding and imaging events (legacy from CSV workflow).
- **FITS File Analysis**:
    - Extracts RA/Dec, timestamp, mean/std dev of pixel data.
    - Calculates Alt/Az coordinates based on observer location (set in `.env`).
    - **NEW**: Performs star detection using the `sep` library (Source Extractor Python) to calculate HFR for sharpness assessment.
    - **NEW**: Calculates moon position and illumination for each frame.
- **PHD2 Log Analysis**:
    - Parses guide frame data (RA/Dec errors) and identifies "star lost" events.
    - Calculates RMS guiding error per image and overall.
    - **NEW**: Extracts detailed header information with parameter descriptions.
- **N.I.N.A. Log Parsing (Optional)**: While the core FITS and PHD2 analysis is broadly applicable (e.g., to ASIAIR-generated data), the tool can also parse N.I.N.A. autofocus logs for HFR, temperature, and step position if such logs are present.
- **Unified Time Synchronization:** Robust timestamp parsing and normalization across FITS, PHD2, and Autorun logs (see `shared/timestamp_utils.py`).
- **Modular Parsers:** Dedicated modules for FITS headers, guiding logs, and autorun logs (see `parsers/`).
- **Event Extraction:** Autofocus, guiding, plate solve, meridian flip, and more, with each event type output to its own CSV (legacy, primary output is now Excel).
- **Guiding & Image QA:** Per-exposure RMS, star-lost counts, Alt/Az, and image stats.
- **Rich Terminal UI:** `run_all.py` orchestrates the full pipeline with a colorful, interactive status display.
- **Unified CSV Output (Legacy):** Generates a single, chronologically-ordered CSV merging all key metrics per exposure (see `final_output/generate_unified_csv.py`). The Excel report is now the primary rich output.

## Project Structure 📁

```
astro-session-reporter/
├── run_all.py                  # Main orchestrator with rich terminal UI
├── phd2_error_anaylsis.py      # Per-exposure guiding analysis
├── altaz_stats_calculator.py   # Alt/Az and image stats from FITS
├── autofocus_analysis.py       # Log/event parser (autofocus, guiding, etc)
├── final_output/
│   └── generate_unified_csv.py # Merges all data into a unified CSV
├── shared/
│   └── timestamp_utils.py      # Timestamp parsing, normalization, comparison
├── utils/
│   ├── paths.py                # Path/env helpers
│   └── session_model.py        # Data models for exposures, guides, events
├── parsers/
│   ├── fits_parser.py          # FITS header → ImageFrame
│   ├── autorun_parser.py       # Autorun log → ExposureMeta
│   └── phd2_parser.py          # PHD2 log → GuideFrame/GuideEvent
├── correlator/
│   └── associate.py            # Associates exposures ↔ images ↔ guides/events
├── output/                     # All generated CSVs and reports
└── README.md                   # This file
```

## Configuration ⚙️

Set these in a `.env` file at the project root or as environment variables:

```env
# 🗂️ Directory containing FITS files and log files (REQUIRED)
RAW_DIR="/path/to/your/imaging/session/data"

💾 # Directory for output files (optional, defaults to RAW_DIR)
REPORTS_DIR="/path/to/output/directory" # For Excel reports, defaults to 'astro-session-reporter/final_output/'

🛸 # Observer Location (for Alt/Az, HFR, and Moon calculations - VERY IMPORTANT)
# Example: Area 51 coordinates 👽
OBSERVER_LAT=37.24804
OBSERVER_LON=-115.800155
OBSERVER_HEIGHT=1350
```

## Setup and Usage 🚀

1. **Install dependencies:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # or .venv\Scripts\activate on Windows
    pip install astropy numpy python-dotenv rich pytz pandas openpyxl sep
    ```
    *(Consider creating a `requirements.txt` file for easier dependency management.)*
2. **Configure:**
    - Create a `.env` file as above, or set env vars. Ensure `RAW_DIR` points to your session data and `OBSERVER_LAT`, `OBSERVER_LON`, `OBSERVER_HEIGHT` are accurately set for your location.
3. **Run all analyses:**
    ```bash
    python astro-session-reporter/run_all.py
    ```
    This will generate an Excel report in the `astro-session-reporter/final_output/` directory.

    **Debug Mode for Detailed Console Output:**
    To enable detailed debug logs from various modules (especially `altaz_stats_calculator.py` and `phd2_error_anaylsis.py`), set the `DEBUG` environment variable to `1` before running:

    *PowerShell (Windows):*
    ```powershell
    $env:DEBUG = "1"
    python astro-session-reporter/run_all.py
    $env:DEBUG = "" # Unset after running
    ```

    *Bash (Linux/macOS):*
    ```bash
    DEBUG=1 python astro-session-reporter/run_all.py
    ```
    The `run_all.py` script also accepts a `--debug` flag which may enable some top-level debug prints, but `DEBUG=1` provides more comprehensive module-level diagnostics.

4. **Run individual modules:**
    ```bash
    python astro-session-reporter/phd2_error_anaylsis.py
    python astro-session-reporter/altaz_stats_calculator.py
    python astro-session-reporter/autofocus_analysis.py
    python astro-session-reporter/final_output/generate_unified_csv.py --raw-dir "astro-session-reporter/output"
    ```
5. **Output:**
    - All CSVs and reports are written to `REPORTS_DIR` (or `RAW_DIR` if unset). The primary comprehensive report is the Excel file in `astro-session-reporter/final_output/`.
    - The unified CSV merges all exposures, guiding, and event data for downstream analysis.

## Advanced Notes 📌

- **Timestamp Handling:** All modules use `shared/timestamp_utils.py` for robust, cross-format time parsing and UTC normalization.
- **Extensibility:** Add new event types or data sources by extending the relevant parser and updating the session model.
- **Error Handling:** The pipeline is resilient—errors in one module do not halt the rest.
- **Output Schema:** Refer to the headers in the generated Excel sheets and CSV files for all available columns. New columns include HFR statistics (hfr_mean, hfr_std, n_stars) and moon parameters (moon_alt, moon_sep, moon_illum).
- **Windows Paths:** Use forward slashes (`/`) in `.env` paths to avoid control character issues.
- **Multiple PHD2 Logs:** The `phd2_error_anaylsis.py` script will automatically find, parse, and combine data from all `PHD2_GuideLog*.txt` files found in the `RAW_DIR` for a comprehensive session analysis.

## Credits & License

MIT License. Contributions welcome! 