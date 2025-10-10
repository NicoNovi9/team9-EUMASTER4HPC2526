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
echo $NODE_IP > output/ollama_ip.txt

# Pull container if missing
if [ ! -f output/containers/ollama_latest.sif ]; then
    mkdir -p output/containers
    apptainer pull output/containers/ollama_latest.sif docker://ollama/ollama:latest
fi

# Setup model cache in backend directory
export OLLAMA_MODELS="$(pwd)/output/ollama_models"
mkdir -p "$OLLAMA_MODELS"

# Start Ollama with mounted CA certificates to fix TLS issues
apptainer exec --nv \\
    --env OLLAMA_MODELS="$OLLAMA_MODELS" \\
    --env OLLAMA_HOST=0.0.0.0:11434 \\
    --bind "$OLLAMA_MODELS:/root/.ollama/models:rw" \\
    --bind "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem:/usr/local/share/ca-certificates/host-ca-bundle.crt:ro" \\
    output/containers/ollama_latest.sif \\
    bash -c "
        echo 'Starting Ollama server with mounted CA certificates...'
        
        # Copy host CA bundle to standard location and update certificates
        cp /usr/local/share/ca-certificates/host-ca-bundle.crt /usr/local/share/ca-certificates/ || echo 'CA copy failed'
        update-ca-certificates || echo 'CA update failed, continuing...'
        
        # Alternative: Set SSL_CERT_FILE environment variable
        export SSL_CERT_FILE=/usr/local/share/ca-certificates/host-ca-bundle.crt
        
        # Start server
        ollama serve &
        OLLAMA_PID=\\$!
        
        # Wait for server to start
        sleep 10
        
        # Now try to pull model with proper certificates
        if [ -n '{model}' ]; then
            echo 'Attempting to pull model {model} with mounted certificates...'
            if ollama pull '{model}'; then
                echo '✓ Model {model} pulled successfully!'
            else
                echo '✗ Model pull still failed - may need additional certificate configuration'
            fi
        fi
        
        echo 'Ollama server is ready at http://$(hostname -i):11434'
        echo 'Available models:'
        ollama list || echo 'Could not list models'
        
        # Keep server alive
        wait \\$OLLAMA_PID
    "
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
    result = subprocess.run(["sbatch", "output/scripts/ollama_service.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)