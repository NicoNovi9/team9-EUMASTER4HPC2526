import sys
import site
import subprocess
import os
import json
import time
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
    
    # prepare_monitoring()

    # Deploy Ollama server
    print("Deploying Ollama server...")
    ollamaService.setup_ollama(data)

    # Wait and deploy client
    print("Waiting 15 seconds...")
    time.sleep(15)

    print("Deploying client service...")
    clientServiceHandler.setup_client_service(data)
    #todo substitute with the correct json parsing

    # querying ollama by testClientService
    print("Deployment complete. Test with: python3 client/testClientService.py")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "idna", "charset_normalizer"])
    for i in range(30):
        testClientService.query()
