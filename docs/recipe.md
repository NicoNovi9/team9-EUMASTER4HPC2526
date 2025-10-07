# HPC Benchmark Recipe Configuration

## Workload Types:
The workload types that users can benchmark include:
- **LLM (Large Language Model)**: Text generation, inference, fine-tuning tasks
- **Retrieval**: Document search, vector similarity, information retrieval tasks
- **Other**: Future works

## Example with INFERENCE workload:

```json
{
  "username": "p301245",
  "job": {
    "scenario": "benchmark_run_v1",
    "partition": "gpu",
    "service": "inference",
    "n_services": 2,
    "numClients": 32,
    "resources": {
      "nodes": 2,
      "gpus": 2,
      "cpus_per_task": 16,
      "mem_gb": 64
    },
    "workload": {
      "model": "deepseek-6.7b",
      "precision": "fp16",
      "context_length": 4096,
      "batchSize": 8,
      "n_services": 2,
      "numClients": 32,
      "prompt_len": [256, 1024],
      "max_tokens": 512,
      "temperature": 0.7
    },
    "metadata": {
      "notes": "benchmark generico HPC"
    }
  },
  "client": {
    "n_clients": 2,
    "n_requests_per_client": 5,
    "prompt": "What is artificial intelligence?",
    "test_duration": 60,
    "request_rate": 10
  }
}
```

## Notes:
- Daniele needs to define the structure for Retrieval workloads
es: 
```json
{
  "job": {
    "service": "retrieval",
    "workload": {
      "model": "some-embedding-model",
      "n_services": 2,
      "numClients": 32,
      // OTHER PARAMETER USEFUL FOR THE RETRIEVAL SYS
    }
  }
}
```