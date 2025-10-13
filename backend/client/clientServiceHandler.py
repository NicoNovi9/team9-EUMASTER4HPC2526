"""
Simplified SLURM job submission handler for client service
"""
import subprocess
import os
from pathlib import Path

def create_slurm_script(partition='cpu', time='00:30:00', account='p200981', mem_gb=8):
    """Generate SLURM batch script content"""
    return f"""#!/bin/bash -l
#SBATCH --job-name=ollama_client
#SBATCH --partition={partition}
#SBATCH --qos=default
#SBATCH --time={time}
#SBATCH --account={account}
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --mem={mem_gb}G
#SBATCH --output=output/logs/client_service.out
#SBATCH --error=output/logs/client_service.err

module load env/release/2024.1
module load Apptainer

NODE_IP=$(hostname -i)
echo "Client service starting on $NODE_IP"

# Build container if needed
[ ! -f "client_service.sif" ] && apptainer build client_service.sif client/client_service.def

# Prepare data
mkdir -p data
cp output/ollama_ip.txt data/

# Start service
echo "Starting client service on $NODE_IP:5000"
apptainer exec --bind data:/app/data client_service.sif python /app/clientService.py &
echo "$NODE_IP" > output/client_ip.txt
wait
"""

def setup_client_service(data):
    """Setup and submit client service job to SLURM"""
    # Extract parameters
    job = data.get('job', {})
    infra = job.get('infrastructure', {})
    
    params = {
        'partition': infra.get('client_partition', 'cpu'),
        'time': infra.get('client_time', '00:30:00'),
        'account': infra.get('account', 'p200981'),
        'mem_gb': infra.get('client_mem_gb', 8)
    }
    
    # Create directories
    Path("output/scripts").mkdir(parents=True, exist_ok=True)
    Path("output/logs").mkdir(parents=True, exist_ok=True)
    
    # Write and submit script
    script_path = "output/scripts/client_service.sh"
    with open(script_path, "w") as f:
        f.write(create_slurm_script(**params))
    
    print(f"Submitting client service job: partition={params['partition']}, mem={params['mem_gb']}GB")
    result = subprocess.run(
        ["sbatch", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    if result.returncode == 0:
        print(f"✓ Job submitted: {result.stdout.strip()}")
    else:
        print(f"✗ Submission failed: {result.stderr}")
    
    return result