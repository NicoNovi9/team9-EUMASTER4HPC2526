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
    
    job_script = f"""#!/bin/bash -l
#SBATCH --job-name=ollama_service
#SBATCH --partition={partition}
#SBATCH --qos=default
#SBATCH --time={time}
#SBATCH --account={account}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node=1
#SBATCH --mem={mem_gb}G
#SBATCH --output=output/logs/ollama_service.out
#SBATCH --error=output/logs/ollama_service.err

module load env/release/2024.1
module load Apptainer

NODE_IP=$(hostname -i)
NODE_NAME=$(hostname)
echo $NODE_IP > output/ollama_ip.txt

#------------
# Register Ollama in Prometheus
cat > output/prometheus_assets/ollama_targets.json <<EOF
[
  {{
    "targets": ["${{NODE_IP}}:11434"],
    "labels": {{
      "job": "ollama_service",
      "node": "${{NODE_NAME}}",
      "service": "ollama"
    }}
  }}
]
EOF
echo "✓ Registered Ollama at ${{NODE_IP}}:11434"

#------------
# START NODE EXPORTER FOR SYSTEM METRICS
echo "Setting up Node Exporter for system metrics..."
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
    --collector.cgroups \
      --collector.processes \
  --web.listen-address=":9100" &
NODE_EXPORTER_PID=$!
echo "Node Exporter started with PID: $NODE_EXPORTER_PID"

cat > output/prometheus_assets/node_targets.json <<EOF
[
  {{
    "targets": ["${{NODE_IP}}:9100"],
    "labels": {{
      "job": "node_exporter",
      "node": "${{NODE_NAME}}"
    }}
  }}
]
EOF
echo "✓ Node Exporter started on ${{NODE_IP}}:9100"


# Pull Ollama container if missing
if [ ! -f output/containers/ollama_latest.sif ]; then
    mkdir -p output/containers
    apptainer pull output/containers/ollama_latest.sif docker://ollama/ollama:latest
fi

# Avvia il servizio Ollama in background
apptainer exec --nv output/containers/ollama_latest.sif ollama serve &
OLLAMA_PID=$!

# Aspetta che il servizio si avvii completamente
sleep 15

# Scarica il modello specificato nel JSON
echo "Downloading model: {model}"
apptainer exec --nv output/containers/ollama_latest.sif ollama pull {model}

echo "Ollama service started with model {model} on $NODE_IP:11434"

# Mantieni il servizio attivo
wait $OLLAMA_PID
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
