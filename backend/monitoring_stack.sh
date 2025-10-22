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
module load Python

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
    uid: prometheus 
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

# Download Node Exporter dashboard for Ollama/Service nodes
if [ ! -f output/grafana_config/provisioning/dashboards/node-exporter-service.json ]; then
    echo "  - Creating Node Exporter Service dashboard..."
    curl -s -o /tmp/node-service-raw.json \
      https://grafana.com/api/dashboards/1860/revisions/latest/download
    
    if [ $? -eq 0 ] && [ -f /tmp/node-service-raw.json ]; then
        python3 << 'PYEOF' > output/grafana_config/provisioning/dashboards/node-exporter-service.json
import json

with open('/tmp/node-service-raw.json', 'r') as f:
    dashboard = json.load(f)

# Fix datasource references - be specific to avoid breaking other UIDs
def fix_datasource(obj):
    if isinstance(obj, dict):
        # Check if this dict has a 'datasource' key
        if 'datasource' in obj:
            ds = obj['datasource']
            # Fix string datasource
            if isinstance(ds, str) and ('${' in ds or ds == ''):
                obj['datasource'] = 'Prometheus'
            # Fix object datasource (but only if it looks like a datasource)
            elif isinstance(ds, dict):
                # Only modify if it has datasource-like properties
                if 'type' in ds or 'uid' in ds:
                    # Check if uid contains variable or is empty
                    if 'uid' in ds and (isinstance(ds['uid'], str) and ('${' in ds['uid'] or ds['uid'] == '')):
                        ds['uid'] = 'prometheus'
                    if 'type' not in ds or ds['type'] == '':
                        ds['type'] = 'prometheus'
        
        # Recurse into nested objects
        for key, value in obj.items():
            if key != 'datasource':  # Don't recurse into datasource we just fixed
                fix_datasource(value)
    elif isinstance(obj, list):
        for item in obj:
            fix_datasource(item)

# Fix all datasources
fix_datasource(dashboard)

# Update dashboard metadata (separate from datasources)
dashboard['title'] = 'Node Exporter - Ollama Service'
dashboard['uid'] = 'node-exporter-service'
if 'id' in dashboard:
    dashboard['id'] = None

print(json.dumps(dashboard, indent=2))
PYEOF
        
        echo "    ✓ Node Exporter Service dashboard created"
        rm -f /tmp/node-service-raw.json
    else
        echo "    ⚠️  Failed to download Node Exporter Service dashboard"
    fi
fi

# Download Node Exporter dashboard for Client nodes  
if [ ! -f output/grafana_config/provisioning/dashboards/node-exporter-client.json ]; then
    echo "  - Creating Node Exporter Client dashboard..."
    curl -s -o /tmp/node-client-raw.json \
      https://grafana.com/api/dashboards/1860/revisions/latest/download
    
    if [ $? -eq 0 ] && [ -f /tmp/node-client-raw.json ]; then
        python3 << 'PYEOF' > output/grafana_config/provisioning/dashboards/node-exporter-client.json
import json

with open('/tmp/node-client-raw.json', 'r') as f:
    dashboard = json.load(f)

def fix_datasource(obj):
    if isinstance(obj, dict):
        if 'datasource' in obj:
            ds = obj['datasource']
            if isinstance(ds, str) and ('${' in ds or ds == ''):
                obj['datasource'] = 'Prometheus'
            elif isinstance(ds, dict):
                if 'type' in ds or 'uid' in ds:
                    if 'uid' in ds and (isinstance(ds['uid'], str) and ('${' in ds['uid'] or ds['uid'] == '')):
                        ds['uid'] = 'prometheus'
                    if 'type' not in ds or ds['type'] == '':
                        ds['type'] = 'prometheus'
        
        for key, value in obj.items():
            if key != 'datasource':
                fix_datasource(value)
    elif isinstance(obj, list):
        for item in obj:
            fix_datasource(item)

fix_datasource(dashboard)
dashboard['title'] = 'Node Exporter - Client Nodes'
dashboard['uid'] = 'node-exporter-client'
if 'id' in dashboard:
    dashboard['id'] = None

print(json.dumps(dashboard, indent=2))
PYEOF
        
        echo "    ✓ Node Exporter Client dashboard created"
        rm -f /tmp/node-client-raw.json
    else
        echo "    ⚠️  Failed to create Client dashboard"
    fi
fi

# Keep cAdvisor and DCGM as before (sed works for them)
if [ ! -f output/grafana_config/provisioning/dashboards/cadvisor.json ]; then
    echo "  - Downloading cAdvisor dashboard..."
    curl -s -o output/grafana_config/provisioning/dashboards/cadvisor.json \
      https://grafana.com/api/dashboards/14282/revisions/latest/download || \
      echo "    ⚠️  Failed to download cAdvisor dashboard"
fi

if [ ! -f output/grafana_config/provisioning/dashboards/dcgm-gpu.json ]; then
    echo "  - Downloading NVIDIA DCGM GPU dashboard..."
    curl -s -o /tmp/dcgm-gpu-raw.json \
      https://grafana.com/api/dashboards/12239/revisions/latest/download
    
    if [ $? -eq 0 ] && [ -f /tmp/dcgm-gpu-raw.json ]; then
        sed -e 's/"datasource":[[:space:]]*"${DS_PROMETHEUS}"/"datasource": "Prometheus"/g' \
            -e 's/"uid":[[:space:]]*"${DS_PROMETHEUS}"/"uid": "prometheus"/g' \
            -e 's/${DS_PROMETHEUS}/Prometheus/g' \
            /tmp/dcgm-gpu-raw.json > output/grafana_config/provisioning/dashboards/dcgm-gpu.json
        
        echo "    ✓ DCGM dashboard downloaded and fixed"
        rm -f /tmp/dcgm-gpu-raw.json
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
echo "  - Node Exporter - Ollama Service (Nodes running Ollama)"
echo "  - Node Exporter - Client Nodes (Nodes running clients)"
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
