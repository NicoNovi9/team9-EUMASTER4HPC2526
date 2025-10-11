#!/usr/bin/env python3

import sys
import json
import clientServiceHandler

"""
Launch the client service for benchmarking Ollama.
Usage: python3 launchClient.py <json_file_path>
"""

if __name__ == "__main__":
    print("Launching Ollama Client Service...")
    
    if len(sys.argv) < 2:
        print("Usage: python3 launchClient.py <json_file_path>")
        sys.exit(1)
    
    json_file_path = sys.argv[1]
    
    try:
        # Read JSON file
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        print(f"Loaded recipe from file: {json_file_path}")
    except FileNotFoundError:
        print(f"Error: File '{json_file_path}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file '{json_file_path}': {e}")
        sys.exit(1)
    
    # Launch client service
    result = clientServiceHandler.setup_client_service(data)
    
    if result.returncode == 0:
        print("\n✓ Client service job submitted successfully!")
        print("Monitor with: squeue -u $USER")
        print("Test when ready with: python3 testClientService.py")
    else:
        print(f"\n✗ Failed to submit client service job")
        print(f"Error: {result.stderr}")
        sys.exit(1)