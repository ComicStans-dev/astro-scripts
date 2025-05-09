import re
import os
import csv
import pandas as pd # Added for DataFrames

# Path helpers
from utils.paths import RAW_DIR, out_path

# Define constants
AUTORUN_LOG_PREFIX = "Autorun_Log"  # Prefix for autorun log files

# Ensure raw dir
if not RAW_DIR:
    raise ValueError("RAW_DIR (or legacy DIRECTORY) not set in environment variables or .env file.")

# Define output CSV filenames
OUTPUT_CSV_FILES = {
    'autofocus': 'autofocus_events.csv',
    'autorun': 'autorun_events.csv',
    'target_coordinates': 'target_coordinates.csv',
    'tracking': 'tracking_events.csv',
    'guide': 'guide_events.csv',
    'exposure': 'exposure_events.csv',
    'plate_solve': 'plate_solve_events.csv',
    'meridian_flip': 'meridian_flip_events.csv',
    'auto_center': 'auto_center_events.csv',
    'mount_slew': 'mount_slew_events.csv',
    'wait': 'wait_events.csv',
    'logging': 'logging_events.csv'
}

# Compile regex patterns for each event type
REGEX_PATTERNS = {
    'autofocus_begin': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[AutoFocus\|Begin\] (.+)'),
    'autofocus_end_success': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Auto focus succeeded, the focused position is (\d+)'),
    'autofocus_end_failure': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[AutoFocus\|End\] Auto focus failed'),

    'autorun_begin': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Autorun\|Begin\] (.+)'),
    'autorun_end': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Autorun\|End\] (.+)'),

    'target_coordinates': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Target RA:(\d+h\d+m\d+s) DEC:([+-]\d+°\d+\'\d+")'),

    'tracking_start': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Start Tracking'),
    'tracking_stop': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Stop Tracking'),

    'guide_stop_guiding': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Guide\] Stop Guiding'),
    'guide_start_guiding': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Guide\] Start Guiding'),
    'guide_star_lost': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Guide\] Guide star lost'),
    'guide_reselect_star': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Guide\] ReSelect Guide star'),
    'guide_settle': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Guide\] Guide Settle'),
    'guide_settle_done': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Guide\] Settle Done'),
    'guide_settle_failed': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Guide\] Settle failed'),
    'guide_select_failed': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Guide\] Select Guide Star failed, no star found'),

    'exposure': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Exposure (\d+\.\d+)s image (\d+)#'),

    'plate_solve_begin': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Plate Solve'),
    'plate_solve_success': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Solve succeeded: RA:(\d+h\d+m\d+s) DEC:([+-]\d+°\d+\'\d+") Angle = ([\d\.]+), Star number = (\d+)'),

    'meridian_flip_begin': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Meridian Flip\|Begin\] (.+)'),
    'meridian_flip_start': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Meridian Flip (\d+)# Start'),
    'meridian_flip_end': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[Meridian Flip\|End\] (.+)'),

    'auto_center_begin': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[AutoCenter\|Begin\] Auto-Center (\d+)#'),
    'auto_center_end': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) .*?\[AutoCenter\|End\] (.+)'),

    'mount_slew': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Mount slews to target position: RA:(\d+h\d+m\d+s) DEC:([+-]\d+°\d+\'\d+")'),

    'wait_message': re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) (Wait .*?)'),

    'logging_enabled': re.compile(r'Log enabled at (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})'),
    'logging_disabled': re.compile(r'Log disabled at (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})')
}

# Initialize data containers for each event type
EVENT_DATA = {
    'autofocus': [],
    'autorun': [],
    'target_coordinates': [],
    'tracking': [],
    'guide': [],
    'exposure': [],
    'plate_solve': [],
    'meridian_flip': [],
    'auto_center': [],
    'mount_slew': [],
    'wait': [],
    'logging': []
}

def parse_log_file_to_data_lists(file_path):
    """
    Parses a single log file to extract various events into lists of dicts.
    This is an internal helper for generate_event_dataframes.

    Args:
        file_path (str): The path to the log file.
    Returns:
        dict: A dictionary where keys are event types and values are lists of event data (dicts).
    """
    # Initialize local data containers for this parse run
    # Use a copy of OUTPUT_CSV_FILES keys to define the structure for event data lists
    local_event_data_keys = list(OUTPUT_CSV_FILES.keys()) 
    local_event_data = {key: [] for key in local_event_data_keys}

    try:
        with open(file_path, 'r', encoding='utf-8') as file: # Added encoding
            for line in file:
                # Autofocus Begin
                match = REGEX_PATTERNS['autofocus_begin'].search(line)
                if match:
                    local_event_data['autofocus'].append({
                        'Timestamp': match.group(1), # Changed to Timestamp for consistency
                        'Event_Type': 'Begin',      # Changed to Event_Type
                        'Details':    match.group(2),
                        'Final_Focus_Position': pd.NA, # Use pd.NA for missing
                        'Status': 'N/A' # Status captured by Event_Type
                    })
                    continue

                # Autofocus End Success
                match = REGEX_PATTERNS['autofocus_end_success'].search(line)
                if match:
                    local_event_data['autofocus'].append({
                        'Timestamp': match.group(1),
                        'Event_Type': 'End',
                        'Details':    'Autofocus Succeeded',
                        'Final_Focus_Position': match.group(2),
                        'Status':               'Success'
                    })
                    continue

                # Autofocus End Failure
                match = REGEX_PATTERNS['autofocus_end_failure'].search(line)
                if match:
                    local_event_data['autofocus'].append({
                        'Timestamp': match.group(1),
                        'Event_Type': 'End',
                        'Details':    'Autofocus Failed',
                        'Final_Focus_Position': pd.NA,
                        'Status':               'Failure'
                    })
                    continue

                # Autorun Begin
                match = REGEX_PATTERNS['autorun_begin'].search(line)
                if match:
                    local_event_data['autorun'].append({
                        'Timestamp': match.group(1),
                        'Event_Type': 'Begin',
                        'Details':    match.group(2)
                    })
                    continue

                # Autorun End
                match = REGEX_PATTERNS['autorun_end'].search(line)
                if match:
                    local_event_data['autorun'].append({
                        'Timestamp': match.group(1),
                        'Event_Type': 'End',
                        'Details':  match.group(2)
                    })
                    continue
                
                match = REGEX_PATTERNS['target_coordinates'].search(line)
                if match:
                    # Ensure 'target_coordinates' key exists if it was missed in OUTPUT_CSV_FILES based init
                    if 'target_coordinates' not in local_event_data: 
                        local_event_data['target_coordinates'] = []
                    local_event_data['target_coordinates'].append({
                        'Timestamp': match.group(1),
                        'RA':        match.group(2),
                        'DEC':       match.group(3)
                    })
                    continue
                
                # Tracking Start
                match = REGEX_PATTERNS['tracking_start'].search(line)
                if match:
                    local_event_data['tracking'].append({
                        'Timestamp':  match.group(1),
                        'Event_Type': 'Start'
                    })
                    continue

                # Tracking Stop
                match = REGEX_PATTERNS['tracking_stop'].search(line)
                if match:
                    local_event_data['tracking'].append({
                        'Timestamp':  match.group(1),
                        'Event_Type': 'Stop'
                    })
                    continue

                # Guide Events
                for guide_event_key, guide_event_name in [
                    ('guide_stop_guiding', 'Stop Guiding'),
                    ('guide_start_guiding', 'Start Guiding'),
                    ('guide_star_lost', 'Guide Star Lost'),
                    ('guide_reselect_star', 'ReSelect Guide Star'),
                    ('guide_settle', 'Guide Settle'),
                    ('guide_settle_done', 'Settle Done'),
                    ('guide_settle_failed', 'Settle Failed'),
                    ('guide_select_failed', 'Select Guide Star Failed')
                ]:
                    match = REGEX_PATTERNS[guide_event_key].search(line)
                    if match:
                        details = match.group(2) if len(match.groups()) > 1 else ''
                        if guide_event_key == 'guide_select_failed': details = 'no star found' # specific detail
                        local_event_data['guide'].append({
                            'Timestamp':  match.group(1),
                            'Event_Type': guide_event_name,
                            'Details':    details
                        })
                        break # Found a guide event, move to next line
                if match: continue # If any guide event matched and broke inner loop

                # Exposure
                match = REGEX_PATTERNS['exposure'].search(line)
                if match:
                    local_event_data['exposure'].append({
                        'Timestamp':   match.group(1),
                        'Exposure_s': match.group(2), # Renamed for clarity
                        'Image_Num':   match.group(3)  # Renamed for clarity
                    })
                    continue

                # Plate Solve Begin
                match = REGEX_PATTERNS['plate_solve_begin'].search(line)
                if match:
                    local_event_data['plate_solve'].append({
                        'Timestamp': match.group(1),
                        'Event_Type': 'Begin',
                        'RA': pd.NA, 'DEC': pd.NA, 'Angle': pd.NA, 'Star_Count': pd.NA 
                    })
                    continue
                
                # Plate Solve Success
                match = REGEX_PATTERNS['plate_solve_success'].search(line)
                if match:
                    local_event_data['plate_solve'].append({
                        'Timestamp':  match.group(1),
                        'Event_Type': 'Success',
                        'RA':         match.group(2),
                        'DEC':        match.group(3),
                        'Angle':      match.group(4),
                        'Star_Count': match.group(5)
                    })
                    continue

                # Meridian Flip Begin
                match = REGEX_PATTERNS['meridian_flip_begin'].search(line)
                if match:
                    local_event_data['meridian_flip'].append({
                        'Timestamp':  match.group(1),
                        'Event_Type': 'Begin',
                        'Details':    match.group(2)
                    })
                    continue
                
                match = REGEX_PATTERNS['meridian_flip_start'].search(line)
                if match:
                    local_event_data['meridian_flip'].append({
                        'Timestamp': match.group(1),
                        'Event_Type': 'Start Action',
                        'Details': f"Flip #{match.group(2)}"
                    })
                    continue
                
                match = REGEX_PATTERNS['meridian_flip_end'].search(line)
                if match:
                    local_event_data['meridian_flip'].append({
                        'Timestamp':  match.group(1),
                        'Event_Type': 'End',
                        'Details':    match.group(2)
                    })
                    continue

                # Auto-Center Begin
                match = REGEX_PATTERNS['auto_center_begin'].search(line)
                if match:
                    local_event_data['auto_center'].append({
                        'Timestamp':  match.group(1),
                        'Event_Type': 'Begin',
                        'Details':    f"Auto-Center #{match.group(2)}"
                    })
                    continue

                match = REGEX_PATTERNS['auto_center_end'].search(line)
                if match:
                    local_event_data['auto_center'].append({
                        'Timestamp':  match.group(1),
                        'Event_Type': 'End',
                        'Details':    match.group(2)
                    })
                    continue
                
                match = REGEX_PATTERNS['mount_slew'].search(line)
                if match:
                    # Ensure 'mount_slew' key exists
                    if 'mount_slew' not in local_event_data: 
                        local_event_data['mount_slew'] = []
                    local_event_data['mount_slew'].append({
                        'Timestamp': match.group(1),
                        'RA':        match.group(2),
                        'DEC':       match.group(3)
                    })
                    continue

                match = REGEX_PATTERNS['wait_message'].search(line)
                if match:
                    # Ensure 'wait' key exists
                    if 'wait' not in local_event_data: 
                        local_event_data['wait'] = []
                    local_event_data['wait'].append({
                        'Timestamp': match.group(1),
                        'Message':   match.group(2)
                    })
                    continue
                
                # Logging Enabled / Disabled
                for log_event_key, log_event_name in [
                    ('logging_enabled', 'Enabled'),
                    ('logging_disabled', 'Disabled')
                ]:
                    match = REGEX_PATTERNS[log_event_key].search(line)
                    if match:
                        # Ensure 'logging' key exists
                        if 'logging' not in local_event_data: 
                            local_event_data['logging'] = []
                        local_event_data['logging'].append({
                            'Timestamp':  match.group(1),
                            'Event_Type': log_event_name
                        })
                        break 
                if match: continue

    except FileNotFoundError:
        print(f"[autofocus_analysis] Log file not found: {file_path}")
    except Exception as e:
        print(f"[autofocus_analysis] Error parsing log file {file_path}: {e}")
    return local_event_data

def find_log_files(directory, prefix):
    """
    Finds all log files in a directory that start with the given prefix.

    Args:
        directory (str): The directory to search for log files.
        prefix (str): The prefix that log files should start with.

    Returns:
        list: A list of file paths matching the prefix.
    """
    return [
        os.path.join(directory, file)
        for file in os.listdir(directory)
        if file.startswith(prefix) and file.endswith('.txt')  # Assuming log files have .txt extension
    ]

def write_csv_from_df(event_type_key, df, base_filename_map):
    """Writes a DataFrame to a CSV file if it's not empty."""
    if df.empty:
        if os.getenv("DEBUG") == "1":
            print(f"[autofocus_analysis] No data for {event_type_key}, CSV not written.")
        return

    csv_filename = base_filename_map.get(event_type_key)
    if not csv_filename:
        if os.getenv("DEBUG") == "1":
            print(f"[autofocus_analysis] No CSV output filename defined for {event_type_key}")
        return

    output_file = out_path(csv_filename)
    try:
        df.to_csv(output_file, index=False)
        # Print only on debug or standalone, and not when imported by run_all.py for Excel generation
        if os.getenv("DEBUG") == "1" or (__name__ == "__main__" and not sys.argv[0].endswith('run_all.py')):
            print(f"[autofocus_analysis] {event_type_key.replace('_', ' ').capitalize()} events have been written to {output_file}")
    except Exception as e:
        print(f"[autofocus_analysis] Error writing CSV for {event_type_key} to {output_file}: {e}")

def generate_event_dataframes():
    """Processes autorun logs and returns a dictionary of DataFrames, one for each event type."""
    if not RAW_DIR or not os.path.exists(RAW_DIR):
        print(f"[autofocus_analysis] RAW_DIR not found or not set: {RAW_DIR}")
        return {}
    
    log_files = find_log_files(RAW_DIR, AUTORUN_LOG_PREFIX)
    if not log_files:
        print(f"[autofocus_analysis] No autorun logs found with prefix '{AUTORUN_LOG_PREFIX}' in {RAW_DIR}")
        return {}

    latest_log_file = sorted(log_files)[-1] 
    if os.getenv("DEBUG") == "1" or (__name__ == "__main__" and not sys.argv[0].endswith('run_all.py')):
         print(f"[autofocus_analysis] Parsing log file: {latest_log_file}")
    
    parsed_data_lists = parse_log_file_to_data_lists(latest_log_file)

    event_dataframes = {}
    for event_type, data_list in parsed_data_lists.items():
        if data_list: 
            df = pd.DataFrame(data_list)
            # Standardize column names for better consistency if needed here
            # Example: df.columns = [col.replace(' ', '_').replace('#', 'Num') for col in df.columns]
            event_dataframes[event_type] = df
        else:
            if os.getenv("DEBUG") == "1":
                print(f"[autofocus_analysis] No data found for event type: {event_type}")
    
    return event_dataframes

def main():
    # This function is now primarily for standalone execution.
    # run_all.py will call generate_event_dataframes() directly.
    event_dataframes = generate_event_dataframes()

    if __name__ == "__main__": 
        if not event_dataframes:
            print("[autofocus_analysis] No event dataframes were generated.")
            return
        # Use a fresh copy of OUTPUT_CSV_FILES for standalone CSV writing
        standalone_csv_map = OUTPUT_CSV_FILES.copy()
        for event_type, df in event_dataframes.items():
            write_csv_from_df(event_type, df, standalone_csv_map)
    
    return event_dataframes 

if __name__ == '__main__':
    import sys # Needed for the check in write_csv_from_df
    main()
