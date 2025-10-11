#!/usr/bin/env python3

"""
Simple workflow manager for Ollama benchmarking on SLURM.

This script provides commands to:
1. Deploy Ollama server
2. Deploy client service  
3. Test the setup
"""

import sys
import subprocess
import os

def print_usage():
    print("""
Ollama Benchmark Workflow Manager

Usage:
  python3 workflow.py server <recipe.json>    # Deploy Ollama server
  python3 workflow.py client <recipe.json>    # Deploy client service
  python3 workflow.py test                    # Test client service
  python3 workflow.py status                  # Check job status
  python3 workflow.py cleanup                 # Cancel all jobs

Examples:
  python3 workflow.py server recipe.json     # Start server
  python3 workflow.py client recipe.json     # Start client
  python3 workflow.py test                    # Run tests
""")

def run_command(cmd, description):
    print(f"\n{description}...")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0

def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "server":
        if len(sys.argv) < 3:
            print("Error: Recipe file required for server command")
            sys.exit(1)
        recipe_file = sys.argv[2]
        success = run_command(f"python3 orch.py {recipe_file}", "Deploying Ollama server")
        
    elif command == "client":
        if len(sys.argv) < 3:
            print("Error: Recipe file required for client command")
            sys.exit(1)
        recipe_file = sys.argv[2]
        success = run_command(f"python3 client/launchClient.py {recipe_file}", "Deploying client service")
        
    elif command == "test":
        success = run_command("python3 client/testClientService.py", "Testing client service")
        
    elif command == "status":
        success = run_command("squeue -u $USER", "Checking job status")
        
    elif command == "cleanup":
        success = run_command("scancel -u $USER", "Cancelling all jobs")
        
    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)
    
    if success:
        print("✓ Command completed successfully")
    else:
        print("✗ Command failed")
        sys.exit(1)

if __name__ == "__main__":
    main()