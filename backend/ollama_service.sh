#!/bin/bash
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
echo $NODE_IP > $HOME/ollama_ip.txt

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
