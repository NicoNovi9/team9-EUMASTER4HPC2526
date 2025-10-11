# Client Service

This directory contains all client-related components for benchmarking Ollama.

## Files

- **`clientService.py`** - Flask REST API service
- **`clientServiceHandler.py`** - SLURM job handler for client service  
- **`client_service.def`** - Apptainer container definition
- **`Dockerfile.client`** - Docker container definition (legacy)
- **`launchClient.py`** - Script to launch client service on SLURM
- **`testClientService.py`** - Test script for client service

## Complete Workflow - Step by Step

### Step 1: Deploy Ollama Server
```bash
cd /home/users/u103210/team9-EUMASTER4HPC2526/backend
python3 orch.py recipe_ex/inference_recipe.json
```
This will:
- Submit SLURM job for Ollama server on GPU node
- Download and start Ollama container
- Pull the specified model (e.g., mistral)
- Save server IP to `output/ollama_ip.txt`

### Step 2: Wait for Server to be Ready
```bash
# Check job status
squeue -u $USER

# Check server logs (optional)
tail -f output/logs/ollama_service.err
```
Wait until you see Ollama listening on port 11434.

### Step 3: Deploy Client Service
```bash
python3 client/launchClient.py recipe_ex/inference_recipe.json
```
This will:
- Submit SLURM job for client service on CPU node
- Build Apptainer container with Flask REST API
- Start client service on port 5000
- Save client IP to `output/client_ip.txt`

### Step 4: Verify Both Services are Running
```bash
# Check all your jobs
squeue -u $USER

# Should show both:
# - ollama_service (on GPU node)
# - ollama_client (on CPU node)
```

### Step 5: Test the Setup
```bash
python3 client/testClientService.py
```
This will run automated tests including:
- Health check
- Simple AI query
- Custom query test

## Alternative: Using Workflow Manager

```bash
# Deploy everything step by step
python3 workflow.py server recipe_ex/inference_recipe.json
python3 workflow.py client recipe_ex/inference_recipe.json
python3 workflow.py test

# Check status
python3 workflow.py status

# Cleanup when done
python3 workflow.py cleanup
```

## Manual API Testing

Once both services are running, you can test manually:

### Get Service IPs
```bash
# Ollama server IP
cat output/ollama_ip.txt

# Client service IP  
cat output/client_ip.txt
```

### Test Endpoints
```bash
# Replace <client-ip> with actual IP from client_ip.txt

# Health check
curl http://<client-ip>:5000/health

# Simple test
curl http://<client-ip>:5000/simple-test

# Custom query
curl -X POST http://<client-ip>:5000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is machine learning?", "model": "mistral"}'
```

## Troubleshooting

### Check Job Logs
```bash
# Server logs
tail -f output/logs/ollama_service.out
tail -f output/logs/ollama_service.err

# Client logs  
tail -f output/logs/client_service.out
tail -f output/logs/client_service.err
```

### Common Issues
- **Container build fails**: Check `client_service.err` for Apptainer errors
- **Connection refused**: Server may not be ready yet, wait longer
- **Empty responses**: Check if correct model name is used in queries
- **Job pending**: Check SLURM queue status with `squeue`

### Manual Container Test
```bash
# Test container build manually
cd /home/users/u103210/team9-EUMASTER4HPC2526/backend
module load env/release/2024.1
module load Apptainer
apptainer build --sandbox test_client client/client_service.def
```