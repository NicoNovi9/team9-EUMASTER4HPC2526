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
- Examples: Ollama (LLM serving), Qdrant (for KNN retrieval benchmarks with FAISS).

### Monitoring (optional)
- A separate service container (e.g., Prometheus) can be integrated to collect CPU/GPU/memory metrics.
- Should be started before client jobs to capture full run metrics.

### Logging
- Services are configured to log automatically when launched via Apptainer (stdout/stderr redirected to files under `output/logs/`).

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