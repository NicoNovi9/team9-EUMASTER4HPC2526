import sys
import site
import subprocess
import os
import json
import time
import glob
import requests
import ollamaService
import client.clientServiceHandler as clientServiceHandler
import client.testClientService as testClientService

print("All packages imported successfully.")

""" 
Ollama Orchestrator - Deploy server and client services. Launches the monitoring script (Prometheus)
"""


def prepare_monitoring():
    username = os.path.basename(os.path.normpath(os.getcwd()))
    
    # === PUSHGATEWAY ===
    pushgateway_running = subprocess.run(
        ['squeue', '-u', username, '-n', 'pushgateway_service', '-h'],
        capture_output=True, text=True).stdout.strip()
    pushgateway_job_id = None
    
    if pushgateway_running:
        print("Pushgateway job already running")
        pushgateway_job_id = pushgateway_running.split()[0]
    else:
        push_result = subprocess.run(['sbatch', 'pushgateway_service.sh'], capture_output=True, text=True)
        output = push_result.stdout.strip()
        print(output)
        if "Submitted batch job" in output:
            pushgateway_job_id = output.split()[-1]
        else:
            print("Failed to submit pushgateway job")
            return

        # Wait for Pushgateway to be RUNNING
        print("Waiting for Pushgateway to enter RUNNING state...")
        while True:
            squeue_output = subprocess.run(
                ['squeue', '-j', pushgateway_job_id, '-o', '%T', '-h'],
                capture_output=True, text=True).stdout.strip()
            if squeue_output == "RUNNING":
                print("Pushgateway is RUNNING!")
                break
            else:
                print(f"  Current state: {squeue_output}, waiting...")
                time.sleep(5)

    # === PROMETHEUS/Grafana ===
    prometheus_running = subprocess.run(
        ['squeue', '-u', username, '-n', 'monitoring_stack', '-h'],
        capture_output=True, text=True).stdout.strip()
    prometheus_job_id = None

    if prometheus_running:
        print("Prometheus job already running")
        prometheus_job_id = prometheus_running.split()[0]
    else:
        prom_submit = subprocess.run(['sbatch', 'monitoring_stack.sh'],
                                    capture_output=True, text=True)
        output = prom_submit.stdout.strip()
        print(output)
        if "Submitted batch job" in output:
            prometheus_job_id = output.split()[-1]
        else:
            print("Failed to submit Prometheus job")
            return
        
        # Wait for Prometheus to be RUNNING before starting Grafana
        print("Waiting for Prometheus to enter RUNNING state...")
        while True:
            squeue_output = subprocess.run(
                ['squeue', '-j', prometheus_job_id, '-o', '%T', '-h'],
                capture_output=True, text=True).stdout.strip()
            if squeue_output == "RUNNING":
                print("✓ Prometheus is RUNNING!")
                break
            else:
                print(f"  Current state: {squeue_output}, waiting...")
                time.sleep(5)
        
        # Give Prometheus extra time to fully initialize
        print("Waiting 10 seconds for Prometheus to fully initialize...")
        time.sleep(10)

if __name__ == "__main__":
    # Accept: orch.py <json_file_path> [--no-monitoring]
    if len(sys.argv) < 2:
        print("Usage: python3 orch.py <json_file_path> [--no-monitoring]")
        sys.exit(1)

    # Simple flag parsing: look for --no-monitoring anywhere
    no_monitoring = '--no-monitoring' in sys.argv[1:]

    # First non-flag argument is the JSON file
    json_file_path = None
    for a in sys.argv[1:]:
        if not a.startswith('-'):
            json_file_path = a
            break

    if json_file_path is None:
        print("Error: recipe json file path not provided")
        sys.exit(1)
    
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
    
    if not no_monitoring:
        prepare_monitoring()
    else:
        print("Skipping monitoring setup (--no-monitoring)")

    # Deploy Ollama server
    print("Deploying Ollama server...")
    ollamaService.setup_ollama(data)

    # Wait for Ollama to be ready with model loaded
    print("\nWaiting for Ollama server to be ready with model loaded...")
    max_wait = 3600  
    elapsed = 0
    
    while elapsed < max_wait:
        ollama_files = glob.glob('output/ollama_ip_*.txt')
        
        if ollama_files:
            with open(sorted(ollama_files, key=os.path.getmtime)[-1], 'r') as f:
                ollama_ip = f.read().strip()
            
            try:
                # Check if Ollama has models loaded
                response = requests.get(f"http://{ollama_ip}:11434/api/tags", timeout=5)
                
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    if models:
                        print(f"  Ollama ready at {ollama_ip}:11434")
                        print(f"  Loaded models: {[m.get('name') for m in models]}")
                        break
                    else:
                        print(f"  Waiting for models to load... ({elapsed}s)")
                else:
                    print(f"  Ollama responding but not ready... ({elapsed}s)")
            except:
                print(f"  Waiting for Ollama... ({elapsed}s)")
        else:
            print(f"  Waiting for ollama_ip file... ({elapsed}s)")
        
        time.sleep(10)
        elapsed += 10
    
    if elapsed >= max_wait:
        print("ERROR: Ollama server timeout - no models loaded")
        sys.exit(1)

    print("Deploying client service...")
    clientServiceHandler.setup_client_service(data)

    # Wait for client service to be ready
    print("\nWaiting for client service to be ready...")
    max_wait = 3600 
    elapsed = 0
    
    while elapsed < max_wait:
        client_files = glob.glob('output/client_ip_*.txt')
        
        if client_files:
            with open(sorted(client_files, key=os.path.getmtime)[-1], 'r') as f:
                client_ip = f.read().strip()
            
            try:
                # Check /health endpoint
                health_resp = requests.get(f"http://{client_ip}:5000/health", timeout=3)
                
                if health_resp.status_code == 200:
                    print(f"✓ Client ready at {client_ip}:5000")
                    # Give extra time for Flask to fully initialize
                    print("Waiting 10 more seconds for Flask to stabilize...")
                    time.sleep(10)
                    break
            except Exception as e:
                print(f"  Waiting... ({elapsed}s) - {e}")
        else:
            print(f"  Waiting for client_ip file... ({elapsed}s)")
        
        time.sleep(5)
        elapsed += 5
    
    if elapsed >= max_wait:
        print("ERROR: Client service timeout")
        sys.exit(1)

    print("\nDeployment complete. Starting test queries...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "idna", "charset_normalizer"])
    
    # Extract parameters from recipe
    model_name = data.get('job', {}).get('service', {}).get('model', 'llama2')
    n_clients = data.get('job', {}).get('service', {}).get('n_clients', 1)
    n_requests_per_client = data.get('job', {}).get('service', {}).get('n_requests_per_client', 5)
    
    print(f"Model: {model_name}")
    print(f"Clients: {n_clients}")
    print(f"Requests per client: {n_requests_per_client}")

    # Run benchmark with correct parameters
    testClientService.run_benchmark(n_clients, n_requests_per_client, model_name)
    
    # Cancel all jobs for current user
    # print("\n" + "="*60)
    # print("Benchmark complete. Cleaning up SLURM jobs...")
    # print("="*60)
    #subprocess.run(['scancel', '--me'], check=False)
    #print("All SLURM jobs cancelled.")
