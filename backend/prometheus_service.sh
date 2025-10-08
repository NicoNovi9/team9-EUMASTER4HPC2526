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
#SBATCH --output=prometheus_service.out
#SBATCH --error=prometheus_service.err

module load Apptainer


# Create basic Prometheus configuration if not present
if [ ! -f prometheus.yml ]; then
    cat > prometheus.yml <<EOF
global:
  scrape_interval: 600s
  evaluation_interval: 600s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
EOF
fi

# Pull Prometheus image if not already present
if [ ! -f prometheus.sif ]; then
    echo "Pulling Prometheus image..."
    apptainer pull prometheus.sif docker://prom/prometheus:latest
fi

# Start Prometheus service using internal container storage
apptainer exec \
  --bind prometheus.yml:/etc/prometheus/prometheus.yml \
  prometheus.sif \
  prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.listen-address=0.0.0.0:9090 &

# Capture PID
PROMETHEUS_PID=$!

# Wait for service to start
sleep 10


# Keep Prometheus alive
wait $PROMETHEUS_PID
