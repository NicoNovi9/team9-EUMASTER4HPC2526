import sys
import json
import time
import subprocess
import servicesHandler
import os
from ollamaClient import OllamaClient

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
    
    #launching prometheus if not already running
    #the path of the cwd must end with your username (dynamically computed),username needed for squeue command
    # subprocess.run(['sbatch', 'prometheus_service.sh']) if not subprocess.run(
    # ['squeue', '-u', os.path.basename(os.path.normpath(os.getcwd())), '-n', 'prometheus_service', '-h'],
    # capture_output=True, text=True).stdout.strip() else print("Already running")

    servicesHandler.handle_service_request(data)
    
    # Test Ollama client after deployment
    print("Testing Ollama client...")
    time.sleep(200)  # Wait for service startup
    
    job = data.get('job', {})
    service = job.get('service', {})
    model = service.get('model', 'llama2')
    
    client = OllamaClient()
    if client.test_connection():
        print("Ollama connection successful")
        response = client.query("What is AI?")
        if response:
            response_text = response.get('response', '')
            print(f"Query successful: {len(response_text)} chars")
            if len(response_text) > 0:
                print(f"Response preview: {response_text[:100]}...")
            else:
                print(f"Full response: {response}")
        else:
            print("Query failed")
    else:
        print("Ollama connection failed")




