import json
import subprocess
import os


def setup_ollama(data):
    # Estraggo parametri dalla ricetta
    job = data.get('job', {})
    infrastructure = job.get('infrastructure', {})
    service = job.get('service', {})
    
    # Parametri SLURM dalla ricetta
    partition = infrastructure.get('partition', 'gpu')
    time = infrastructure.get('time', '00:05:00')
    account = infrastructure.get('account', 'p200981')
    nodes = infrastructure.get('nodes', 1)
    mem_gb = infrastructure.get('mem_gb', 64)
    
    # Parametri del servizio
    model = service.get('model', 'llama2')
    n_clients = service.get('n_clients', 1)  # For OLLAMA_NUM_PARALLEL
    
    job_script = f"""#!/bin/bash -l
#SBATCH --time=01:00:00
#SBATCH --job-name=ollama_service
#SBATCH --partition={partition}
#SBATCH --qos=default
#SBATCH --time={time}
#SBATCH --account={account}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node=1
#SBATCH --mem={mem_gb}G
#SBATCH --output=output/logs/ollama_service_%j.out
#SBATCH --error=output/logs/ollama_service_%j.err

module load env/release/2024.1
module load Apptainer

NODE_IP=$(hostname -i)
NODE_NAME=$(hostname)
JOB_ID=$SLURM_JOB_ID

echo "Job ID: $JOB_ID running on $NODE_NAME ($NODE_IP)"
echo $NODE_IP > output/ollama_ip_${{JOB_ID}}.txt

# Create persistent directory for Ollama models
mkdir -p output/ollama_models

#============================================
# CLEANUP FUNCTION (removes targets when job ends)
#============================================

cleanup() {{
  echo "Job $JOB_ID terminating, cleaning up target files..."
  rm -f output/prometheus_assets/node_targets_${{JOB_ID}}.json
  rm -f output/prometheus_assets/cadvisor_targets_${{JOB_ID}}.json
  rm -f output/prometheus_assets/gpu_targets_${{JOB_ID}}.json
  echo "✓ Cleanup completed"
}}

trap cleanup EXIT

#============================================
# START NODE EXPORTER FOR HARDWARE METRICS
#============================================

echo "Setting up Node Exporter for hardware metrics..."
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
  --web.listen-address=":9100" &

NODE_EXPORTER_PID=$!
echo "Node Exporter started with PID: $NODE_EXPORTER_PID"

# Register Node Exporter with Prometheus (unique file per job)
cat > output/prometheus_assets/node_targets_${{JOB_ID}}.json <<EOF
[
  {{
    "targets": ["${{NODE_IP}}:9100"],
    "labels": {{
      "job": "node_exporter",
      "node": "${{NODE_NAME}}",
      "node_type": "service",
      "slurm_job_id": "${{JOB_ID}}"
    }}
  }}
]
EOF
echo "✓ Node Exporter registered: node_targets_${{JOB_ID}}.json"

#============================================
# START DCGM EXPORTER FOR GPU METRICS
#============================================

echo "Setting up DCGM Exporter for GPU metrics..."
if [ ! -f output/containers/dcgm-exporter.sif ]; then
    echo "Pulling DCGM Exporter container..."
    apptainer pull output/containers/dcgm-exporter.sif \\
      docker://nvcr.io/nvidia/k8s/dcgm-exporter:3.3.5-3.4.0-ubuntu22.04
fi

apptainer exec --nv output/containers/dcgm-exporter.sif dcgm-exporter \\
  > output/logs/dcgm_exporter_${{JOB_ID}}.out 2> output/logs/dcgm_exporter_${{JOB_ID}}.err &

DCGM_PID=$!
sleep 5
echo "DCGM Exporter started with PID: $DCGM_PID"

# Register DCGM with Prometheus (unique file per job)
cat > output/prometheus_assets/gpu_targets_${{JOB_ID}}.json <<EOF
[
  {{
    "targets": ["${{NODE_IP}}:9400"],
    "labels": {{
      "job": "ollama_gpu",
      "node": "${{NODE_NAME}}",
      "gpu_type": "nvidia",
      "model": "{model}",
      "slurm_job_id": "${{JOB_ID}}"
    }}
  }}
]
EOF
echo "✓ DCGM Exporter registered: gpu_targets_${{JOB_ID}}.json"

#============================================
# START OLLAMA SERVICE
#============================================

echo "Setting up Ollama service..."
if [ ! -f output/containers/ollama_latest.sif ]; then
    mkdir -p output/containers
    apptainer pull output/containers/ollama_latest.sif docker://ollama/ollama:latest
fi

# Start Ollama with persistent model storage
echo "Starting Ollama service..."
apptainer exec --nv \\
  --env OLLAMA_NUM_PARALLEL={n_clients} \\
  --env OLLAMA_MAX_LOADED_MODELS={n_clients} \\
  --bind output/ollama_models:/root/.ollama \\
  output/containers/ollama_latest.sif \\
  ollama serve &

OLLAMA_PID=$!
echo "Ollama started with PID: $OLLAMA_PID"
echo "Parallel requests enabled: {n_clients}"

# Wait for Ollama to be ready
sleep 15

#============================================
# DOWNLOAD MODEL (IF NOT ALREADY PRESENT)
#============================================

echo "Checking if model {model} is available..."
MODEL_CHECK=$(apptainer exec --nv \\
  --bind output/ollama_models:/root/.ollama \\
  output/containers/ollama_latest.sif \\
  ollama list | grep -w "{model}" || echo "")

if [ -z "$MODEL_CHECK" ]; then
    echo "Model {model} not found. Downloading..."
    apptainer exec --nv \\
      --bind output/ollama_models:/root/.ollama \\
      output/containers/ollama_latest.sif \\
      ollama pull {model}
    echo "✓ Model {model} downloaded successfully"
else
    echo "✓ Model {model} already exists, skipping download"
fi

#============================================
# SUMMARY
#============================================

echo ""
echo "========================================="
echo "   OLLAMA SERVICE READY (Job $JOB_ID)"
echo "========================================="
echo "Node:          ${{NODE_NAME}}"
echo "IP:            ${{NODE_IP}}"
echo ""
echo "Services:"
echo "  Ollama:        http://${{NODE_IP}}:11434"
echo "  Node Exporter: http://${{NODE_IP}}:9100"
echo "  DCGM Exporter: http://${{NODE_IP}}:9400"
echo ""
echo "Model:         {model}"
echo "Parallel reqs: {n_clients}"
echo "Model Storage: $(pwd)/output/ollama_models"
echo ""
echo "Target files:"
echo "  - node_targets_${{JOB_ID}}.json"
echo "  - gpu_targets_${{JOB_ID}}.json"
echo "========================================="
echo ""

# Keep all services alive
wait $OLLAMA_PID $NODE_EXPORTER_PID $DCGM_PID
"""

    # Debug logging
    job_name = job.get('name', 'ollama_service')
    print("received JSON:", data)
    print(f"Using job: name={job_name}")
    print(f"Using infrastructure: partition={partition}, account={account}, nodes={nodes}, mem={mem_gb}GB")
    print(f"Using service: model={model}")
    
    # Ensure output directories exist
    os.makedirs("output/scripts", exist_ok=True)
    os.makedirs("output/logs", exist_ok=True)
    os.makedirs("output/containers", exist_ok=True)
    os.makedirs("output/prometheus_assets", exist_ok=True)
    os.makedirs("output/ollama_models", exist_ok=True)
  
    with open("output/scripts/ollama_service.sh", "w") as f:
        f.write(job_script)

    # Submit to SLURM
    result = subprocess.run(
        ["sbatch", "output/scripts/ollama_service.sh"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        universal_newlines=True
    )
    
    print(f"SLURM submission output: {result.stdout}")
    if result.stderr:
        print(f"SLURM submission errors: {result.stderr}")
    
    return result
