import json
import subprocess
import os

def setup_client_service(data):
    """Setup containerized client service on SLURM"""
    
    # Extract parameters from recipe
    job = data.get('job', {})
    infrastructure = job.get('infrastructure', {})
    service = job.get('service', {})
    
    # Get absolute path of backend directory for bind mount
    backend_dir = os.path.abspath(os.path.dirname(__file__) + '/..')
    
    # SLURM parameters for client
    partition = infrastructure.get('client_partition', 'cpu')  # CPU nodes for clients
    time = infrastructure.get('client_time', '00:30:00')
    account = infrastructure.get('account', 'p200981')
    nodes = 1  # Single node for now
    mem_gb = infrastructure.get('client_mem_gb', 8)  # Less memory for client
    
    # Get n_clients from recipe (for ThreadPool sizing)
    n_clients = service.get('n_clients', 1)
    n_requests_per_client = service.get('n_requests_per_client', 5)
    
    # We need 1 CPU per client (each client makes requests sequentially)
    cpus_needed = n_clients
    
    job_script = f"""#!/bin/bash -l
#SBATCH --job-name=ollama_client
#SBATCH --partition={partition}
#SBATCH --qos=default
#SBATCH --time={time}
#SBATCH --account={account}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task={cpus_needed}
#SBATCH --mem={mem_gb}G
#SBATCH --output=output/logs/client_service_%j.out
#SBATCH --error=output/logs/client_service_%j.err

module load env/release/2024.1
module load Apptainer

# Get job info
NODE_IP=$(hostname -i)
NODE_NAME=$(hostname)
JOB_ID=$SLURM_JOB_ID

echo "Client service starting on $NODE_NAME ($NODE_IP) - Job $JOB_ID"

# Save IP immediately
echo "$NODE_IP" > output/client_ip_${{JOB_ID}}.txt
echo "Saved client IP: $NODE_IP"

# ========================================
# REGISTER IN PROMETHEUS
# ========================================
echo "Registering client node in Prometheus..."

cat > output/prometheus_assets/node_targets_client_${{JOB_ID}}.json <<EOF
[
  {{
    "targets": ["${{NODE_IP}}:9100"],
    "labels": {{
      "job": "node_exporter",
      "node": "${{NODE_NAME}}",
      "node_type": "client",
      "slurm_job_id": "${{JOB_ID}}"
    }}
  }}
]
EOF

echo "✓ Registered in Prometheus: output/prometheus_assets/node_targets_client_${{JOB_ID}}.json"

# ========================================
# START NODE EXPORTER
# ========================================
echo "Starting Node Exporter for Prometheus..."

if [ ! -f "output/containers/node_exporter.sif" ]; then
    echo "Pulling node_exporter image..."
    apptainer pull output/containers/node_exporter.sif docker://prom/node-exporter:latest
fi

apptainer exec output/containers/node_exporter.sif /bin/node_exporter &
NODE_EXPORTER_PID=$!

echo "✓ Node Exporter started (PID: $NODE_EXPORTER_PID) on port 9100"

# ========================================
# BUILD AND START CLIENT SERVICE
# ========================================
if [ ! -f "output/containers/client_service.sif" ]; then
    echo "Building client service container..."
    apptainer build output/containers/client_service.sif client/client_service.def
fi

echo ""
echo "========================================="
echo "   CLIENT SERVICE READY (Job $JOB_ID)"
echo "========================================="
echo "Node:          ${{NODE_NAME}}"
echo "IP:            ${{NODE_IP}}"
echo "Client API:    http://${{NODE_IP}}:5000"
echo "Node Exporter: http://${{NODE_IP}}:9100"
echo "CPUs allocated: {cpus_needed}"
echo "========================================="
echo ""

export OMP_NUM_THREADS={cpus_needed}
export SLURM_CPUS_ON_NODE={cpus_needed}

apptainer exec --bind {backend_dir}/output:/app/output:ro output/containers/client_service.sif python /app/clientService.py
"""

    
    # Debug logging
    print("Setting up client service...")
    print(f"Using infrastructure: partition={partition}, account={account}, mem={mem_gb}GB")
    print(f"Resource allocation: 1 task, {cpus_needed} CPUs ({n_clients} clients, each doing {n_requests_per_client} sequential requests)")
    
    # Ensure output directories exist
    os.makedirs("output/scripts", exist_ok=True)
    os.makedirs("output/logs", exist_ok=True)
    
    # Write job script
    with open("output/scripts/client_service.sh", "w") as f:
        f.write(job_script)
    
    # Submit to SLURM
    result = subprocess.run(
        ["sbatch", "output/scripts/client_service.sh"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        universal_newlines=True
    )
    
    if result.returncode == 0:
        print(f"Client service job submitted: {result.stdout.strip()}")
    else:
        print(f"Error submitting client service job: {result.stderr}")
    
    return result