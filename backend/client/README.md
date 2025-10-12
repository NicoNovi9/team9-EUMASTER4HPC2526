# Client Service

REST API service for benchmarking Ollama server running on SLURM.

## Files

- **`clientService.py`** - Flask REST API service
- **`clientServiceHandler.py`** - SLURM job handler 
- **`client_service.def`** - Apptainer container definition
- **`testClientService.py`** - Test script

## Usage

### Deploy Everything
```bash
cd ../
python3 orch.py recipe_ex/inference_recipe.json
```
This deploys both Ollama server and client service.

### Test
```bash
cd ../
python3 client/testClientService.py
```

### Monitor
```bash
squeue -u $USER
```

## API Endpoints

- `GET /health` - Service status
- `GET /simple-test` - Quick AI test with predefined prompt
- `POST /query` - Custom AI query

### Example
```bash
curl -X POST http://$(cat ../output/client_ip.txt):5000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is AI?", "model": "mistral"}'
```

## Architecture

```
orch.py → ollamaService (GPU node) + clientServiceHandler (CPU node)
         ↓                                    ↓
    Ollama Server                    Flask API Container  
    (port 11434)                      (port 5000)
```