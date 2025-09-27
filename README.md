# team9-EUMASTER4HPC2526
# 🧪 Benchmarking AI Factories

This project develops a **benchmarking platform** for various components of an AI ecosystem running on Meluxina.  
The goal is to measure the performance and resource usage of *retrieval systems*, *inference engines*, and I/O operations within a microservices-based architecture.

---

## 📐 Architecture

The system is built around **four main pillars**:

1. **Server**  
   Service that performs the actual benchmarks:
   - **Retrieval System**  
     - **Purpose**: Uses similarity search tools such as [FAISS](https://github.com/facebookresearch/faiss) to measure the retrieval time of *N nearest neighbors* of vectors of dimension K.  
     - **Input**:  vector length, number of neighbors.  
     - **Output**: execution time.

   - **Inference Engine**  
     - **Purpose**: Based on [Ollama](https://ollama.ai) + **Mistral** model executed in Apptainer.  To mitigate stochastic variability, the same prompt is repeated multiple times and the results are averaged (*Monte Carlo*).
     - **Input**:  prompt.  
     - **Output**: `time_to_first_token` and `tokens_generated_per_second`.

   - **I/O Benchmark (if enough time)**  
     -  **Purpose**: Measures read/write times for large files.  
     - **Input**: file size and path.  
     - **Output**: write and read time.

2. **Client**  
   -  **Purpose**: Exposes a “menu” endpoint to select and launch benchmarks.  
   - **Input**: number of clients, services to execute, configuration, hardware resources (CPU/GPU, number of cores) where each service will run.  
   - **Output**: `ok` if the jobs are submitted, `ko + reason` in case of failure.  
   - (Possible future extension: orchestration with [Dask](https://www.dask.org/)).

3. **Monitor**  
   -  **Purpose**: Web service showing real-time status of active jobs.  
   - **Input**: which job to monitor (eg. retrieval, inference, I/O).  
   - **Output**: computational resources in use (eg. GPU, CPU, memory) and possibly workload (eg. records processed).
   (Possible future extension: monitoring through Grafana)

4. **Log**  
   -  **Purpose**: Configurable logging system via REST or file.  Reads an expiration `DateTime` and a `logLevel` (eg. 0=info, 1=warning, 2=error) written in the config file.  During execution of our benchmarking services, all the custom logging statements are written to a file while the configuration is valid.
    - **Input**: dateTime util logging on permanent storage ends, loggingLevel.  
   - **Output**: file with all the logging statements being present in the benchmarking services.
   (Possible future extension: logging through Prometheus/Grafana Loki)

---

## 🏗️ Technologies (TBD, but likely:)

- **Containerization**: [Apptainer](https://apptainer.org/) for portability on HPC.
- **Web Frameworks**: [FastAPI](https://fastapi.tiangolo.com/).
- **Benchmarking Libraries**: FAISS, Ollama + Mistral LLM.
- **Monitoring & Logging**: Python built-in libraries (with possible extensions through Prometheus), configuration files, and REST API.

---