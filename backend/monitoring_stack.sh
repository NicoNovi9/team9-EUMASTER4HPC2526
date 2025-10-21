#!/bin/bash
#SBATCH --job-name=monitoring_stack
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --mem-per-cpu=4G
#SBATCH --time=01:00:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --output=output/logs/monitoring_stack.out
#SBATCH --error=output/logs/monitoring_stack.err

module load env/release/2024.1
module load Apptainer

# Go to submit directory
cd $SLURM_SUBMIT_DIR || exit 1

echo "Working directory: $(pwd)"

# Create directories
mkdir -p output/logs
mkdir -p output/prometheus_assets
mkdir -p output/grafana_data
mkdir -p output/grafana_config/provisioning/datasources
mkdir -p output/grafana_config/provisioning/dashboards
mkdir -p output/prometheus_data

# ========================================
# PROMETHEUS CONFIGURATION
# ========================================

PUSHGATEWAY_IP=$(cat output/pushgateway_data/pushgateway_ip.txt 2>/dev/null || echo "localhost")
echo "Current directory: $(pwd)"

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
          - '/prometheus/prometheus_assets/node_targets_*.json'
        refresh_interval: 10s
    scrape_interval: 15s

  # cAdvisor for container metrics
  - job_name: 'cadvisor'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/cadvisor_targets_*.json'
        refresh_interval: 10s
    scrape_interval: 15s

  # DCGM GPU Exporter for GPU metrics
  - job_name: 'dcgm_gpu'
    file_sd_configs:
      - files:
          - '/prometheus/prometheus_assets/gpu_targets_*.json'
        refresh_interval: 3s

  # Pushgateway for pushed metrics
  - job_name: 'pushgateway'
    static_configs:
      - targets: ['$PUSHGATEWAY_IP:9091']
    scrape_interval: 10s
EOF


echo "✓ Prometheus configuration created"

# Initialize empty JSON target files
#echo '[]' > output/prometheus_assets/ollama_targets.json
#echo '[]' > output/prometheus_assets/node_targets.json
#echo '[]' > output/prometheus_assets/cadvisor_targets.json
#echo '[]' > output/prometheus_assets/gpu_targets.json

# ========================================
# GRAFANA CONFIGURATION
# ========================================

# Provision Prometheus datasource (using localhost since same node)
cat > output/grafana_config/provisioning/datasources/prometheus.yml <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: 15s
EOF

echo "✓ Grafana datasource configuration created"

# Provision dashboard provider
cat > output/grafana_config/provisioning/dashboards/default.yml <<EOF
apiVersion: 1

providers:
  - name: 'System Metrics'
    orgId: 1
    folder: 'Hardware Monitoring'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

echo "✓ Grafana dashboard provider configuration created"

# ========================================
# DOWNLOAD GRAFANA DASHBOARDS
# ========================================

echo "Downloading preconfigured Grafana dashboards..."

# Download Node Exporter dashboard if not exists
if [ ! -f output/grafana_config/provisioning/dashboards/node-exporter.json ]; then
    echo "  - Downloading Node Exporter dashboard (ID 1860)..."
    curl -s -o output/grafana_config/provisioning/dashboards/node-exporter.json \
      https://grafana.com/api/dashboards/1860/revisions/latest/download || \
      echo "    ⚠️  Failed to download Node Exporter dashboard"
fi

# Download cAdvisor dashboard if not exists
if [ ! -f output/grafana_config/provisioning/dashboards/cadvisor.json ]; then
    echo "  - Downloading cAdvisor dashboard (ID 14282)..."
    curl -s -o output/grafana_config/provisioning/dashboards/cadvisor.json \
      https://grafana.com/api/dashboards/14282/revisions/latest/download || \
      echo "    ⚠️  Failed to download cAdvisor dashboard"
fi

# Download NVIDIA DCGM GPU dashboard if not exists
# Download NVIDIA DCGM GPU dashboard if not exists
if [ ! -f output/grafana_config/provisioning/dashboards/dcgm-gpu.json ]; then
    echo "  - Downloading NVIDIA DCGM GPU dashboard (ID 12239)..."
    
    # Download to temporary file first
    curl -s -o /tmp/dcgm-gpu-raw.json \
      https://grafana.com/api/dashboards/12239/revisions/latest/download
    
    if [ $? -eq 0 ] && [ -f /tmp/dcgm-gpu-raw.json ]; then
        # Fix datasource references for provisioning
        sed -e 's/"datasource":[[:space:]]*"${DS_PROMETHEUS}"/"datasource": "Prometheus"/g' \
            -e 's/"uid":[[:space:]]*"${DS_PROMETHEUS}"/"uid": "prometheus"/g' \
            -e 's/${DS_PROMETHEUS}/Prometheus/g' \
            /tmp/dcgm-gpu-raw.json > output/grafana_config/provisioning/dashboards/dcgm-gpu.json
        
        echo "    ✓ DCGM dashboard downloaded and fixed"
        rm -f /tmp/dcgm-gpu-raw.json
    else
        echo "    ⚠️  Failed to download DCGM GPU dashboard"
    fi
fi

echo "✓ Dashboard download completed"

# ========================================
# PULL CONTAINER IMAGES
# ========================================

# Pull Prometheus container if not already present
if [ ! -f output/containers/prometheus.sif ]; then
    echo "Pulling Prometheus image..."
    mkdir -p output/containers
    apptainer pull output/containers/prometheus.sif docker://prom/prometheus:latest
fi

# Pull Grafana container if not already present
if [ ! -f output/containers/grafana.sif ]; then
    echo "Pulling Grafana image..."
    mkdir -p output/containers
    apptainer pull output/containers/grafana.sif docker://grafana/grafana:latest
fi

# ========================================
# START PROMETHEUS
# ========================================

echo "Starting Prometheus..."
apptainer exec \
  --bind prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  --bind $(pwd)/output:/prometheus \
  output/containers/prometheus.sif \
  prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.listen-address=0.0.0.0:9090 \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=30d \
  --web.enable-lifecycle \
  > output/logs/prometheus_service.out 2> output/logs/prometheus_service.err &

PROMETHEUS_PID=$!
echo "Prometheus PID: $PROMETHEUS_PID"

# Wait for Prometheus to start
sleep 10

echo "✓ Prometheus started at http://$(hostname -i):9090"
echo "  Logs: output/logs/prometheus_service.{out,err}"

# ========================================
# START GRAFANA
# ========================================

echo "Starting Grafana..."
apptainer exec \
  --env GF_SECURITY_ADMIN_USER=admin \
  --env GF_SECURITY_ADMIN_PASSWORD=changeme123 \
  --env GF_USERS_ALLOW_SIGN_UP=false \
  --bind $(pwd)/output/grafana_data:/var/lib/grafana \
  --bind $(pwd)/output/grafana_config/provisioning:/etc/grafana/provisioning:ro \
  output/containers/grafana.sif \
  grafana-server \
  --homepath=/usr/share/grafana \
  > output/logs/grafana_service.out 2> output/logs/grafana_service.err &

GRAFANA_PID=$!
echo "Grafana PID: $GRAFANA_PID"

# Wait for Grafana to start
sleep 15

echo "✓ Grafana started at http://$(hostname -i):3000"
echo "  Username: admin"
echo "  Password: changeme123"
echo "  Logs: output/logs/grafana_service.{out,err}"

# ========================================
# SUMMARY
# ========================================

echo ""
echo "========================================="
echo "   MONITORING STACK READY"
echo "========================================="
echo "Node:       $(hostname)"
echo "IP:         $(hostname -i)"
echo ""
echo "Services:"
echo "  Prometheus: http://$(hostname -i):9090"
echo "  Grafana:    http://$(hostname -i):3000"
echo ""
echo "Dashboards provisioned:"
echo "  - Node Exporter (CPU, RAM, Disk, Network)"
echo "  - cAdvisor (Container metrics)"
echo "  - NVIDIA DCGM (GPU metrics)"
echo ""
echo "Prometheus targets: $(pwd)/output/prometheus_assets/*.json"
echo "========================================="
echo ""

# Save node info for reference
echo "$(hostname -i)" > output/prometheus_data/prometheus_ip.txt
echo "$(hostname -i)" > output/grafana_data/grafana_ip.txt

# Keep both services alive
wait $PROMETHEUS_PID $GRAFANA_PID
