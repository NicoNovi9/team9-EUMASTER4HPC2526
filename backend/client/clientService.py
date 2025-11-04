#!/usr/bin/env python3

from flask import Flask, request, jsonify
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor
import threading

app = Flask(__name__)

# Thread pool for parallel requests
executor = ThreadPoolExecutor(max_workers=10)

class OllamaClientService:
    def __init__(self):
        self.ollama_host = self._get_ollama_ip()
        self.ollama_port = 11434
        self.default_model = "mistral"
    
    def _get_ollama_ip(self):
        """Get Ollama server IP from file"""
        try:
            with open("/app/data/ollama_ip.txt", "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            # Fallback: try environment variable or localhost
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
                timeout=60,
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
            print(f"Response received: {len(response['response'])} chars")
            print(f"Preview: {response['response'][:100]}...")
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/benchmark', methods=['POST'])
def benchmark():
    """Run parallel benchmark queries"""
    try:
        data = request.get_json()
        num_queries = data.get('num_queries', 10)
        prompt = data.get('prompt', 'Hello, how are you?')
        model = data.get('model', client_service.default_model)
        parallel = data.get('parallel', True)
        
        print(f"Starting benchmark: {num_queries} queries, parallel={parallel}")
        
        start_time = time.time()
        
        if parallel:
            # Submit all queries to thread pool
            futures = []
            for i in range(num_queries):
                future = executor.submit(client_service.query_ollama, prompt, model)
                futures.append(future)
            
            # Collect results
            results = []
            for i, future in enumerate(futures):
                try:
                    result = future.result(timeout=120)
                    results.append(result)
                    print(f"Query {i+1}/{num_queries} completed")
                except Exception as e:
                    results.append({"error": str(e)})
                    print(f"Query {i+1}/{num_queries} failed: {e}")
        else:
            # Sequential execution
            results = []
            for i in range(num_queries):
                result = client_service.query_ollama(prompt, model)
                results.append(result)
                print(f"Query {i+1}/{num_queries} completed")
        
        total_time = time.time() - start_time
        
        # Calculate stats
        successful = sum(1 for r in results if 'error' not in r)
        failed = len(results) - successful
        avg_request_time = sum(r.get('request_time', 0) for r in results if 'error' not in r) / successful if successful > 0 else 0
        
        return jsonify({
            "total_queries": num_queries,
            "successful": successful,
            "failed": failed,
            "total_time": total_time,
            "avg_request_time": avg_request_time,
            "queries_per_second": num_queries / total_time if total_time > 0 else 0,
            "parallel": parallel,
            "results": results
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting Ollama Client Service...")
    print(f"Ollama server: {client_service.ollama_host}:{client_service.ollama_port}")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)