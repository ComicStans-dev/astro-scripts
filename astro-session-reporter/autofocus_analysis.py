import re
import os
import csv

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

def parse_log_file(file_path):
    """
    Parses a single log file to extract various events.

    Args:
        file_path (str): The path to the log file.
    """
    try:
        with open(file_path, 'r') as file:
            for line in file:
                # Autofocus Begin
                match = REGEX_PATTERNS['autofocus_begin'].search(line)
                if match:
                    EVENT_DATA['autofocus'].append({
                        'Start Time': match.group(1),
                        'Details':    match.group(2)
                    })
                    continue

                # Autofocus End Success
                match = REGEX_PATTERNS['autofocus_end_success'].search(line)
                if match:
                    EVENT_DATA['autofocus'].append({
                        'End Time':             match.group(1),
                        'Final Focus Position': match.group(2),
                        'Status':               'Success'
                    })
                    continue

                # Autofocus End Failure
                match = REGEX_PATTERNS['autofocus_end_failure'].search(line)
                if match:
                    EVENT_DATA['autofocus'].append({
                        'End Time':             match.group(1),
                        'Final Focus Position': 'Failed',
                        'Status':               'Failure'
                    })
                    continue

                # Autorun Begin
                match = REGEX_PATTERNS['autorun_begin'].search(line)
                if match:
                    EVENT_DATA['autorun'].append({
                        'Start Time': match.group(1),
                        'Details':    match.group(2)
                    })
                    continue

                # Autorun End
                match = REGEX_PATTERNS['autorun_end'].search(line)
                if match:
                    EVENT_DATA['autorun'].append({
                        'End Time': match.group(1),
                        'Details':  match.group(2)
                    })
                    continue

                # Target Coordinates
                match = REGEX_PATTERNS['target_coordinates'].search(line)
                if match:
                    EVENT_DATA['target_coordinates'].append({
                        'Timestamp': match.group(1),
                        'RA':        match.group(2),
                        'DEC':       match.group(3)
                    })
                    continue

                # Tracking Start
                match = REGEX_PATTERNS['tracking_start'].search(line)
                if match:
                    EVENT_DATA['tracking'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Start'
                    })
                    continue

                # Tracking Stop
                match = REGEX_PATTERNS['tracking_stop'].search(line)
                if match:
                    EVENT_DATA['tracking'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Stop'
                    })
                    continue

                # Guide Events
                # Guide Stop Guiding
                match = REGEX_PATTERNS['guide_stop_guiding'].search(line)
                if match:
                    EVENT_DATA['guide'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Stop Guiding',
                        'Details':    ''
                    })
                    continue

                # Guide Start Guiding
                match = REGEX_PATTERNS['guide_start_guiding'].search(line)
                if match:
                    EVENT_DATA['guide'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Start Guiding',
                        'Details':    ''
                    })
                    continue

                # Guide Star Lost
                match = REGEX_PATTERNS['guide_star_lost'].search(line)
                if match:
                    EVENT_DATA['guide'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Guide Star Lost',
                        'Details':    ''
                    })
                    continue

                # Guide ReSelect Guide Star
                match = REGEX_PATTERNS['guide_reselect_star'].search(line)
                if match:
                    EVENT_DATA['guide'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'ReSelect Guide Star',
                        'Details':    ''
                    })
                    continue

                # Guide Settle
                match = REGEX_PATTERNS['guide_settle'].search(line)
                if match:
                    EVENT_DATA['guide'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Guide Settle',
                        'Details':    ''
                    })
                    continue

                # Guide Settle Done
                match = REGEX_PATTERNS['guide_settle_done'].search(line)
                if match:
                    EVENT_DATA['guide'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Settle Done',
                        'Details':    ''
                    })
                    continue

                # Guide Settle Failed
                match = REGEX_PATTERNS['guide_settle_failed'].search(line)
                if match:
                    EVENT_DATA['guide'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Settle Failed',
                        'Details':    ''
                    })
                    continue

                # Guide Select Failed
                match = REGEX_PATTERNS['guide_select_failed'].search(line)
                if match:
                    EVENT_DATA['guide'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Select Guide Star Failed',
                        'Details':    'No star found'
                    })
                    continue

                # Exposure Events
                match = REGEX_PATTERNS['exposure'].search(line)
                if match:
                    EVENT_DATA['exposure'].append({
                        'Timestamp':         match.group(1),
                        'Exposure Time (s)': match.group(2),
                        'Image Number':      match.group(3)
                    })
                    continue

                # Plate Solve Begin
                match = REGEX_PATTERNS['plate_solve_begin'].search(line)
                if match:
                    EVENT_DATA['plate_solve'].append({
                        'Timestamp':   match.group(1),
                        'Status':      'Begin',
                        'RA':          '',
                        'DEC':         '',
                        'Angle':       '',
                        'Star Number': ''
                    })
                    continue

                # Plate Solve Success
                match = REGEX_PATTERNS['plate_solve_success'].search(line)
                if match:
                    EVENT_DATA['plate_solve'].append({
                        'Timestamp':   match.group(1),
                        'Status':      'Succeeded',
                        'RA':          match.group(2),
                        'DEC':         match.group(3),
                        'Angle':       match.group(4),
                        'Star Number': match.group(5)
                    })
                    continue

                # Meridian Flip Begin
                match = REGEX_PATTERNS['meridian_flip_begin'].search(line)
                if match:
                    EVENT_DATA['meridian_flip'].append({
                        'Start Time': match.group(1),
                        'Details':    match.group(2),
                        'Event':      '' # Placeholder, might be updated by other events
                    })
                    continue

                # Meridian Flip Start
                match = REGEX_PATTERNS['meridian_flip_start'].search(line)
                if match:
                    # Note: This might create a separate entry from Begin/End
                    EVENT_DATA['meridian_flip'].append({
                        'Timestamp':  match.group(1),
                        'Event':      f'Meridian Flip {match.group(2)}# Start',
                        'Start Time': '', # Not captured in this line
                        'End Time':   '', # Not captured in this line
                        'Details':    ''  # Not captured in this line
                    })
                    continue

                # Meridian Flip End
                match = REGEX_PATTERNS['meridian_flip_end'].search(line)
                if match:
                    EVENT_DATA['meridian_flip'].append({
                        'End Time':   match.group(1),
                        'Details':    match.group(2),
                        'Event':      '', # Placeholder
                        'Start Time': ''  # Placeholder
                    })
                    continue

                # Auto-Center Begin
                match = REGEX_PATTERNS['auto_center_begin'].search(line)
                if match:
                    EVENT_DATA['auto_center'].append({
                        'Start Time':         match.group(1),
                        'Auto-Center Number': match.group(2),
                        'End Time':           '', # Placeholder
                        'Details':            ''  # Placeholder
                    })
                    continue

                # Auto-Center End
                match = REGEX_PATTERNS['auto_center_end'].search(line)
                if match:
                    EVENT_DATA['auto_center'].append({
                        'End Time':           match.group(1),
                        'Details':            match.group(2),
                        'Start Time':         '', # Placeholder
                        'Auto-Center Number': ''  # Placeholder
                    })
                    continue

                # Mount Slew Events
                match = REGEX_PATTERNS['mount_slew'].search(line)
                if match:
                    EVENT_DATA['mount_slew'].append({
                        'Timestamp': match.group(1),
                        'RA':        match.group(2),
                        'DEC':       match.group(3)
                    })
                    continue

                # Wait Messages
                match = REGEX_PATTERNS['wait_message'].search(line)
                if match:
                    EVENT_DATA['wait'].append({
                        'Timestamp':    match.group(1),
                        'Wait Message': match.group(2)
                    })
                    continue

                # Logging Enabled
                match = REGEX_PATTERNS['logging_enabled'].search(line)
                if match:
                    EVENT_DATA['logging'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Enabled'
                    })
                    continue

                # Logging Disabled
                match = REGEX_PATTERNS['logging_disabled'].search(line)
                if match:
                    EVENT_DATA['logging'].append({
                        'Timestamp':  match.group(1),
                        'Event Type': 'Disabled'
                    })
                    continue

    except FileNotFoundError:
        print(f"Error: Log file not found at {file_path}")
    except Exception as e:
        print(f"An error occurred while parsing {file_path}: {e}")

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

def write_csv(event_type, data):
    """
    Writes event data to a CSV file.

    Args:
        event_type (str): The type of event.
        data (list): The list of event dictionaries.
    """
    if not data:
        return  # Skip if no data to write

    # Define the output file path
    output_file = out_path(OUTPUT_CSV_FILES[event_type])

    # Define the CSV headers based on event type
    headers = []
    if event_type == 'autofocus':
        headers = ['Start Time', 'End Time', 'Final Focus Position', 'Status']
    elif event_type == 'autorun':
        headers = ['Start Time', 'End Time', 'Details']
    elif event_type == 'target_coordinates':
        headers = ['Timestamp', 'RA', 'DEC']
    elif event_type == 'tracking':
        headers = ['Timestamp', 'Event Type']
    elif event_type == 'guide':
        headers = ['Timestamp', 'Event Type', 'Details']
    elif event_type == 'exposure':
        headers = ['Timestamp', 'Exposure Time (s)', 'Image Number']
    elif event_type == 'plate_solve':
        headers = ['Timestamp', 'Status', 'RA', 'DEC', 'Angle', 'Star Number']
    elif event_type == 'meridian_flip':
        headers = ['Start Time', 'End Time', 'Details', 'Event']
    elif event_type == 'auto_center':
        headers = ['Start Time', 'End Time', 'Details', 'Auto-Center Number']
    elif event_type == 'mount_slew':
        headers = ['Timestamp', 'RA', 'DEC']
    elif event_type == 'wait':
        headers = ['Timestamp', 'Wait Message']
    elif event_type == 'logging':
        headers = ['Timestamp', 'Event Type']
    else:
        headers = ['Timestamp', 'Event Type', 'Details']

    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            # Use extrasaction to ignore any fields not in headers
            writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            for entry in data:
                # Remove empty keys to avoid writing unnecessary columns
                cleaned_entry = {k: v for k, v in entry.items() if v}
                writer.writerow(cleaned_entry)
        print(f"{event_type.capitalize()} events have been written to {output_file}")
    except Exception as e:
        print(f"An error occurred while writing {event_type} events to CSV: {e}")

def main():
    # Ensure the log directory exists
    if not os.path.isdir(RAW_DIR):
        print(f"Error: The log directory '{RAW_DIR}' does not exist.")
        return

    # Find all relevant log files
    log_files = find_log_files(RAW_DIR, AUTORUN_LOG_PREFIX)

    if not log_files:
        print(f"No log files found with prefix '{AUTORUN_LOG_PREFIX}' in directory '{RAW_DIR}'.")
        return

    # Parse each log file
    for log_file in log_files:
        print(f"Parsing log file: {log_file}")
        parse_log_file(log_file)

    # Write each event type to its respective CSV
    for event_type, data in EVENT_DATA.items():
        write_csv(event_type, data)

if __name__ == "__main__":
    main()
