# team9-EUMASTER4HPC2526
# 🧪 Benchmarking AI Factories

This project provides a flexible benchmarking framework for deploying, monitoring, and executing service-based benchmarks on **Meluxina**.  
The system is designed to be configuration-driven (via JSON/YAML), making it possible to orchestrate services, clients, and monitoring pipelines automatically, while minimizing manual setup.  

---

## 📌 Project Overview

The benchmarking workflow is composed of several key components:

### 1. **Entry Point (Python Program)**
- Central control program that runs on Meluxina (does not necessarily require allocated resources).  
- Responsibilities:
  - Reads the configuration file (YAML/JSON).  
  - Launches the required **services** in containers (via Apptainer). it launches the sbatch of dynamically created .sh file configurations and through pyslurm/subprocess the containers are launched.
  - Ensures services are “up and running” before client jobs are submitted.  
  - Starts the **monitoring service** prior to launching jobs.  

### 2. **Services (Containerized Software)**
- Benchmarked systems or libraries that run inside Apptainer containers.  
- Examples:
  - **Qdrant** (used for KNN retrieval benchmarks with FAISS).  
  - **Ollama** (for LLM serving).  
- Characteristics:
  - Already implemented since the are pulled from dockerhub, ready to be containerized.  
  - Expose APIs and generate logs automatically (`stdout` and `stderr` redirected to `.log` files) through proper launching configuration.  

### 3. **Clients (Python Program + SLURM jobs)**
- Python programs that interact with service endpoints.  
- Configuration defines:
  - Which service endpoint to query.  
  - Parameters/payload of the requests.  
  - Computational resources to request (CPU, GPU, memory).  
  - Number of clients to deploy.  
- Each client job is submitted to SLURM (`sbatch`) and executed independently.  

### 4. **Monitoring (Prometheus Service)**
- A separate service container running **Prometheus**.  
- Must be started **before** client jobs are submitted.  
- Responsibilities:
  - Collects metrics on CPU, GPU, and memory usage from all service containers.  
  - Metrics are stored for later analysis.  

### 5. **Logging**
- Services are configured to log automatically when launched via Apptainer:  

  ```bash
  apptainer exec ollama.sif ollama serve > ollama_out.log 2> ollama_err.log