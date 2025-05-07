# Astro Session Reporter 🔭📝

This project is a modular Python toolkit for analyzing, synchronizing, and reporting on astrophotography session data. It fuses FITS headers, guiding logs, and acquisition logs into unified, machine-readable outputs for deep session QA and science.

## Key Features 🛠️

- **Unified Time Synchronization:** Robust timestamp parsing and normalization across FITS, PHD2, and Autorun/NINA logs (see `shared/timestamp_utils.py`).
- **Modular Parsers:** Dedicated modules for FITS headers, guiding logs, and autorun logs (see `parsers/`).
- **Event Extraction:** Autofocus, guiding, plate solve, meridian flip, and more, with each event type output to its own CSV.
- **Guiding & Image QA:** Per-exposure RMS, star-lost counts, Alt/Az, and image stats.
- **Rich Terminal UI:** `run_all.py` orchestrates the full pipeline with a colorful, interactive status display.
- **Unified Output:** Generates a single, chronologically-ordered CSV merging all key metrics per exposure (see `final_output/generate_unified_csv.py`).

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
REPORTS_DIR="/path/to/output/directory"

🛸 # Observer Location (for Alt/Az calculations)
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
    pip install astropy numpy python-dotenv rich pytz
    ```
2. **Configure:**
    - Create a `.env` file as above, or set env vars.
3. **Run all analyses:**
    ```bash
    python astro-session-reporter/run_all.py
    # or with debug output:
    python astro-session-reporter/run_all.py --debug
    ```
4. **Run individual modules:**
    ```bash
    python astro-session-reporter/phd2_error_anaylsis.py
    python astro-session-reporter/altaz_stats_calculator.py
    python astro-session-reporter/autofocus_analysis.py
    python astro-session-reporter/final_output/generate_unified_csv.py --raw-dir "astro-session-reporter/output"
    ```
5. **Output:**
    - All CSVs and reports are written to `REPORTS_DIR` (or `RAW_DIR` if unset).
    - The unified CSV merges all exposures, guiding, and event data for downstream analysis.

## Advanced Notes 📌

- **Timestamp Handling:** All modules use `shared/timestamp_utils.py` for robust, cross-format time parsing and UTC normalization.
- **Extensibility:** Add new event types or data sources by extending the relevant parser and updating the session model.
- **Error Handling:** The pipeline is resilient—errors in one module do not halt the rest.
- **CSV Schema:** See the header of the unified CSV for all available columns (exposure, Alt/Az, RMS, star-lost, mean_pix, etc).
- **Windows Paths:** Use forward slashes (`/`) in `.env` paths to avoid control character issues.

## Credits & License

MIT License. Contributions welcome! 