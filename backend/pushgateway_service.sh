#!/bin/bash
#SBATCH --job-name=pushgateway_service
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem-per-cpu=2G
#SBATCH --time=01:00:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --output=output/logs/pushgateway_service.out
#SBATCH --error=output/logs/pushgateway_service.err

module load env/release/2024.1
module load Apptainer

cd $SLURM_SUBMIT_DIR || exit 1

mkdir -p output/logs
mkdir -p output/pushgateway_data

# Scrivi l'IP del nodo in un file (IP pubblico/interfaccia di rete)
hostname -I | awk '{print $1}' > output/pushgateway_data/pushgateway_ip.txt

if [ ! -f output/containers/pushgateway.sif ]; then
    echo "Pulling Pushgateway image..."
    mkdir -p output/containers
    apptainer pull output/containers/pushgateway.sif docker://prom/pushgateway:latest
fi

echo "Starting Pushgateway..."
apptainer exec \
  --bind $(pwd)/output/pushgateway_data:/pushgateway-data \
  output/containers/pushgateway.sif \
  /bin/pushgateway \
  --log.level=debug \
  --web.listen-address=0.0.0.0:9091 &

PUSHGATEWAY_PID=$!
wait $PUSHGATEWAY_PID
