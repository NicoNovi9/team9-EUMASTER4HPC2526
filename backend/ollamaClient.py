import json
import subprocess
import os

class OllamaClient:
    def __init__(self, config=None, host=None, port=11434, model="llama2"):
        self.host = host or self._get_ollama_ip()
        self.port = port
        self.model = model
        
        # If config is provided, extract benchmark settings
        if config:
            job = config.get('job', {})
            service = job.get('service', {})
            self.model = service.get('model', self.model)
            self.n_clients = service.get('n_clients', 1)
            self.n_requests_per_client = service.get('n_requests_per_client', 1)
            self.max_tokens = service.get('max_tokens', 100)
        else:
            self.n_clients = 1
            self.n_requests_per_client = 1
            self.max_tokens = 100
    
    def _get_ollama_ip(self):
        try:
            with open("output/ollama_ip.txt", "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "localhost"
    
    def query(self, prompt):
        url = f"http://{self.host}:{self.port}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        
        cmd = ["curl", "-s", "-X", "POST", url, "-H", "Content-Type: application/json", "-d", json.dumps(payload)]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except:
            pass
        return None
    
    def test_connection(self):
        response = self.query("Hello")
        return response is not None
    
    def run_benchmark(self):
        """Run benchmark based on JSON configuration"""
        print(f"Starting benchmark with {self.n_clients} clients, {self.n_requests_per_client} requests each")
        print(f"Model: {self.model}, Max tokens: {self.max_tokens}")
        
        if not self.test_connection():
            print("Ollama connection failed")
            return False
        
        print("Ollama connection successful")
        
        # Simple benchmark - single client for now (skeleton)
        print("Running benchmark requests...")
        
        for client_id in range(self.n_clients):
            print(f"Client {client_id + 1}/{self.n_clients}")
            
            for request_id in range(self.n_requests_per_client):
                print(f"  Request {request_id + 1}/{self.n_requests_per_client}")
                
                # Simple test query
                response = self.query("What is AI?")
                
                if response:
                    response_text = response.get('response', '')
                    print(f"Response: {len(response_text)} chars")
                    if len(response_text) > 0:
                        print(f"    Preview: {response_text[:50]}...")
                else:
                    print(f"Request failed")
        
        print("Benchmark completed!")
        return True