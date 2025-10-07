import json
import subprocess

def setup_ollama(data):
    job_script = f"""#!/bin/bash -l
#SBATCH --job-name=ollama_service
#SBATCH --partition=gpu
#SBATCH --qos=default
#SBATCH --time=00:40:00
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
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
"""
    
    print("received JSON:", data) #print statements will be shown in .out file
    with open("output/scripts/ollama_service.sh", "w") as f:
        f.write(job_script)

    # Submit to SLURM
    result = subprocess.run(["sbatch", "output/scripts/ollama_service.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    print("SLURM submission output:", result.stdout)
    print("SLURM submission error:", result.stderr)