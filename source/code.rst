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