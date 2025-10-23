#!/usr/bin/env python3

import requests
import json
import time
import sys
import os
import glob
from flask import jsonify


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



def push_tps_to_pushgateway(tps_value, pushgateway_ip, client_id, model="unknown"):
    """Push TPS metric to Pushgateway"""
    metric_data = f"""# TYPE tokens_per_second gauge
tokens_per_second{{client_id="{client_id}",model="{model}"}} {tps_value}
"""
    url = f"http://{pushgateway_ip}:9091/metrics/job/benchmark/instance/{client_id}"
    
    print(f"\n=== PUSHING TO PUSHGATEWAY ===")
    print(f"URL: {url}")
    print(f"TPS: {tps_value:.2f}")
    print(f"Client ID: {client_id}")
    print(f"Model: {model}")
    
    try:
        response = requests.put(
            url,
            data=metric_data.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
            timeout=5
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✓ SUCCESSFULLY Pushed TPS={tps_value:.2f} to Pushgateway")
        else:
            print(f"✗ Pushgateway error: {response.status_code}")
            print(f"Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to push to Pushgateway: {e}")
        import traceback
        traceback.print_exc()
    
    print("=================================\n")


def query(data=None):
    """
    Query Ollama DIRECTLY and push metrics to Pushgateway.
    Bypasses clientService Flask completely.
    """
    try:
        print("\n" + "="*60)
        print("=== DIRECT OLLAMA QUERY (testClientService) ===")
        print("="*60)
        
        # Extract parameters
        prompt = data.get('prompt', 'hello how are you?') if data else 'hello how are you?'
        model = data.get('model', 'mistral') if data else 'mistral'
        
        print(f"Prompt: {prompt[:50]}...")
        print(f"Model: {model}")
        
        # Load Ollama IP (with job ID pattern support)
        try:
            if os.path.exists('output/ollama_ip.txt'):
                with open('output/ollama_ip.txt', 'r') as f:
                    ollama_ip = f.read().strip()
            else:
                ollama_files = sorted(glob.glob('output/ollama_ip_*.txt'), key=os.path.getmtime, reverse=True)
                if ollama_files:
                    with open(ollama_files[0], 'r') as f:
                        ollama_ip = f.read().strip()
                    print(f"Using Ollama IP file: {ollama_files[0]}")
                else:
                    print("✗ Error: No ollama_ip file found")
                    return json.dumps({"error": "ollama_ip file not found"})
        except Exception as e:
            print(f"✗ Error loading Ollama IP: {e}")
            return json.dumps({"error": str(e)})
        
        print(f"Ollama IP: {ollama_ip}")
        
        # Construct Ollama API URL
        ollama_url = f"http://{ollama_ip}:11434/api/generate"
        print(f"Ollama URL: {ollama_url}")
        
        # Prepare payload
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        # Query Ollama with retry logic
        max_retries = 3
        response_data = None
        
        for attempt in range(max_retries):
            try:
                print(f"\nAttempt {attempt+1}/{max_retries}: Calling Ollama directly...")
                start_time = time.time()
                
                response = requests.post(
                    ollama_url,
                    json=payload,
                    timeout=60,
                    headers={'Content-Type': 'application/json'}
                )
                
                end_time = time.time()
                elapsed = end_time - start_time
                
                if response.status_code == 200:
                    response_data = response.json()
                    print(f"✓ Response received from Ollama in {elapsed:.2f}s")
                    break
                else:
                    print(f"✗ Ollama returned {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                print(f"✗ Timeout on attempt {attempt+1}")
            except requests.exceptions.RequestException as e:
                print(f"✗ Request failed on attempt {attempt+1}: {e}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                error_response = {"error": f"Failed to reach Ollama after {max_retries} attempts"}
                print(f"✗ {error_response['error']}")
                try:
                    return jsonify(error_response)
                except RuntimeError:
                    return json.dumps(error_response)
        
        # Process response and calculate TPS
        if response_data and 'response' in response_data:
            text = response_data['response']
            print(f"\n✓ Response received")
            print(f"  Text length: {len(text)} chars")
            
            # Calculate TPS using eval_count from Ollama (MODEL AGNOSTIC)
            if 'eval_count' in response_data:
                num_tokens = response_data['eval_count']
                print(f"  ✓ Using eval_count: {num_tokens} tokens")
            elif 'prompt_eval_count' in response_data:
                num_tokens = response_data['prompt_eval_count']
                print(f"  ⚠ Using prompt_eval_count: {num_tokens} tokens")
            else:
                num_tokens = len(text.split())
                print(f"  ⚠ Estimating tokens from text: {num_tokens} tokens")
            
            tps = num_tokens / elapsed if elapsed > 0 else 0
            print(f"  ✓ Calculated TPS: {tps:.2f} tokens/sec")
            print(f"  Response preview: {text[:100]}...")
            
            # Load Pushgateway IP
            try:
                with open("output/pushgateway_data/pushgateway_ip.txt", "r") as f:
                    pushgateway_ip = f.read().strip()
                print(f"\n✓ Pushgateway IP: {pushgateway_ip}")
            except FileNotFoundError:
                print("\n⚠ Warning: pushgateway_ip.txt not found. Metrics will NOT be pushed.")
                pushgateway_ip = None
            
            # Get client ID from environment or use default
            client_id = os.environ.get("CLIENT_ID", "client_direct_01")
            print(f"✓ Client ID: {client_id}")
            
            # Push metrics to Pushgateway
            if pushgateway_ip:
                push_tps_to_pushgateway(tps, pushgateway_ip, client_id, model)
            else:
                print("⚠ Skipping push - Pushgateway not configured")
            
            # Add computed metrics to response
            response_data['tps'] = tps
            response_data['num_tokens'] = num_tokens
            response_data['elapsed'] = elapsed
            
            print("\n" + "="*60)
            print("=== QUERY COMPLETED SUCCESSFULLY ===")
            print("="*60 + "\n")
            
        else:
            error_msg = response_data.get('error', 'Unknown error') if response_data else 'No response'
            print(f"\n✗ Error: {error_msg}")
            print("="*60 + "\n")
        
        # Return JSON response
        try:
            return jsonify(response_data)
        except RuntimeError:
            return json.dumps(response_data)
    
    except Exception as e:
        error_response = {"error": str(e)}
        print(f"\n✗ Exception in query(): {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*60 + "\n")
        try:
            return jsonify(error_response)
        except RuntimeError:
            return json.dumps(error_response)
        
if __name__ == "__main__":
    success = test_client_service()
    sys.exit(0 if success else 1)
