import sys
import json


import subprocess
import clientsHandler
import servicesHandler

""" This is the main script, server side entry point.
    It is responsible for orchestrating the deployment of the services (Ollama and Qdrant),
    client generation and launch the monitoring script (Prometheus) on Meluxina.
"""

if __name__ == "__main__":
    print("starting the orchestrator python")
    
    if len(sys.argv) < 2:
        print("Usage: python3 orch.py <json_file_path>")
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
    
    servicesHandler.handle_service_request(data);
    clientsHandler.generate_clients(data['client'], data['username'])




