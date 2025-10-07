import json
import subprocess

def setup_ollama(data):
    # Estraggo parametri dalla ricetta
    infrastructure = data.get('infrastructure', {})
    service = data.get('service', {})
    
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

module add Apptainer

NODE_IP=$(hostname -i)
echo $NODE_IP > $HOME/ollama_ip.txt

# Pull Ollama image if not already present
if [ ! -f output/containers/ollama_latest.sif ]; then
    apptainer pull output/containers/ollama_latest.sif docker://ollama/ollama
fi

# Start Ollama service on all interfaces
export OLLAMA_HOST=0.0.0.0:11434
apptainer exec --nv output/containers/ollama_latest.sif ollama serve

# Keep service alive
wait
"""
    
    # Debug logging
    print("received JSON:", data)
    print(f"Using infrastructure: partition={partition}, account={account}, nodes={nodes}, mem={mem_gb}GB")
    print(f"Using service: model={model}")
    with open("output/scripts/ollama_service.sh", "w") as f:
        f.write(job_script)

    # Submit to SLURM
    result = subprocess.run(["sbatch", "output/scripts/ollama_service.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)