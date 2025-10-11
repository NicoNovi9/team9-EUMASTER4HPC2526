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
#SBATCH --output=output/logs/client_service.out
#SBATCH --error=output/logs/client_service.err

module load env/release/2024.1
module load Apptainer

# Get current node IP
NODE_IP=$(hostname -i)
echo "Client service starting on $NODE_IP"

# Build the container if it doesn't exist
if [ ! -f "client_service.sif" ]; then
    echo "Building client service container..."
    apptainer build client_service.sif client/client_service.def
fi

# Create data directory and copy ollama IP
mkdir -p data
cp output/ollama_ip.txt data/

# Run the client service container
echo "Starting client service container on $NODE_IP:5000"
apptainer exec --bind data:/app/data client_service.sif python /app/clientService.py &
CLIENT_PID=$!

echo "Client service started with PID $CLIENT_PID"
echo "Access at: http://$NODE_IP:5000"
echo "$NODE_IP" > output/client_ip.txt

# Keep the service running
wait $CLIENT_PID
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