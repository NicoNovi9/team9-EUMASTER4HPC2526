#!/usr/bin/env python3

import requests
import json
import time
import sys
import os
import glob


def _load_ollama_ip():
    if os.path.exists('output/ollama_ip.txt'):
        with open('output/ollama_ip.txt', 'r') as f:
            return f.read().strip()
    
    ollama_files = sorted(glob.glob('output/ollama_ip_*.txt'), key=os.path.getmtime, reverse=True)
    if ollama_files:
        with open(ollama_files[0], 'r') as f:
            return f.read().strip()
    
    raise FileNotFoundError("No ollama_ip file found")


def _load_pushgateway_ip():
    try:
        with open("output/pushgateway_data/pushgateway_ip.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def _calculate_tokens(response_data, text):
    if 'eval_count' in response_data:
        return response_data['eval_count']
    elif 'prompt_eval_count' in response_data:
        return response_data['prompt_eval_count']
    else:
        return len(text.split())


def push_tps_to_pushgateway(tps_value, pushgateway_ip, client_id, model="unknown"):
    metric_data = f"""# TYPE tokens_per_second gauge
tokens_per_second{{client_id="{client_id}",model="{model}"}} {tps_value}
"""
    url = f"http://{pushgateway_ip}:9091/metrics/job/benchmark/instance/{client_id}"
    
    try:
        response = requests.put(
            url,
            data=metric_data.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"Pushed TPS={tps_value:.2f} to Pushgateway")
        else:
            print(f"Pushgateway error: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to push to Pushgateway: {e}")


def query(prompt="hello how are you?", model="mistral"):
    print("\n" + "="*60)
    print("OLLAMA QUERY")
    print("="*60)
    print(f"Prompt: {prompt[:50]}...")
    print(f"Model: {model}")
    
    try:
        ollama_ip = _load_ollama_ip()
        print(f"Ollama IP: {ollama_ip}")
        
        ollama_url = f"http://{ollama_ip}:11434/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        max_retries = 3
        response_data = None
        elapsed = 0
        
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt+1}/{max_retries}...")
                start_time = time.time()
                
                response = requests.post(
                    ollama_url,
                    json=payload,
                    timeout=60,
                    headers={'Content-Type': 'application/json'}
                )
                
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    response_data = response.json()
                    print(f"Response received in {elapsed:.2f}s")
                    break
                else:
                    print(f"Ollama error {response.status_code}")
                    
            except requests.exceptions.Timeout:
                print(f"Timeout")
            except requests.exceptions.RequestException as e:
                print(f"Request error: {e}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        if not response_data:
            error = {"error": f"Ollama unreachable after {max_retries} attempts"}
            print(f"ERROR: {error['error']}")
            print("="*60 + "\n")
            return error
        
        if 'response' not in response_data:
            error = {"error": "Invalid Ollama response"}
            print(f"ERROR: {error['error']}")
            print("="*60 + "\n")
            return error
        
        text = response_data['response']
        num_tokens = _calculate_tokens(response_data, text)
        tps = num_tokens / elapsed if elapsed > 0 else 0
        
        print(f"Response completed")
        print(f"Length: {len(text)} chars | Tokens: {num_tokens} | TPS: {tps:.2f}")
        
        pushgateway_ip = _load_pushgateway_ip()
        if pushgateway_ip:
            client_id = os.environ.get("CLIENT_ID", "client_direct")
            push_tps_to_pushgateway(tps, pushgateway_ip, client_id, model)
        else:
            print("Pushgateway not configured")
        
        response_data['tps'] = tps
        response_data['num_tokens'] = num_tokens
        response_data['elapsed'] = elapsed
        
        print("="*60 + "\n")
        
        return response_data
        
    except FileNotFoundError as e:
        error = {"error": str(e)}
        print(f"ERROR: {error['error']}")
        print("="*60 + "\n")
        return error
    except Exception as e:
        error = {"error": str(e)}
        print(f"ERROR: {e}")
        print("="*60 + "\n")
        return error


def run_benchmark(num_queries=30, delay=1, model="llama2"):
    """Run multiple test queries to benchmark the Ollama service"""
    print("\n" + "="*60)
    print(f"STARTING BENCHMARK: {num_queries} queries")
    print(f"Model: {model}")
    print("="*60 + "\n")
    
    successful_queries = 0
    failed_queries = 0
    total_tps = 0
    
    for i in range(num_queries):
        print(f"\n--- Query {i+1}/{num_queries} ---")
        result = query(model=model)
        
        if "error" in result:
            print(f"✗ Query {i+1} failed: {result['error']}")
            failed_queries += 1
        else:
            print(f"✓ Query {i+1} succeeded | TPS: {result.get('tps', 0):.2f}")
            successful_queries += 1
            total_tps += result.get('tps', 0)
        
        if i < num_queries - 1:  # Don't sleep after the last query
            time.sleep(delay)
    
    # Summary
    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)
    print(f"Total queries: {num_queries}")
    print(f"Successful: {successful_queries}")
    print(f"Failed: {failed_queries}")
    if successful_queries > 0:
        avg_tps = total_tps / successful_queries
        print(f"Average TPS: {avg_tps:.2f}")
    print("="*60 + "\n")
    
    return {
        "total": num_queries,
        "successful": successful_queries,
        "failed": failed_queries,
        "avg_tps": total_tps / successful_queries if successful_queries > 0 else 0
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "benchmark":
        # Run benchmark mode
        num_queries = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        result = run_benchmark(num_queries)
        sys.exit(0 if result['failed'] == 0 else 1)
    else:
        # Run single query
        result = query()
        
        if "error" in result:
            sys.exit(1)
        else:
            print(f"Test completed successfully | TPS: {result.get('tps', 0):.2f}")
            sys.exit(0)
