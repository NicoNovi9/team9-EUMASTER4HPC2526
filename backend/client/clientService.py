#!/usr/bin/env python3

from flask import Flask, request, jsonify
import json
import subprocess
import os
import time
import requests

app = Flask(__name__)

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
        print("enerting clientService.query_ollama function")
        model = model or self.default_model
        print("ollama host querying ip!")
        print("ollama host is", self.ollama_host)
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
            end_time = time.time()
            
            if response.status_code == 200:
                response_data = response.json()
                response_data['request_time'] = end_time - start_time
                return response_data
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except requests.exceptions.RequestException as e:
            print("clientService request exception occurred:", e)
            return {"error": f"Request failed: {str(e)}"}
        except Exception as e:
            print("clientService general exception occurred:", e)
            return {"error": f"Exception occurred: {str(e)}"}

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

if __name__ == '__main__':
    print("Starting Ollama Client Service...")
    print(f"Ollama server: {client_service.ollama_host}:{client_service.ollama_port}")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)