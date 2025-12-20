#!/usr/bin/env python3

from flask import Flask, request, jsonify
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Thread pool for parallel client simulation
executor = ThreadPoolExecutor(max_workers=20)
# No longer need ThreadPoolExecutor - each client does sequential requests

class OllamaClientService:
    def __init__(self):
        self.ollama_host = self._get_ollama_ip()
        self.ollama_port = 11434
        self.default_model = "mistral"
    
    def _get_ollama_ip(self):
        """Get Ollama server IP from file"""
        try:
            # Look for ollama_ip_*.txt files
            import glob
            print(f"DEBUG: Looking for files in /app/output/")
            all_files = glob.glob('/app/output/*')
            print(f"DEBUG: Found {len(all_files)} files: {all_files[:5]}")
            
            ollama_files = sorted(glob.glob('/app/output/ollama_ip_*.txt'), key=os.path.getmtime, reverse=True)
            print(f"DEBUG: Found {len(ollama_files)} ollama_ip files")
            
            if ollama_files:
                print(f"DEBUG: Using {ollama_files[0]}")
                with open(ollama_files[0], 'r') as f:
                    ip = f.read().strip()
                    print(f"DEBUG: Loaded IP: {ip}")
                    return ip
            
            # Fallback to environment variable
            print("DEBUG: No ollama_ip file found, using fallback")
            return os.getenv('OLLAMA_HOST', 'localhost')
        except Exception as e:
            print(f"Error loading Ollama IP: {e}")
            return os.getenv('OLLAMA_HOST', 'localhost')
    
    def query_ollama(self, prompt, model=None):
        """Query Ollama server with a prompt"""
        model = model or self.default_model
        print(f"Querying Ollama at {self.ollama_host} with model {model}")
        
        url = f"http://{self.ollama_host}:{self.ollama_port}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                url,
                json=payload,
                timeout=120,
                headers={'Content-Type': 'application/json'}
            )
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                response_data = response.json()
                response_data['request_time'] = elapsed
                return response_data
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            print(f"Request failed: {e}")
            return {"error": f"Request failed: {str(e)}"}

# Initialize service
client_service = OllamaClientService()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "ollama_host": client_service.ollama_host})

@app.route('/query', methods=['POST'])
def query():
    """Query Ollama with a prompt"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', 'Hello, how are you?')
        model = data.get('model', client_service.default_model)
        
        print(f"Querying Ollama: {prompt[:50]}...")
        
        response = client_service.query_ollama(prompt, model)
        
        if 'response' in response:
            print(f"Response: {len(response['response'])} chars")
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/benchmark', methods=['POST'])
def benchmark():
    """Run benchmark with n_clients doing n_requests each (in parallel)"""
    try:
        data = request.get_json()
        n_clients = data.get('n_clients', 1)
        n_requests_per_client = data.get('n_requests_per_client', 5)
        prompt = data.get('prompt', 'Hello, how are you?')
        model = data.get('model', client_service.default_model)
        
        print(f"Starting benchmark: {n_clients} clients × {n_requests_per_client} requests")
        
        start_time = time.time()
        
        def client_worker(client_id):
            """Each client does n_requests_per_client sequential requests"""
            import threading
            print(f"[Client {client_id}] Starting on thread {threading.current_thread().name}")
            results = []
            for i in range(n_requests_per_client):
                result = client_service.query_ollama(prompt, model)
                result['client_id'] = client_id
                result['request_id'] = i
                results.append(result)
                print(f"[Client {client_id}] Request {i+1}/{n_requests_per_client} completed in {result.get('request_time', 0):.2f}s")
            print(f"[Client {client_id}] Finished all {n_requests_per_client} requests")
            return results
        
        # Execute n_clients in parallel (each doing sequential requests)
        all_results = []
        futures = []
        for client_id in range(n_clients):
            future = executor.submit(client_worker, client_id)
            futures.append(future)
        
        # Collect all results
        for future in futures:
            client_results = future.result(timeout=600)
            all_results.extend(client_results)
        
        total_time = time.time() - start_time
        
        # Calculate stats
        total_queries = n_clients * n_requests_per_client
        successful = sum(1 for r in all_results if 'error' not in r)
        failed = total_queries - successful
        avg_request_time = sum(r.get('request_time', 0) for r in all_results if 'error' not in r) / successful if successful > 0 else 0
        
        return jsonify({
            "n_clients": n_clients,
            "n_requests_per_client": n_requests_per_client,
            "total_queries": total_queries,
            "successful": successful,
            "failed": failed,
            "total_time": total_time,
            "avg_request_time": avg_request_time,
            "queries_per_second": total_queries / total_time if total_time > 0 else 0,
            "results": all_results
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting Ollama Client Service...")
    print(f"Ollama server: {client_service.ollama_host}:{client_service.ollama_port}")
    
    # Check available CPUs
    import multiprocessing
    cpus_available = multiprocessing.cpu_count()
    slurm_cpus = os.getenv('SLURM_CPUS_ON_NODE', 'not set')
    print(f"CPUs available: {cpus_available}")
    print(f"SLURM_CPUS_ON_NODE: {slurm_cpus}")
    print(f"ThreadPoolExecutor max_workers: {executor._max_workers}")
    
    # Run Flask app (production mode, no debug!)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)