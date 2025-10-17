#!/bin/bash
#SBATCH --job-name=prometheus_service
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4G
#SBATCH --time=01:00:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --output=output/logs/prometheus_service.out
#SBATCH --error=output/logs/prometheus_service.err

module load env/release/2024.1
module load Apptainer

# Go to submit directory
cd $SLURM_SUBMIT_DIR || exit 1

echo "Working directory: $(pwd)"

# Create directories including the new prometheus_assets folder
mkdir -p output/logs
mkdir -p output/prometheus_assets

# ALWAYS recreate prometheus.yml (var espansa correttamente)
PUSHGATEWAY_IP=$(cat output/pushgateway_data/pushgateway_ip.txt 2>/dev/null || echo "localhost")
echo "Current directoryy: $(pwd)"

cat > prometheus.yml <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  scrape_timeout: 10s

scrape_configs:
  # Prometheus monitoring itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']


  # Node Exporter for system hardware metrics
  - job_name: 'node_exporter'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/node_targets.json'
        refresh_interval: 10s
    scrape_interval: 15s

  # cAdvisor for container metrics
  - job_name: 'cadvisor'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/cadvisor_targets.json'
        refresh_interval: 10s
    scrape_interval: 15s

  # Pushgateway for pushed metrics
  - job_name: 'pushgateway'
    static_configs:
      - targets: ['$PUSHGATEWAY_IP:9091']
    scrape_interval: 10s
EOF

echo "✓ Prometheus configuration created"

# Initialize empty JSON target files in the new folder
echo '[]' > output/prometheus_assets/ollama_targets.json
echo '[]' > output/prometheus_assets/node_targets.json
echo '[]' > output/prometheus_assets/cadvisor_targets.json

# Optional: show prometheus.yml for debugging
echo "---- prometheus.yml content ----"
cat prometheus.yml
echo "------------------------------"

# Pull Prometheus container if not already present
if [ ! -f output/containers/prometheus.sif ]; then
    echo "Pulling Prometheus image..."
    mkdir -p output/containers
    apptainer pull output/containers/prometheus.sif docker://prom/prometheus:latest
fi

# Start Prometheus with bind mounts
echo "Starting Prometheus..."
apptainer exec \
  --bind prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  --bind $(pwd)/output:/prometheus:ro \
  output/containers/prometheus.sif \
  prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.listen-address=0.0.0.0:9090 \
  --web.enable-lifecycle &

PROMETHEUS_PID=$!
echo "Prometheus PID: $PROMETHEUS_PID"

# Wait for Prometheus to start
sleep 10

echo "✓ Prometheus started at http://$(hostname -i):9090"
echo "Targets will be read from: $(pwd)/output/prometheus_assets/*.json"

# Keep Prometheus alive
wait $PROMETHEUS_PID
