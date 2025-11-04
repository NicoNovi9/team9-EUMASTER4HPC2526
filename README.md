# team9-EUMASTER4HPC2526

## Benchmarking AI Factories on Meluxina

This project provides a minimal, configuration‑driven framework for benchmarking AI services (e.g., Ollama) on the Meluxina supercomputer using Apptainer and SLURM. It aims to deploy, monitor, and execute service‑based benchmarks on Meluxina with minimal manual setup.

The system is configuration‑driven (JSON/YAML): it orchestrates services, clients, and optional monitoring pipelines automatically.

---

## Components

### Orchestrator (`orch.py`)
- Main entry point. Reads a JSON recipe and deploys both the Ollama server (on a GPU node) and the client REST API (on a CPU node) via SLURM.
- Handles all job submission logic directly and ensures services are up before clients start.

### Ollama Service
- Runs in an Apptainer container on a GPU node.
- Serves LLMs (e.g., mistral) via HTTP API on port 11434.
- Logs are written to `output/logs/ollama_service.out` and `output/logs/ollama_service.err`.

### Client Service
- Runs in an Apptainer container on a CPU node.
- Exposes a Flask REST API (port 5000) for benchmarking and testing the Ollama server.
- Main endpoints: `/health`, `/simple-test`, `/query`.
- Logs are written to `output/logs/client_service.out` and `output/logs/client_service.err`.

### Services (Containerized Software)
- Benchmarked systems or libraries run inside Apptainer containers.
- Examples: Ollama (LLM serving), Qdrant (for KNN retrieval benchmarks with FAISS, optional).

### Monitoring 

- **Monitoring Stack**: A `monitoring_stack` service runs Prometheus and Grafana together on a dedicated compute node via SLURM job submission
- *Automatic Detection*: The system automatically detects which compute node is running the monitoring stack using `squeue` commands
- *Prometheus Health Checks*: The application waits for Prometheus to become ready (checking `http://{node}:9090/-/healthy`) with configurable retries before proceeding
- *SSH Tunnel*: An SSH tunnel is automatically established to forward Grafana from the compute node to `localhost:3000` on your local machine for easy access
- *Pushgateway Integration*: A pushgateway service collects metrics from ephemeral jobs and forwards them to Prometheus
- *Startup Order*: The monitoring stack starts before the benchmark jobs to ensure all metrics are captured from the beginning


### Logging
- Services are configured to log automatically when launched via Apptainer (stdout/stderr redirected to files under `output/logs/`).
- *SLURM Native Logging*: Services launched via SLURM automatically capture stdout and stderr to `.out` and `.err` files in the `output/logs/` directory
- *Hierarchical Structure*: Logs are organized in subdirectories under `/home/users/{username}/output/logs/` based on job structure
- *Web-Based Log Browser*: An integrated web interface at `/logs` endpoint allows browsing, viewing, and downloading log files exploiting the current active SSH connection to Meluxina
- *Real-Time Access*: Log files can be viewed in real-time through the web interface
- *File Types*: 
  - `.out` files contain standard output (stdout)
  - `.err` files contain standard error (stderr)
  - Both are created automatically by SLURM for each job




### Testing
- Use `python3 client/testClientService.py` to verify the full stack after deployment.
- You can also manually test endpoints with `curl` using the client service IP.

---

## Quickstart

From the repository root:

```bash
# 1) Deploy everything (run from backend/)
cd backend
python3 orch.py recipe_ex/inference_recipe.json

# 2) Monitor jobs
squeue -u "$USER"

# 3) Test the deployment (run from backend/)
python3 client/testClientService.py
```

---

## File Structure (essentials)

```
backend/
├── orch.py                         # Main orchestrator script
├── ollamaService.py                # Ollama server SLURM handler
├── qdrantService.py                # Qdrant service handler (if used)
├── client/                         # Client REST API components
│   ├── clientService.py            # Flask API for benchmarking
│   ├── clientServiceHandler.py     # SLURM handler for client
│   ├── client_service.def          # Apptainer definition
│   ├── testClientService.py        # Test script
│   └── README.md                   # Client documentation
├── output/                         # Generated files and artifacts
│   ├── logs/                       # Service logs (*.out/*.err)
│   ├── scripts/                    # Generated SLURM scripts
│   ├── ollama_ip.txt               # Ollama server IP
│   └── client_ip.txt               # Client service IP
└── recipe_ex/                      # Example configurations
    └── inference_recipe.json       # Sample recipe
```

---

## Recipe Configuration

Example `inference_recipe.json`:

```json
{
  "job": {
    "name": "ollama_benchmark",
    "infrastructure": {
      "partition": "gpu",
      "time": "00:30:00",
      "account": "p200981",
      "nodes": 1,
      "mem_gb": 32
    },
    "service": {
      "type": "inference",
      "model": "mistral"
    }
  }
}
```

---

## Notes

- The architecture is simplified: `orch.py` directly manages both server and client deployments.
- All services run in Apptainer containers for reproducibility and isolation.
- The framework is minimal and easy to extend for new services or more complex benchmarks.