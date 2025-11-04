import json
import subprocess
import os

def setup_client_service(data):
    """Setup containerized client service on SLURM"""
    
    # Extract parameters from recipe
    job = data.get('job', {})
    infrastructure = job.get('infrastructure', {})
    
    # SLURM parameters for client
    partition = infrastructure.get('client_partition', 'cpu')  # CPU nodes for clients
    time = infrastructure.get('client_time', '00:30:00')
    account = infrastructure.get('account', 'p200981')
    nodes = 1  # Single node for now
    mem_gb = infrastructure.get('client_mem_gb', 8)  # Less memory for client
    
    job_script = f"""#!/bin/bash -l
#SBATCH --job-name=ollama_client
#SBATCH --partition={partition}
#SBATCH --qos=default
#SBATCH --time={time}
#SBATCH --account={account}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node=1
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

#============================================
# CLEANUP FUNCTION
#============================================

cleanup() {{
  echo "Client job $JOB_ID terminating, cleaning up..."
  rm -f output/prometheus_assets/node_targets_client_${{JOB_ID}}.json
  echo "✓ Client cleanup completed"
}}

trap cleanup EXIT
#============================================
# START NODE EXPORTER FOR CLIENT NODE
#============================================

echo "Setting up Node Exporter for client node metrics..."
if [ ! -f output/containers/node_exporter.sif ]; then
    echo "Pulling Node Exporter container..."
    apptainer pull output/containers/node_exporter.sif docker://prom/node-exporter:latest
fi

apptainer run \\
  --bind /proc:/host/proc:ro \\
  --bind /sys:/host/sys:ro \\
  output/containers/node_exporter.sif \\
  --path.procfs=/host/proc \\
  --path.sysfs=/host/sys \\
  --collector.cgroups \\
  --collector.processes \\
  --web.listen-address=":9101" &    # ← CAMBIATO DA 9100 A 9101

NODE_EXPORTER_PID=$!
echo "Node Exporter started with PID: $NODE_EXPORTER_PID"

# Register client node with Prometheus (porta 9101!)
cat > output/prometheus_assets/node_targets_client_${{JOB_ID}}.json <<EOF
[
  {{
    "targets": ["${{NODE_IP}}:9101"],    # <- CHANGED FROM 9100 TO 9101, SO TO AVOID POSSIBLE CONFLICTS IN CASE OF OLLAMA AND CLIENTS ON SAME NODE
    "labels": {{
      "job": "node_exporter",
      "node": "${{NODE_NAME}}",
      "node_type": "client",
      "slurm_job_id": "${{JOB_ID}}"
    }}
  }}
]
EOF
echo "✓ Node Exporter registered: node_targets_client_${{JOB_ID}}.json"

# Register client node with Prometheus (unique file)
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
echo "✓ Node Exporter registered: node_targets_client_${{JOB_ID}}.json"

#============================================
# BUILD AND START CLIENT SERVICE
#============================================

# Build the container if it doesn't exist
if [ ! -f "client_service.sif" ]; then
    echo "Building client service container..."
    apptainer build client_service.sif client/client_service.def
fi

# Run the client service container
echo "Starting client service container on $NODE_IP:5000"
echo "$NODE_IP" > output/client_ip_${{JOB_ID}}.txt

#============================================
# SUMMARY
#============================================

echo ""
echo "========================================="
echo "   CLIENT SERVICE READY (Job $JOB_ID)"
echo "========================================="
echo "Node:          ${{NODE_NAME}}"
echo "IP:            ${{NODE_IP}}"
echo ""
echo "Services:"
echo "  Client API:    http://${{NODE_IP}}:5000"
echo "  Node Exporter: http://${{NODE_IP}}:9101"
echo ""
echo "Target file:"
echo "  - node_targets_client_${{JOB_ID}}.json"
echo "========================================="
echo ""

# Run Flask in foreground (will keep job alive)
# Use absolute path for bind mount
apptainer exec --bind $PWD/output:/app/output:ro client_service.sif python /app/clientService.py
"""
    
    # Debug logging
    print("Setting up client service...")
    print(f"Using infrastructure: partition={partition}, account={account}, mem={mem_gb}GB")
    
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