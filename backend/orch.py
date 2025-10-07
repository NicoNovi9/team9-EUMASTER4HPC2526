import sys
import json


import subprocess
import clientsHandler

""" This is the main script, server side entry point.
    It is responsible for orchestrating the deployment of the services (Ollama and Qdrant),
    client generation and launch the monitoring script (Prometheus) on Meluxina.
"""

if __name__ == "__main__":
    print("hello from the orchestrator python")
    json_str = sys.argv[1]
    data = json.loads(json_str)

    job_script = f"""#!/bin/bash
#SBATCH --job-name=ollama_service
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4G
#SBATCH --time=00:40:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --output=ollama_service.out
#SBATCH --error=ollama_service.err

module load Apptainer

NODE_IP=$(hostname -i)
echo $NODE_IP > /home/users/{data['username']}/ollama_ip.txt

# Pull Ollama image if not already present
if [ ! -f ollama.sif ]; then
    apptainer pull ollama.sif docker://ollama/ollama:latest
fi

# Start Ollama service on all interfaces
apptainer exec --nv --env OLLAMA_HOST=0.0.0.0:11434 ollama.sif ollama serve &

# Capture PID
OLLAMA_PID=$!

# Wait for service to start
sleep 10

# Preload mistral model
apptainer exec --nv --env OLLAMA_HOST=0.0.0.0:11434 ollama.sif ollama pull mistral

# Keep Ollama alive
wait $OLLAMA_PID
"""
    
    print("received JSON:", data) #print statements will be shown in .out file
    with open("ollama_service.sh", "w") as f:
        f.write(job_script)

    # Submit to SLURM
    result = subprocess.run(["sbatch", "ollama_service.sh"], capture_output=True, text=True)
    print("SLURM submission output:", result.stdout)
    print("SLURM submission error:", result.stderr)
    clientsHandler.generate_clients(data['client'], data['username'])




