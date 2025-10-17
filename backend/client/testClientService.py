#!/usr/bin/env python3

import requests
import json
import time
import sys
import clientService
from flask import jsonify
import clientService

def test_client_service():
    """Test the containerized client service"""
    
    # Get client service IP
    try:
        with open("output/client_ip.txt", "r") as f:
            client_ip = f.read().strip()
    except FileNotFoundError:
        print("Error: client_ip.txt not found. Is the client service running?")
        return False
    
    base_url = f"http://{client_ip}:5000"
    print(f"Testing client service at: {base_url}")
    
    # Test 1: Health check
    print("\n1. Health check...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print("✓ Health check passed")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False
    
    # Test 2: Simple test endpoint
    print("\n2. Simple test query...")
    try:
        response = requests.get(f"{base_url}/simple-test", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print("✓ Simple test passed")
            print(f"  Prompt: {data.get('prompt', '')}")
            print(f"  Response length: {data.get('response_length', 0)} chars")
            print(f"  Request time: {data.get('request_time', 0):.2f}s")
            print(f"  Preview: {data.get('response', '')[:100]}...")
        else:
            print(f"✗ Simple test failed: {response.status_code}")
            print(f"  Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Simple test failed: {e}")
        return False
    
    # Test 3: Custom query
    print("\n3. Custom query test...")
    try:
        custom_prompt = "Explain what is machine learning in 2 sentences."
        payload = {
            "prompt": custom_prompt,
            "model": "mistral"
        }
        
        response = requests.post(
            f"{base_url}/query", 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Custom query passed")
            print(f"  Prompt: {custom_prompt}")
            print(f"  Response: {data.get('response', '')}")
            print(f"  Request time: {data.get('request_time', 0):.2f}s")
        else:
            print(f"✗ Custom query failed: {response.status_code}")
            print(f"  Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Custom query failed: {e}")
        return False
    
    print("\nAll tests passed! Client service is working correctly.")
    return True



def push_tps_to_pushgateway(tps_value, pushgateway_ip, client_id):
    metric_data = f"""
# TYPE tokens_per_second gauge
tokens_per_second{{client="{client_id}"}} {tps_value}
"""
    url = f"http://{pushgateway_ip}:9091/metrics/job/llm_inference/instance/{client_id}"
    response = requests.put(url, data=metric_data.encode('utf-8'), headers={'Content-Type': 'text/plain'})
    if response.status_code != 200:
        print(f"Error pushing TPS metric: {response.status_code} - {response.text}")

def query(data=None):
    """
    Query Ollama with prompt/model data.

    If `data` dict is not provided, it attempts to get JSON from Flask request.
    """
    try:
        print("hello from testClientService.py, query function!!")
        

        prompt = 'hello how are you?'
        model = 'mistral'
        
        print(f"Querying Ollama: {prompt[:50]}...")

        start_time = time.time()
        ollamaClientService= clientService.OllamaClientService()
        print("let's see the ollamaHost IP gatherd by the constructor->"+str(ollamaClientService.ollama_host))#prende localhost...
        with open('output/ollama_ip.txt', 'r') as f:
            ollama_ip = f.read().strip()

        ollamaClientService.ollama_host = ollama_ip
        print("setted ollama_ip to ollamaClientService.ollama_host->"+ ollamaClientService.ollama_host)
        print("initialiazed ollamaClientService")
        response=ollamaClientService.query_ollama(prompt, model)
        end_time = time.time()
        elapsed = end_time - start_time if end_time > start_time else 1e-6 # todo bring it to clientService.query_ollama
        print("computed elapsed time", elapsed);
        if 'response' in response:
            print("✓ Response received")
            text = response['response']#parsing the response to get the text
            num_tokens = len(text.split())
            tps = num_tokens / elapsed
            print(f"Response received: {len(text)} chars, TPS: {tps:.2f}")
            print(f"Preview: {text[:100]}...")

            try:
                with open("output/pushgateway_data/pushgateway_ip.txt", "r") as f:
                    pushgateway_ip = f.read().strip()
            except FileNotFoundError:
                print("Warning: pushgateway_ip.txt not found. Metrics will not be pushed.")
                pushgateway_ip = None

            client_id = "client_01" # todo, remove hardcoding!! In real use, generate or assign unique client IDs

            if pushgateway_ip:
                push_tps_to_pushgateway(tps, pushgateway_ip, client_id)
        else:
            print("response->", response)
            print(f"✗ Error in response: {response.get('error', 'Unknown error')}")

        # Return JSON response properly for Flask or JSON string outside Flask
        try:
            return jsonify(response)
        except RuntimeError:
            return json.dumps(response)

    except Exception as e:
        error_response = {"error": str(e)}
        print(f"✗ Exception occurred: {str(e)}")
        try:
            return jsonify(error_response)
        except RuntimeError:
            return json.dumps(error_response)



if __name__ == "__main__":
    success = test_client_service()
    sys.exit(0 if success else 1)