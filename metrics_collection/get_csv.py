import os
import re
import csv
from pathlib import Path

def extract_tps_to_csvs_by_directory(root_directory, output_directory='tps_csvs'):
    """
    Recursively find all .out files, extract TPS values, 
    and save to CSVs named after their parent directory.
    Multiple .out files in same directory append to same CSV.
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)
    
    # Dictionary to track which CSVs we've created (to write header only once)
    csv_files_created = set()
    
    processed_files = 0
    total_tps_values = 0
    
    # Walk through directory recursively
    for root, dirs, files in os.walk(root_directory):
        for filename in files:
            if filename.endswith('.out'):
                filepath = os.path.join(root, filename)
                
                # Get parent directory name
                parent_dir = os.path.basename(os.path.dirname(filepath))
                if not parent_dir or parent_dir == '.':
                    parent_dir = 'root'
                
                # CSV filename based on parent directory
                csv_filename = f"{parent_dir}.csv"
                csv_filepath = os.path.join(output_directory, csv_filename)
                
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Find all TPS values using regex
                        tps_matches = re.findall(r'TPS=(\d+\.?\d*)', content)
                        
                        if tps_matches:
                            # Determine write mode and whether to write header
                            write_mode = 'a' if csv_filepath in csv_files_created else 'w'
                            write_header = csv_filepath not in csv_files_created
                            
                            # Write TPS values to CSV (append mode if already exists)
                            with open(csv_filepath, write_mode, newline='') as csvfile:
                                writer = csv.writer(csvfile)
                                if write_header:
                                    writer.writerow(['tps'])  # Header
                                for tps_value in tps_matches:
                                    writer.writerow([float(tps_value)])
                            
                            csv_files_created.add(csv_filepath)
                            processed_files += 1
                            total_tps_values += len(tps_matches)
                            
                            mode_str = "appended to" if write_mode == 'a' else "created"
                            print(f"✓ {filename} → {csv_filename} ({len(tps_matches)} values {mode_str})")
                        
                except Exception as e:
                    print(f"✗ Error reading {filepath}: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUCCESS: Processed {processed_files} .out files")
    print(f"Created {len(csv_files_created)} unique CSV files")
    print(f"Total TPS values extracted: {total_tps_values}")
    print(f"Output directory: {output_directory}/")
    print(f"{'='*60}")
    
    return processed_files, len(csv_files_created), total_tps_values

# Usage
root_dir = '.'  # Current directory, change to your target directory
output_dir = 'tps_csvs'  # Directory where CSVs will be saved

processed, unique_csvs, total = extract_tps_to_csvs_by_directory(root_dir, output_dir)
