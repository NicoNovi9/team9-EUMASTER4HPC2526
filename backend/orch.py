import sys
import json
import time
import subprocess
import ollamaService
from client import clientServiceHandler
import os

""" 
Ollama Orchestrator - Deploy server and client services.
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 orch.py <json_file_path>")
        sys.exit(1)
    
    json_file_path = sys.argv[1]
    
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        print(f"Loaded recipe: {json_file_path}")
    except FileNotFoundError:
        print(f"Error: File '{json_file_path}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)
    
    # Deploy Ollama server
    print("Deploying Ollama server...")
    ollamaService.setup_ollama(data)
    
    print("Deploying client service...")
    clientServiceHandler.setup_client_service(data)
    
    print("Deployment complete. Test with: python3 client/testClientService.py")