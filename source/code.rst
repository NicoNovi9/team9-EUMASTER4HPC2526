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

Deployment Flow
~~~~~~~~~~~~~~~

.. code-block:: text

   User -> orch.py -> [1] Pushgateway (SLURM job)
                   -> [2] Prometheus/Grafana (SLURM job)
                   -> [3] Ollama Service (SLURM job on GPU node)
                   -> [4] Client Service (SLURM job on CPU node)
                   -> [5] Run Benchmark Tests
                   -> [6] Collect Metrics via Pushgateway

Main Components
~~~~~~~~~~~~~~~

orch.py (Orchestrator)
^^^^^^^^^^^^^^^^^^^^^^

The main entry point that coordinates the deployment of all services.

**Usage:**

.. code-block:: bash

   python3 orch.py <recipe.json> [--no-monitoring]

**Arguments:**

- ``<recipe.json>`` - Path to job configuration file
- ``--no-monitoring`` - Skip Prometheus/Grafana deployment (optional)

**Key Functions:**

``prepare_monitoring()``
   Deploys the monitoring infrastructure:
   
   1. Checks if Pushgateway job is already running via ``squeue``
   2. Submits ``pushgateway_service.sh`` if needed
   3. Waits for Pushgateway to enter RUNNING state (polls every 5s)
   4. Checks if Prometheus job is already running
   5. Submits ``monitoring_stack.sh`` if needed
   6. Waits for Prometheus to enter RUNNING state
   7. Adds 10s delay for full initialization

**Main Execution Flow:**

1. Parse command line arguments and JSON recipe file
2. Call ``prepare_monitoring()`` unless ``--no-monitoring`` flag is set
3. Deploy Ollama server via ``ollamaService.setup_ollama(data)``
4. Wait for Ollama readiness (max 3600s timeout):

   - Poll for ``output/ollama_ip_*.txt`` file
   - Query ``/api/tags`` endpoint to verify model is loaded
   - Check every 10 seconds

5. Deploy client service via ``clientServiceHandler.setup_client_service(data)``
6. Wait for client service readiness (max 3600s timeout):

   - Poll for ``output/client_ip_*.txt`` file
   - Query ``/health`` endpoint
   - Add 10s stabilization delay

7. Install required Python packages (idna, charset_normalizer)
8. Extract benchmark parameters from recipe
9. Run benchmark via ``testClientService.run_benchmark()``

**Error Handling:**

- Exits with code 1 if recipe file not found or invalid JSON
- Exits with code 1 if Ollama server timeout (no models loaded)
- Exits with code 1 if client service timeout

ollamaService.py
^^^^^^^^^^^^^^^^

Handles Ollama LLM server deployment on GPU nodes.

**Function:** ``setup_ollama(data)``

Generates and submits a SLURM batch script that deploys Ollama with GPU support.

**Generated SLURM Script Structure:**

.. code-block:: bash

   #SBATCH --job-name=ollama_service
   #SBATCH --partition=<from recipe>
   #SBATCH --time=<from recipe>
   #SBATCH --account=<from recipe>
   #SBATCH --nodes=<from recipe>
   #SBATCH --mem=<from recipe>G

**Script Execution Steps:**

1. **Environment Setup**
   
   - Load modules: ``env/release/2024.1``, ``Apptainer``
   - Get node IP and hostname
   - Write IP to ``output/ollama_ip_<jobid>.txt``
   - Create persistent model directory

2. **Cleanup Handler**
   
   - Registers trap for EXIT signal
   - Removes Prometheus target files on job termination

3. **Node Exporter Deployment**
   
   - Pulls ``prom/node-exporter:latest`` container if not present
   - Starts with bind mounts for ``/proc`` and ``/sys``
   - Listens on port 9100
   - Registers target in ``node_targets_<jobid>.json``

4. **DCGM Exporter Deployment**
   
   - Pulls ``nvcr.io/nvidia/k8s/dcgm-exporter`` container
   - Starts with ``--nv`` flag for GPU access
   - Listens on port 9400
   - Registers target in ``gpu_targets_<jobid>.json``

5. **Ollama Service Startup**
   
   - Pulls ``ollama/ollama:latest`` container if not present
   - Environment variables:
   
     - ``OLLAMA_NUM_PARALLEL=<n_clients>`` - Concurrent request limit
     - ``OLLAMA_MAX_LOADED_MODELS=<n_clients>`` - Model cache size
   
   - Bind mounts ``output/ollama_models`` for persistent storage
   - Listens on port 11434

6. **Model Download**
   
   - Checks if model exists via ``ollama list``
   - Downloads model via ``ollama pull <model>`` if not present
   - Uses persistent storage to cache models between runs

**Configuration Parameters:**

+------------------------+------------------+------------------------+
| Parameter              | Default          | Description            |
+========================+==================+========================+
| ``partition``          | ``gpu``          | SLURM partition        |
+------------------------+------------------+------------------------+
| ``time``               | ``00:05:00``     | Job time limit         |
+------------------------+------------------+------------------------+
| ``account``            | ``p200981``      | SLURM account          |
+------------------------+------------------+------------------------+
| ``nodes``              | ``1``            | Number of nodes        |
+------------------------+------------------+------------------------+
| ``mem_gb``             | ``64``           | Memory in GB           |
+------------------------+------------------+------------------------+
| ``model``              | ``llama2``       | LLM model name         |
+------------------------+------------------+------------------------+
| ``n_clients``          | ``1``            | Parallel connections   |
+------------------------+------------------+------------------------+

**Prometheus Target Registration:**

Node Exporter target (``node_targets_<jobid>.json``):

.. code-block:: json

   [{
     "targets": ["<node_ip>:9100"],
     "labels": {
       "job": "node_exporter",
       "node": "<hostname>",
       "node_type": "service",
       "slurm_job_id": "<jobid>"
     }
   }]

GPU target (``gpu_targets_<jobid>.json``):

.. code-block:: json

   [{
     "targets": ["<node_ip>:9400"],
     "labels": {
       "job": "ollama_gpu",
       "node": "<hostname>",
       "gpu_type": "nvidia",
       "model": "<model_name>",
       "slurm_job_id": "<jobid>"
     }
   }]

Client Service
~~~~~~~~~~~~~~

clientServiceHandler.py
^^^^^^^^^^^^^^^^^^^^^^^

**Function:** ``setup_client_service(data)``

Deploys a containerized Flask-based REST API client on CPU nodes.

**Generated SLURM Script Structure:**

.. code-block:: bash

   #SBATCH --job-name=ollama_client
   #SBATCH --partition=cpu
   #SBATCH --cpus-per-task=<n_clients>
   #SBATCH --mem=<client_mem_gb>G

**Script Execution Steps:**

1. Write node IP to ``output/client_ip_<jobid>.txt``
2. Register client node in Prometheus via ``node_targets_client_<jobid>.json``
3. Start Node Exporter for client metrics (port 9100)
4. Build client container from ``client_service.def`` using Apptainer
5. Set environment variables:

   - ``OMP_NUM_THREADS=<n_clients>``
   - ``SLURM_CPUS_ON_NODE=<n_clients>``

6. Start Flask service with bind mount to ``output/`` directory

**Resource Allocation:**

The handler allocates 1 CPU per client to enable true parallel execution:

.. code-block:: python

   cpus_needed = n_clients  # 1 CPU per simulated client

clientService.py
^^^^^^^^^^^^^^^^

Flask REST API providing endpoints to interact with Ollama.

**Endpoints:**

``GET /health``
   Returns service health status and Ollama host information.
   
   Response:
   
   .. code-block:: json
   
      {"status": "healthy", "ollama_host": "10.x.x.x"}

``POST /query``
   Sends a single query to Ollama and returns the response.
   
   Request:
   
   .. code-block:: json
   
      {"prompt": "Your question", "model": "llama2"}
   
   Response includes:
   
   - ``response`` - Generated text
   - ``request_time`` - Elapsed time in seconds
   - Additional Ollama metadata (tokens, timing)

``POST /benchmark``
   Runs a parallel benchmark with multiple simulated clients.
   
   Request:
   
   .. code-block:: json
   
      {
        "n_clients": 10,
        "n_requests_per_client": 5,
        "prompt": "Test prompt",
        "model": "llama2"
      }
   
   **Execution Model:**
   
   Uses ``ThreadPoolExecutor`` with ``max_workers=20`` to run clients in parallel.
   Each client executes its requests sequentially within its thread.
   
   Response:
   
   .. code-block:: json
   
      {
        "n_clients": 10,
        "n_requests_per_client": 5,
        "total_queries": 50,
        "successful": 48,
        "failed": 2,
        "total_time": 120.5,
        "avg_request_time": 2.4,
        "queries_per_second": 0.41,
        "results": [...]
      }

**Class:** ``OllamaClientService``

``__init__()``
   Initializes the client and loads Ollama server IP.

``_get_ollama_ip()``
   Reads Ollama server IP from ``/app/output/ollama_ip_*.txt`` files.
   Falls back to ``OLLAMA_HOST`` environment variable or ``localhost``.

``query_ollama(prompt, model)``
   Sends POST request to Ollama ``/api/generate`` endpoint.
   
   - Timeout: 120 seconds
   - Stream: disabled
   - Returns response data with ``request_time`` added

testClientService.py
^^^^^^^^^^^^^^^^^^^^

Benchmark execution module that runs parallel tests and pushes metrics.

**Function:** ``run_benchmark(n_clients, n_requests_per_client, model)``

Orchestrates the benchmark by sending a single request to the client service
which handles internal parallelization.

**Execution Flow:**

1. Load client service IP from ``output/client_ip_*.txt``
2. Send POST request to ``/benchmark`` endpoint with parameters
3. Process results and calculate metrics:

   - Total tokens generated
   - Average tokens per second (TPS)
   - Request times

4. Push TPS metrics to Pushgateway for each request
5. Print summary report

**Helper Functions:**

``_load_pushgateway_ip()``
   Reads Pushgateway IP from ``output/pushgateway_data/pushgateway_ip.txt``

``_calculate_tokens(response_data)``
   Extracts token count from response, checking:
   
   1. ``eval_count`` field
   2. ``prompt_eval_count`` field
   3. Word count of response text (fallback)

``_push_to_pushgateway(tps, model, client_id, pushgateway_ip)``
   Pushes ``tokens_per_second`` gauge metric to Pushgateway:
   
   .. code-block:: text
   
      tokens_per_second{client_id="<id>",model="<model>"} <value>

**Command Line Usage:**

.. code-block:: bash

   python testClientService.py <n_clients> <n_requests> <model>

client_service.def
^^^^^^^^^^^^^^^^^^

Apptainer container definition for the client service.

.. code-block:: text

   Bootstrap: docker
   From: python:3.9-slim
   
   %post
       pip install flask requests
       mkdir -p /app /app/data
   
   %files
       client/clientService.py /app/clientService.py
   
   %runscript
       exec python /app/clientService.py

- Base image: ``python:3.9-slim``
- Dependencies: Flask, requests
- Exposes port 5000
- Mounts ``output/`` directory for IP file access

Monitoring Stack
~~~~~~~~~~~~~~~~

monitoring_stack.sh
^^^^^^^^^^^^^^^^^^^

SLURM script that deploys the complete monitoring infrastructure.

**SLURM Configuration:**

.. code-block:: bash

   #SBATCH --job-name=monitoring_stack
   #SBATCH --cpus-per-task=2
   #SBATCH --mem=8G
   #SBATCH --time=02:00:00
   #SBATCH --partition=cpu

**Components Deployed:**

+-----------------+-------+----------------------------------------+
| Service         | Port  | Description                            |
+=================+=======+========================================+
| Prometheus      | 9090  | Metrics collection and querying        |
+-----------------+-------+----------------------------------------+
| Grafana         | 3000  | Visualization dashboards               |
+-----------------+-------+----------------------------------------+

**Prometheus Configuration:**

Generated ``prometheus.yml`` with scrape configs:

.. code-block:: yaml

   global:
     scrape_interval: 15s
     evaluation_interval: 15s
   
   scrape_configs:
     - job_name: 'prometheus'
       static_configs:
         - targets: ['localhost:9090']
     
     - job_name: 'node_exporter'
       file_sd_configs:
         - files: ['/prometheus/prometheus_assets/node_targets_*.json']
           refresh_interval: 10s
     
     - job_name: 'dcgm_gpu'
       file_sd_configs:
         - files: ['/prometheus/prometheus_assets/gpu_targets_*.json']
           refresh_interval: 3s
     
     - job_name: 'pushgateway'
       static_configs:
         - targets: ['<pushgateway_ip>:9091']

**Grafana Configuration:**

Auto-provisioned datasource (``prometheus.yml``):

.. code-block:: yaml

   datasources:
     - name: Prometheus
       type: prometheus
       uid: prometheus
       url: http://localhost:9090
       isDefault: true

**Pre-configured Dashboards:**

1. **Node Exporter - Ollama Service** - System metrics for GPU nodes
2. **Node Exporter - Client Nodes** - System metrics for client nodes
3. **cAdvisor** - Container metrics
4. **NVIDIA DCGM GPU** - GPU utilization, memory, temperature
5. **Tokens Per Second** - Custom benchmark metrics dashboard

**Tokens Per Second Dashboard:**

Custom dashboard displaying benchmark metrics from Pushgateway:

- Average TPS by model over time
- Model comparison visualization
- Color thresholds: red (<30), yellow (30-80), green (>80)

pushgateway_service.sh
^^^^^^^^^^^^^^^^^^^^^^

Deploys Prometheus Pushgateway for receiving pushed metrics.

**SLURM Configuration:**

.. code-block:: bash

   #SBATCH --job-name=pushgateway_service
   #SBATCH --cpus-per-task=2
   #SBATCH --mem-per-cpu=2G
   #SBATCH --partition=cpu

**Execution:**

1. Write node IP to ``output/pushgateway_data/pushgateway_ip.txt``
2. Pull ``prom/pushgateway:latest`` container
3. Start Pushgateway on port 9091 with debug logging

**Metrics Endpoint:**

- Push URL: ``http://<ip>:9091/metrics/job/<job>/instance/<instance>``
- Query URL: ``http://<ip>:9091/metrics``

SLURM Integration
~~~~~~~~~~~~~~~~~

slurm_orch.sh
^^^^^^^^^^^^^

Wrapper script to run the orchestrator as a SLURM job.

**SLURM Configuration:**

.. code-block:: bash

   #SBATCH --time=01:00:00
   #SBATCH --partition=cpu
   #SBATCH --nodes=1
   #SBATCH --ntasks=32

**Execution:**

.. code-block:: bash

   sbatch slurm_orch.sh

1. Load Python module
2. Install dependencies from ``requirements.txt``
3. Clean previous ``output/`` directory
4. Execute ``python -u orch.py recipe_ex/inference_recipe.json "$@"``

The ``-u`` flag enables unbuffered output for real-time logging.

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

Frontend Overview
-----------------

The frontend provides a web-based interface for configuring and submitting LLM inference jobs to the HPC cluster. It connects to MeluXina via SSH and manages job submission, monitoring tunnels, and log viewing.

Architecture
~~~~~~~~~~~~

The frontend is a Node.js/Express application that:

1. Serves a wizard-based HTML interface for job configuration
2. Establishes SSH connections to the HPC cluster
3. Uploads backend files and submits SLURM jobs
4. Creates SSH tunnels for Grafana access
5. Provides log browsing capabilities

Main Components
~~~~~~~~~~~~~~~

conn_melux.js
^^^^^^^^^^^^^

Main Express server and SSH orchestration module.

**Usage:**

.. code-block:: bash

   node conn_melux.js webapp

**Key Functions:**

- ``doBenchmarking(res, uploadSourceFiles)`` - Orchestrates the benchmark workflow:

  - Establishes SSH connection to MeluXina
  - Uploads backend source files via SFTP
  - Submits SLURM job via ``sbatch``
  - Waits for Prometheus readiness
  - Retrieves Ollama service information
  - Sets up Grafana SSH tunnel

- ``submitSqueue()`` - Retrieves current SLURM queue status
- ``submitCancel(jobId)`` - Cancels a running SLURM job
- ``setupWebApp()`` - Configures Express routes and starts the server

**REST Endpoints:**

- ``GET /`` - Serves the wizard HTML page
- ``POST /startbenchmark`` - Submits a new benchmark job
- ``GET /squeue`` - Returns current job queue
- ``POST /scancel/:jobId`` - Cancels specified job
- ``POST /setup-tunnel`` - Establishes Grafana tunnel
- ``GET /logs`` - Browse log files
- ``GET /logs/view`` - View log file content
- ``GET /logs/download`` - Download log file

helper.js
^^^^^^^^^

Utility functions for SSH operations, file handling, and service discovery.

**Key Functions:**

- ``getSSHConnection()`` - Returns or creates a persistent SSH connection
- ``execCommand(conn, command)`` - Executes remote SSH command
- ``uploadFiles(sftp, files)`` - Uploads multiple files via SFTP
- ``waitForPrometheus(retries, delay)`` - Polls Prometheus health endpoint
- ``getPrometheusNode(conn, username)`` - Finds monitoring stack compute node
- ``getOllamaServiceInfo(conn, username)`` - Retrieves Ollama job details with retry logic
- ``setupGrafanaTunnel()`` - Creates SSH tunnel for Grafana access (port 3000)
- ``listLogsDirectory(conn, path)`` - Lists log files in remote directory
- ``readLogFile(conn, path)`` - Reads log file content
- ``generateJobSH(username)`` - Generates SLURM job submission script
- ``renderTemplate(templatePath, vars)`` - Renders HTML templates with variables

**SSH Configuration:**

- Host: ``login.lxp.lu``
- Port: ``8822``
- Authentication: SSH private key

constants.js
^^^^^^^^^^^^

Global state and configuration constants.

**Variables:**

- ``MONITORING_COMPUTE_NODE`` - Prometheus/Grafana node info (IP and hostname)
- ``GRAFANA_LOCAL_PORT`` - Local port for Grafana tunnel (default: 3000)
- ``sshConnection`` - Shared SSH connection instance
- ``prometheusServer`` - SSH tunnel server reference

wizard.html
^^^^^^^^^^^

Multi-step wizard interface for job configuration.

**Steps:**

1. **Job Name** - Set job identifier
2. **Infrastructure** - Configure SLURM parameters (partition, account, nodes, memory, time)
3. **Service** - Define LLM settings (model, precision, clients, requests, prompt)
4. **Review** - Preview JSON configuration and submit

**Key Functions (JavaScript):**

- ``generateConfigObject()`` - Builds JSON recipe from form inputs
- ``callBenchmark(config)`` - Sends configuration to backend
- ``useDefaults()`` - Applies default configuration values
- ``changeStep(direction)`` - Navigates between wizard steps

**Default Configuration:**

.. code-block:: javascript

   {
     jobName: "ollama_inference_job",
     partition: "gpu",
     account: "p200981",
     nodes: 1,
     memory: 64,
     time: "00:05:00",
     model: "llama2",
     precision: "fp16",
     nClients: 2,
     nRequests: 5
   }

Templates
~~~~~~~~~

log-browser.html
^^^^^^^^^^^^^^^^

HTML template for browsing log directories. Displays files and folders with:

- File/folder icons
- File size and modification date
- View and download buttons for files

log-viewer.html
^^^^^^^^^^^^^^^

HTML template for viewing log file contents with:

- Syntax highlighting for log entries
- File metadata display
- Back navigation and download options

Configuration Files
~~~~~~~~~~~~~~~~~~~

package.json
^^^^^^^^^^^^

Node.js project configuration.

**Dependencies:**

- ``ssh2`` - SSH2 client for Node.js
- ``http-proxy-middleware`` - HTTP proxy middleware
- ``express`` - Web framework (peer dependency)
- ``p-limit`` - Concurrency limiter for SFTP operations

**Scripts:**

.. code-block:: bash

   npm start  # Runs: node conn_melux.js

recipe.json
^^^^^^^^^^^

Stores the last submitted job configuration (generated by the wizard).

Workflow
~~~~~~~~

1. User opens ``http://localhost:8000`` in browser
2. Configures job parameters through wizard steps
3. Clicks "Start Benchmark" on final step
4. Frontend saves configuration to ``recipe.json``
5. Establishes SSH connection to MeluXina
6. Uploads backend files (if enabled)
7. Submits ``job.sh`` via ``sbatch``
8. Waits for Prometheus/Grafana to be ready
9. Creates SSH tunnel for Grafana (local port 3000)
10. Redirects user to Grafana dashboard

SSH Tunnel Setup
~~~~~~~~~~~~~~~~

The frontend creates an SSH tunnel for accessing Grafana:

- **Local port**: 3000
- **Remote**: Grafana on monitoring compute node (port 3000)
- **Access**: ``http://localhost:3000`` after job submission

Source Code Reference
---------------------

For the complete source code, please refer to:
https://github.com/NicoNovi9/team9-EUMASTER4HPC2526