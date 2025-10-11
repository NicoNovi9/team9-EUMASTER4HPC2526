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
    
    job_script = job_script = f"""#!/bin/bash -l
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

# Scarica il container Ollama se non esiste già
if [ ! -f "ollama_latest.sif" ]; then
    apptainer pull docker://ollama/ollama
fi

# Avvia il servizio Ollama in background
apptainer exec --nv ollama_latest.sif ollama serve &
OLLAMA_PID=$!

# Aspetta che il servizio si avvii completamente
sleep 15

# Scarica il modello specificato nel JSON
echo "Downloading model: {model}"
apptainer exec --nv ollama_latest.sif ollama pull {model}

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
    result = subprocess.run(["sbatch", "output/scripts/ollama_service.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)