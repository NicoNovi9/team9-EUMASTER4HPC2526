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

System Flow
~~~~~~~~~~~

.. code-block:: text

   Browser (localhost:8000)
       |
       v
   Express Server (conn_melux.js)
       |
       +---> SSH Connection (ssh2) ---> MeluXina Login Node (login.lxp.lu:8822)
       |                                      |
       |                                      +---> SFTP File Upload
       |                                      +---> sbatch job.sh
       |                                      +---> squeue/scancel
       |
       +---> SSH Tunnel ---> Compute Node:3000 (Grafana)
       |
       v
   Local Browser ---> localhost:3000 ---> Grafana Dashboard

Main Components
~~~~~~~~~~~~~~~

conn_melux.js
^^^^^^^^^^^^^

Main Express server and SSH orchestration module.

**Usage:**

.. code-block:: bash

   # Start web application
   node conn_melux.js webapp
   
   # Check SLURM queue
   node conn_melux.js squeue
   
   # Cancel a job
   node conn_melux.js scancel <job_id>

**Server Configuration:**

.. code-block:: javascript

   const PORT = 8000;
   // Kills any existing process on port before starting
   require('child_process').execSync(`lsof -ti:${PORT} | xargs kill -9`);

**Function:** ``doBenchmarking(res, uploadSourceFiles)``

Orchestrates the complete benchmark workflow:

.. code-block:: text

   1. getSSHConnection()           --> Establish/reuse SSH connection
   2. conn.sftp()                  --> Get SFTP session
   3. generateJobSH(username)      --> Create SLURM job script
   4. uploadFiles(sftp, files)     --> Upload backend files (if enabled)
   5. execCommand('sbatch job.sh') --> Submit SLURM job
   6. waitForPrometheus()          --> Poll until Prometheus ready
   7. getOllamaServiceInfo()       --> Get Ollama job ID, IP, node
   8. setupGrafanaTunnel()         --> Create SSH tunnel to Grafana

**Files Uploaded (when uploadSourceFiles=true):**

.. code-block:: javascript

   [
     { local: 'job.sh', remote: 'job.sh' },
     { local: '../backend/orch.py', remote: 'orch.py' },
     { local: '../backend/requirements.txt', remote: 'requirements.txt' },
     { local: '../backend/client/clientService.py', remote: 'client/clientService.py' },
     { local: '../backend/client/clientServiceHandler.py', remote: 'client/clientServiceHandler.py' },
     { local: '../backend/client/testClientService.py', remote: 'client/testClientService.py' },
     { local: '../backend/ollamaService.py', remote: 'ollamaService.py' },
     { local: '../backend/qdrantService.py', remote: 'qdrantService.py' },
     { local: 'recipe.json', remote: 'recipe.json' },
     { local: '../backend/pushgateway_service.sh', remote: 'pushgateway_service.sh' },
     { local: '../backend/client/client_service.def', remote: 'client/client_service.def' },
     { local: '../backend/monitoring_stack.sh', remote: 'monitoring_stack.sh' }
   ]

**Function:** ``submitSqueue()``

Retrieves current SLURM queue status via SSH.

.. code-block:: javascript

   const output = await helper.execCommand(conn, 'squeue');
   return { success: true, output: output };

**Function:** ``submitCancel(jobId)``

Cancels a running SLURM job.

.. code-block:: javascript

   const output = await helper.execCommand(conn, `scancel ${jobId}`);

**Function:** ``setupWebApp()``

Configures Express routes and middleware:

.. code-block:: javascript

   app.use(express.json());
   app.use(express.static(__dirname));

**REST Endpoints:**

+-------------------------+--------+------------------------------------------------+
| Endpoint                | Method | Description                                    |
+=========================+========+================================================+
| ``/``                   | GET    | Serves wizard.html                             |
+-------------------------+--------+------------------------------------------------+
| ``/startbenchmark``     | POST   | Submits benchmark job, returns job info        |
+-------------------------+--------+------------------------------------------------+
| ``/squeue``             | GET    | Returns SLURM queue status                     |
+-------------------------+--------+------------------------------------------------+
| ``/scancel/:jobId``     | POST   | Cancels specified SLURM job                    |
+-------------------------+--------+------------------------------------------------+
| ``/setup-tunnel``       | POST   | Establishes Grafana SSH tunnel                 |
+-------------------------+--------+------------------------------------------------+
| ``/logs``               | GET    | Browse log directories (query: path)           |
+-------------------------+--------+------------------------------------------------+
| ``/logs/view``          | GET    | View log file content (query: file)            |
+-------------------------+--------+------------------------------------------------+
| ``/logs/download``      | GET    | Download log file (query: file)                |
+-------------------------+--------+------------------------------------------------+

**POST /startbenchmark Response:**

.. code-block:: json

   {
     "success": true,
     "message": "Benchmark job submitted successfully",
     "path": "/path/to/recipe.json",
     "fileName": "recipe.json",
     "jobId": "12345",
     "grafanaAddress": "http://localhost:3000",
     "ipComputeNodeService": "10.x.x.x",
     "ollamaComputeNode": "mel1234",
     "ollamaJobID": "12345"
   }

**Graceful Shutdown:**

.. code-block:: javascript

   process.on('SIGINT', () => {
     if (consts.prometheusServer) consts.prometheusServer.close();
     if (consts.sshConnection) consts.sshConnection.end();
     process.exit();
   });

helper.js
^^^^^^^^^

Utility functions for SSH operations, file handling, and service discovery.

**Initialization:**

.. code-block:: javascript

   function init() {
     contextParams = getContextParams();
     envParams = {
       'privateKeyPath': contextParams.privateKey,
       'username': contextParams.username,
       'host': 'login.lxp.lu',
       'port': 8822
     };
   }

**Function:** ``getContextParams()``

Returns user-specific SSH configuration based on local directory:

.. code-block:: javascript

   // Detects user from __dirname path
   if (__dirname.includes('ivanalkhayat')) {
     params.privateKey = '/Users/ivanalkhayat/.ssh/id_ed25519_mlux';
     params.username = 'u103038';
   }

**Function:** ``getSSHConnection()``

Returns existing SSH connection or creates a new one (singleton pattern):

.. code-block:: javascript

   // Connection reuse logic
   if (consts.sshConnection && consts.sshConnection._sock.readable) {
     return resolve(consts.sshConnection);
   }
   
   // Connection state tracking
   if (consts.isConnecting) {
     // Wait for existing connection attempt
   }

**SSH Configuration:**

.. code-block:: javascript

   const sshConfig = {
     host: 'login.lxp.lu',
     port: 8822,
     username: envParams.username,
     privateKey: fs.readFileSync(envParams.privateKeyPath)
   };

**Function:** ``execCommand(conn, command)``

Executes SSH command and returns output:

.. code-block:: javascript

   conn.exec(command, (err, stream) => {
     stream.on('data', (data) => { output += data.toString(); });
     stream.stderr.on('data', (data) => { errorOutput += data.toString(); });
     stream.on('close', () => { resolve(output); });
   });

**Function:** ``uploadFiles(sftp, files)``

Uploads multiple files via SFTP to remote server:

.. code-block:: javascript

   const remoteDir = '/home/users/' + envParams.username + '/client';
   for (const file of files) {
     await sftp.fastPut(file.local, file.remote);
   }

**Function:** ``waitForPrometheus(retries, delay)``

Polls Prometheus health endpoint until ready:

.. code-block:: javascript

   // Default: 30 retries, 2000ms delay
   const output = await execCommand(conn, 
     `curl -s http://${MONITORING_COMPUTE_NODE.ip}:9090/-/healthy`
   );
   if (output.includes('Prometheus')) return true;

**Function:** ``getPrometheusNode(conn, username, maxAttempts, delayMs)``

Finds monitoring_stack job and resolves compute node IP:

.. code-block:: javascript

   // Query squeue for monitoring_stack job
   const squeueCmd = `squeue -u ${username} -n monitoring_stack -h -o '%N'`;
   const node = await execCommand(conn, squeueCmd);
   
   // Resolve node hostname to IP
   const hostCmd = `host ${node}`;
   const hostResult = await execCommand(conn, hostCmd);
   // Extract IP from "has address X.X.X.X"

**Function:** ``getOllamaServiceInfo(conn, username, options)``

Retrieves Ollama service details with exponential backoff retry:

.. code-block:: javascript

   const options = {
     maxRetries: 10,
     initialDelay: 20000,      // 20 seconds before first attempt
     maxDelay: 60000,          // Cap at 60 seconds
     backoffMultiplier: 1.5
   };
   
   // Returns: { jobID, ip, node }

**Function:** ``setupGrafanaTunnel()``

Creates SSH port forwarding tunnel for Grafana:

.. code-block:: javascript

   // Create local TCP server
   consts.prometheusServer = net.createServer((localSocket) => {
     // Forward through SSH to compute node
     conn.forwardOut(
       '127.0.0.1', 0,                           // Source
       consts.MONITORING_COMPUTE_NODE.ip, 3000,  // Destination
       (err, remoteStream) => {
         localSocket.pipe(remoteStream).pipe(localSocket);
       }
     );
   });
   
   // Listen on localhost:3000
   consts.prometheusServer.listen(3000, '127.0.0.1');

**SFTP Helper Functions:**

Concurrency-limited SFTP operations using ``p-limit``:

.. code-block:: javascript

   const limit = pLimit(3);  // Max 3 concurrent SFTP operations
   let cachedSftp = null;    // Reuse SFTP session

``getSftp(conn)``
   Returns cached or new SFTP session.

``withRetry(fn, retries)``
   Wraps function with exponential backoff retry logic.

``listLogsDirectory(conn, remotePath, relativePath)``
   Lists files and directories with metadata (size, modified date).

``readLogFile(conn, remotePath)``
   Reads file content via SFTP stream.

``getFileInfo(conn, remotePath)``
   Returns file/directory metadata (size, modified, isDirectory).

**HTML Template Functions:**

``renderTemplate(templatePath, data)``
   Replaces ``{{PLACEHOLDER}}`` with actual values in template files.

``generateBreadcrumb(subPath)``
   Generates navigation breadcrumb HTML for log browser.

``generateLogsContent(logsList)``
   Generates HTML for files and directories list.

``generateDirectoryItem(dir)``
   Generates HTML for a directory entry with folder icon.

``generateFileItem(file)``
   Generates HTML for a file entry with appropriate icon (.err, .out, other).

**Function:** ``generateJobSH(username)``

Generates SLURM job submission script:

.. code-block:: bash

   #!/bin/bash -l
   #SBATCH --time=00:45:00
   #SBATCH --qos=default
   #SBATCH --partition=cpu
   #SBATCH --account=p200981
   #SBATCH --nodes=1
   #SBATCH --ntasks=1
   #SBATCH --output=/home/users/${username}/output/logs/%x_%j.out
   #SBATCH --error=/home/users/${username}/output/logs/%x_%j.err
   
   mkdir -p /home/users/${username}/output/logs
   module load Python
   python /home/users/u103038/orch.py /home/users/${username}/recipe.json

constants.js
^^^^^^^^^^^^

Global state and configuration constants.

.. code-block:: javascript

   let MONITORING_COMPUTE_NODE = null;  // {ip, node}
   const GRAFANA_LOCAL_PORT = 3000;
   
   let sshConnection = null;
   let isConnecting = false;
   let prometheusServer = null;
   
   module.exports = {
     MONITORING_COMPUTE_NODE,
     GRAFANA_LOCAL_PORT,
     prometheusServer,
     sshConnection,
     isConnecting
   };

wizard.html
^^^^^^^^^^^

Multi-step wizard interface for job configuration.

**HTML Structure:**

.. code-block:: html

   <div class="wizard-step" data-step="1">Step 1: Job Name</div>
   <div class="wizard-step" data-step="2">Step 2: Infrastructure</div>
   <div class="wizard-step" data-step="3">Step 3: Service</div>
   <div class="wizard-step" data-step="4">Step 4: Review</div>

**CSS Classes:**

- ``.wizard-step`` - Hidden by default (``display: none``)
- ``.wizard-step.active`` - Visible step (``display: block``)
- ``.switch-container`` - Flexbox container for checkbox options

**Form Fields:**

+-------------------------+------------------+------------------------+
| Field                   | Type             | Default Value          |
+=========================+==================+========================+
| ``jobName``             | text             | ollama_inference_job   |
+-------------------------+------------------+------------------------+
| ``partition``           | select           | gpu                    |
+-------------------------+------------------+------------------------+
| ``account``             | text             | p200981                |
+-------------------------+------------------+------------------------+
| ``nodes``               | number           | 1                      |
+-------------------------+------------------+------------------------+
| ``memory``              | number           | 64                     |
+-------------------------+------------------+------------------------+
| ``time``                | text             | 00:05:00               |
+-------------------------+------------------+------------------------+
| ``serviceType``         | select           | inference              |
+-------------------------+------------------+------------------------+
| ``model``               | text             | llama2                 |
+-------------------------+------------------+------------------------+
| ``precision``           | select           | fp16                   |
+-------------------------+------------------+------------------------+
| ``nClients``            | number           | 2                      |
+-------------------------+------------------+------------------------+
| ``nRequests``           | number           | 5                      |
+-------------------------+------------------+------------------------+
| ``prompt``              | textarea         | (empty)                |
+-------------------------+------------------+------------------------+
| ``uploadSourceFiles``   | checkbox         | checked                |
+-------------------------+------------------+------------------------+

**Function:** ``generateConfigObject()``

Builds JSON recipe from form inputs:

.. code-block:: javascript

   return {
     job: {
       name: document.getElementById('jobName').value,
       infrastructure: {
         partition: document.getElementById('partition').value,
         account: document.getElementById('account').value,
         nodes: parseInt(document.getElementById('nodes').value),
         mem_gb: parseInt(document.getElementById('memory').value),
         time: document.getElementById('time').value
       },
       service: {
         type: document.getElementById('serviceType').value,
         model: document.getElementById('model').value,
         precision: document.getElementById('precision').value,
         n_clients: parseInt(document.getElementById('nClients').value),
         n_requests_per_client: parseInt(document.getElementById('nRequests').value),
         prompt: document.getElementById('prompt').value
       }
     }
   };

**Function:** ``callBenchmark(config)``

Sends configuration to backend and handles response:

.. code-block:: javascript

   const response = await fetch('/startbenchmark', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify(config)
   });
   
   const result = await response.json();
   if (result.success) {
     alert("Ollama_jobId: " + result.ollamaJobID + 
           " on compute node: " + result.ollamaComputeNode);
     window.location.replace(result.grafanaAddress);
   }

**Function:** ``useDefaults()``

Applies default configuration and immediately submits job:

.. code-block:: javascript

   Object.keys(defaults).forEach(key => {
     const el = document.getElementById(key);
     if (el.type === 'checkbox') el.checked = defaults[key];
     else el.value = defaults[key];
   });
   await callBenchmark(generateConfigObject());

**Function:** ``changeStep(direction)``

Navigates between wizard steps:

.. code-block:: javascript

   // Hide current step
   document.querySelector(`.wizard-step[data-step="${currentStep}"]`)
     .classList.remove('active');
   
   // Show new step
   currentStep += direction;
   document.querySelector(`.wizard-step[data-step="${currentStep}"]`)
     .classList.add('active');
   
   // Update navigation buttons
   document.getElementById('prevBtn').style.display = 
     currentStep === 1 ? 'none' : 'block';

Templates
~~~~~~~~~

log-browser.html
^^^^^^^^^^^^^^^^

HTML template for browsing log directories.

**Template Variables:**

- ``{{BREADCRUMB}}`` - Navigation path HTML
- ``{{CONTENT}}`` - Directory/file listing HTML

**Styling Features:**

- Responsive grid layout with max-width 1200px
- Cards with shadow and hover effects
- Color-coded header (#2c3e50 dark blue)
- Action buttons: blue (View), green (Download)

**File Icons:**

- Folder: folder emoji
- .err files: red X emoji
- .out files: green checkmark emoji
- Other files: document emoji

log-viewer.html
^^^^^^^^^^^^^^^

HTML template for viewing log file contents.

**Template Variables:**

- ``{{FILE_NAME}}`` - Name of the log file
- ``{{FILE_META}}`` - Size and modification date
- ``{{BACK_LINK}}`` - URL to parent directory
- ``{{FILE_CONTENT}}`` - Actual log content (escaped HTML)

**Features:**

- Monospace font for log content
- Horizontal scrolling for long lines
- Download button in header
- Back navigation link

Configuration Files
~~~~~~~~~~~~~~~~~~~

package.json
^^^^^^^^^^^^

Node.js project configuration.

.. code-block:: json

   {
     "name": "team9_ssh_meluxina",
     "version": "1.0.0",
     "description": "Project for SSH to Meluxina",
     "main": "index.js",
     "scripts": {
       "start": "node conn_melux.js"
     },
     "dependencies": {
       "http-proxy-middleware": "^3.0.5",
       "ssh2": "^1.11.0"
     }
   }

**Dependencies:**

+---------------------------+----------+----------------------------------------+
| Package                   | Version  | Purpose                                |
+===========================+==========+========================================+
| ``ssh2``                  | ^1.11.0  | SSH2 client for Node.js                |
+---------------------------+----------+----------------------------------------+
| ``http-proxy-middleware`` | ^3.0.5   | HTTP proxy middleware                  |
+---------------------------+----------+----------------------------------------+
| ``express``               | (peer)   | Web framework                          |
+---------------------------+----------+----------------------------------------+
| ``p-limit``               | (peer)   | Concurrency limiter for SFTP           |
+---------------------------+----------+----------------------------------------+

**Scripts:**

.. code-block:: bash

   npm start        # Runs: node conn_melux.js
   npm run webapp   # Alias for: node conn_melux.js webapp

recipe.json
^^^^^^^^^^^

Stores the last submitted job configuration (generated by the wizard).

Updated on each ``/startbenchmark`` POST request before upload.

Complete Workflow
~~~~~~~~~~~~~~~~~

**Step-by-step execution:**

1. **User Access**
   
   - User opens ``http://localhost:8000`` in browser
   - Express serves ``wizard.html``

2. **Job Configuration**
   
   - User navigates through 4 wizard steps
   - Configures infrastructure and service parameters
   - Optionally enables/disables source file upload

3. **Job Submission**
   
   - User clicks "Start Benchmark" on Step 4
   - Frontend saves config to local ``recipe.json``
   - ``callBenchmark()`` POSTs to ``/startbenchmark``

4. **Backend Processing**
   
   - ``doBenchmarking()`` establishes SSH connection
   - Generates ``job.sh`` with user-specific paths
   - Uploads files via SFTP (if enabled)
   - Submits job: ``sbatch job.sh``

5. **Service Discovery**
   
   - ``waitForPrometheus()`` polls until monitoring ready
   - ``getOllamaServiceInfo()`` retrieves Ollama job details
   - Returns IP addresses and job IDs to frontend

6. **Tunnel Setup**
   
   - ``setupGrafanaTunnel()`` creates SSH port forward
   - Maps ``localhost:3000`` to compute node Grafana

7. **User Redirect**
   
   - Frontend receives success response
   - Shows alert with job information
   - Redirects browser to ``http://localhost:3000`` (Grafana)

SSH Tunnel Architecture
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   User Browser                Frontend Server              MeluXina
   (localhost:3000)           (Node.js)                    (Compute Node)
        |                          |                            |
        |---HTTP Request---------->|                            |
        |                          |---SSH forwardOut---------->|
        |                          |   to compute_node:3000     |
        |                          |<--Grafana Response---------|
        |<--HTTP Response----------|                            |

**Tunnel Lifecycle:**

1. Created after Prometheus becomes ready
2. Persists until ``SIGINT`` (Ctrl+C) or process exit
3. Handles multiple concurrent browser connections
4. Automatic cleanup on SSH connection close

Error Handling
~~~~~~~~~~~~~~

**SSH Connection Errors:**

.. code-block:: javascript

   consts.sshConnection.on('error', (err) => {
     consts.isConnecting = false;
     consts.sshConnection = null;
     reject(err);
   });

**SFTP Retry Logic:**

.. code-block:: javascript

   async function withRetry(fn, retries = 3) {
     for (let i = 0; i < retries; i++) {
       try {
         return await fn();
       } catch (err) {
         if (i === retries - 1) throw err;
         await sleep(1000 * (i + 1));  // Exponential backoff
       }
     }
   }

**Service Discovery Timeout:**

- Prometheus: 30 retries x 2s = 60s max
- Ollama: 10 retries with exponential backoff (20s initial)

Source Code Reference
---------------------

For the complete source code, please refer to:
https://github.com/NicoNovi9/team9-EUMASTER4HPC2526