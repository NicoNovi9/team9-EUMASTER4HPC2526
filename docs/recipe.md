# HPC Benchmark Recipe Configuration

## Workload Types:
The workload types that users can benchmark include:
- **LLM (Large Language Model)**: Text generation, inference, fine-tuning tasks
- **Retrieval**: Document search, vector similarity, information retrieval tasks
- **Other**: Future works

## Example with INFERENCE workload:

```json
{
  "job": {
    "scenario": "benchmark_run_v1",
    "partition": "gpu",
    "account": "p301245",
    "resources": {
      "nodes": 2,
      "gpus": 2,
      "cpus_per_task": 16,
      "mem_gb": 64
    },
    "workload": {
      "service": "inference",
      "model": "deepseek-6.7b",
      "n_services": 2,
      "numClients": 32,
      "prompt_len": [256, 1024],
      "batchSize": 8,
      "precision": "fp16",
    },
    "metadata": {
      "notes": "benchmark generico HPC"
    }
  }
}

```

## Notes:
- Daniele needs to define the structure for Retrieval workloads
es: 
"workload": {
      "service": "inference",
      "model": "deepseek-6.7b",
      "n_services": 2,
      "numClients": 32,
      OTHER PARAMETER USEFULL FOR THE RETRIEVAL SYS
    },