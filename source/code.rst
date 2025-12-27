Code Documentation
==================

Overview of project files and modules.

Backend Overview
----------------

The backend provides an orchestrated LLM inference service deployed on HPC infrastructure using SLURM. It manages Ollama server deployment, client services, and a monitoring stack with Prometheus and Grafana.

Architecture
~~~~~~~~~~~~

The system follows a distributed architecture:

1. **Orchestrator** - Central controller that coordinates all services
2. **Ollama Service** - GPU-accelerated LLM inference server
3. **Client Service** - REST API for querying the LLM
4. **Monitoring Stack** - Prometheus, Grafana, and exporters for metrics collection

Main Components
~~~~~~~~~~~~~~~

orch.py (Orchestrator)
^^^^^^^^^^^^^^^^^^^^^^

The main entry point that coordinates the deployment of all services.

**Usage:**

.. code-block:: bash

   python3 orch.py <recipe.json> [--no-monitoring]

**Key Functions:**

- ``prepare_monitoring()`` - Deploys Pushgateway and Prometheus/Grafana stack
- Waits for Ollama server to be ready with models loaded
- Deploys client service and verifies health

**Workflow:**

1. Parse JSON recipe file
2. Start monitoring services (optional)
3. Deploy Ollama server via ``ollamaService.setup_ollama()``
4. Wait for model loading (polls ``/api/tags`` endpoint)
5. Deploy client service via ``clientServiceHandler.setup_client_service()``
6. Verify client health endpoint

ollamaService.py
^^^^^^^^^^^^^^^^

Handles Ollama LLM server deployment on GPU nodes.

**Function:** ``setup_ollama(data)``

Generates and submits a SLURM batch script that:

- Pulls and starts the Ollama container with GPU support (``--nv``)
- Configures ``OLLAMA_NUM_PARALLEL`` for concurrent request handling
- Starts Node Exporter for hardware metrics (port 9100)
- Starts DCGM Exporter for GPU metrics (port 9400)
- Registers targets with Prometheus via JSON files
- Implements cleanup on job termination

**Configuration (from recipe):**

- ``partition`` - SLURM partition (default: gpu)
- ``time`` - Job time limit
- ``account`` - SLURM account
- ``nodes`` - Number of nodes
- ``mem_gb`` - Memory allocation
- ``model`` - LLM model name (e.g., llama2, mistral)
- ``n_clients`` - Number of parallel connections

Client Service
~~~~~~~~~~~~~~

clientServiceHandler.py
^^^^^^^^^^^^^^^^^^^^^^^

**Function:** ``setup_client_service(data)``

Deploys a containerized Flask-based REST API client on CPU nodes.

- Builds container from ``client_service.def`` using Apptainer
- Configures CPUs based on ``n_clients`` parameter
- Registers with Prometheus for monitoring
- Starts Node Exporter for metrics collection

clientService.py
^^^^^^^^^^^^^^^^

Flask REST API providing endpoints to interact with Ollama.

**Endpoints:**

- ``GET /health`` - Health check, returns Ollama host info
- ``POST /query`` - Single query to Ollama

  .. code-block:: json

     {"prompt": "Your question", "model": "llama2"}

- ``POST /benchmark`` - Run parallel benchmark tests

  .. code-block:: json

     {
       "n_clients": 10,
       "n_requests_per_client": 5,
       "prompt": "Test prompt",
       "model": "llama2"
     }

**Class:** ``OllamaClientService``

- ``_get_ollama_ip()`` - Reads Ollama server IP from output files
- ``query_ollama(prompt, model)`` - Sends POST request to Ollama ``/api/generate``

client_service.def
^^^^^^^^^^^^^^^^^^

Apptainer container definition for the client service.

- Base image: ``python:3.9-slim``
- Dependencies: Flask, requests
- Exposes port 5000

Monitoring Stack
~~~~~~~~~~~~~~~~

monitoring_stack.sh
^^^^^^^^^^^^^^^^^^^

SLURM script that deploys the monitoring infrastructure:

**Components:**

- **Prometheus** (port 9090) - Metrics collection and storage
- **Grafana** (port 3000) - Visualization dashboards

**Features:**

- File-based service discovery (``file_sd_configs``)
- Auto-discovers targets from JSON files in ``prometheus_assets/``
- Pre-configured Grafana datasource for Prometheus

pushgateway_service.sh
^^^^^^^^^^^^^^^^^^^^^^

Deploys Prometheus Pushgateway for receiving pushed metrics (port 9091).

prometheus_service.sh
^^^^^^^^^^^^^^^^^^^^^

Alternative standalone Prometheus deployment script.

SLURM Integration
~~~~~~~~~~~~~~~~~

slurm_orch.sh
^^^^^^^^^^^^^

Wrapper script to run the orchestrator as a SLURM job.

.. code-block:: bash

   sbatch slurm_orch.sh

- Installs Python dependencies
- Cleans previous output directory
- Executes ``orch.py`` with the default recipe

Recipe Configuration
~~~~~~~~~~~~~~~~~~~~

Recipes are JSON files defining job parameters. Example (``recipe_ex/inference_recipe.json``):

.. code-block:: json

   {
     "job": {
       "name": "ollama_inference_job",
       "infrastructure": {
         "partition": "cpu",
         "account": "p200981",
         "nodes": 1,
         "mem_gb": 64,
         "time": "01:00:00"
       },
       "service": {
         "type": "inference",
         "model": "llama2",
         "precision": "fp16",
         "n_clients": 100,
         "n_requests_per_client": 10
       }
     }
   }

**Infrastructure Parameters:**

- ``partition`` - SLURM partition (cpu/gpu)
- ``account`` - SLURM billing account
- ``nodes`` - Number of compute nodes
- ``mem_gb`` - Memory per node in GB
- ``time`` - Maximum job duration

**Service Parameters:**

- ``model`` - LLM model to deploy
- ``n_clients`` - Number of parallel clients
- ``n_requests_per_client`` - Requests per client for benchmarks

Output Structure
~~~~~~~~~~~~~~~~

The backend generates outputs in the ``output/`` directory:

.. code-block:: text

   output/
     ollama_ip_<jobid>.txt      # Ollama server IP
     client_ip_<jobid>.txt      # Client service IP
     containers/                 # Apptainer images
       ollama_latest.sif
       client_service.sif
       node_exporter.sif
       dcgm-exporter.sif
       pushgateway.sif
     logs/                       # SLURM job logs
       ollama_service_<jobid>.out/err
       client_service_<jobid>.out/err
       monitoring_stack.out/err
     ollama_models/              # Cached LLM models
     prometheus_assets/          # Service discovery files
       node_targets_<jobid>.json
       gpu_targets_<jobid>.json

Dependencies
~~~~~~~~~~~~

Python packages (see ``requirements.txt``):

- ``flask>=2.3.0`` - REST API framework
- ``requests>=2.31.0`` - HTTP client library
- ``werkzeug>=2.3.0`` - WSGI utilities

System requirements:

- SLURM workload manager
- Apptainer/Singularity container runtime
- GPU nodes with NVIDIA drivers (for Ollama)
- Python 3.x

qdrantService.py
~~~~~~~~~~~~~~~~

Placeholder module for future Qdrant vector database integration.

**Function:** ``setup_qdrant(data)`` - Generates SLURM script for Qdrant deployment (not yet fully implemented).

Source Code Reference
---------------------

For the complete source code, please refer to:
https://github.com/NicoNovi9/team9-EUMASTER4HPC2526