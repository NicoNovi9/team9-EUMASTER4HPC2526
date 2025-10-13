#!/usr/bin/env python3
"""
Simplified Flask REST API for querying Ollama server
"""
from flask import Flask, request, jsonify
import os
import time
import requests

app = Flask(__name__)

# Configuration
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'localhost')
OLLAMA_PORT = int(os.getenv('OLLAMA_PORT', 11434))
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'mistral')

def get_ollama_host():
    """Get Ollama server IP from file or environment"""
    try:
        with open("/app/data/ollama_ip.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return OLLAMA_HOST

def query_ollama(prompt, model=DEFAULT_MODEL):
    """Query Ollama server and return response"""
    url = f"http://{get_ollama_host()}:{OLLAMA_PORT}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=60)
        request_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            data['request_time'] = request_time
            return data, 200
        return {"error": f"HTTP {response.status_code}: {response.text}"}, response.status_code
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "healthy", "ollama_host": get_ollama_host()})

@app.route('/query', methods=['POST'])
def query():
    """Query Ollama with custom prompt"""
    data = request.get_json() or {}
    prompt = data.get('prompt', 'Hello, how are you?')
    model = data.get('model', DEFAULT_MODEL)
    
    result, status = query_ollama(prompt, model)
    return jsonify(result), status

if __name__ == '__main__':
    print(f"Starting Client Service on {get_ollama_host()}:{OLLAMA_PORT}")
    app.run(host='0.0.0.0', port=5000, debug=False)