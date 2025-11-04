#!/usr/bin/env python3

import requests
import sys
import os
import glob


def _load_pushgateway_ip():
    """Load Pushgateway IP from file"""
    try:
        with open("output/pushgateway_data/pushgateway_ip.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def _calculate_tokens(response_data):
    """Calculate token count from response"""
    if 'eval_count' in response_data:
        return response_data['eval_count']
    elif 'prompt_eval_count' in response_data:
        return response_data['prompt_eval_count']
    elif 'response' in response_data:
        return len(response_data['response'].split())
    return 0


def _push_to_pushgateway(tps, model, client_id, pushgateway_ip):
    """Push TPS metric to Pushgateway"""
    if not pushgateway_ip:
        return
    
    metric_data = f"""# TYPE tokens_per_second gauge
tokens_per_second{{client_id="{client_id}",model="{model}"}} {tps}
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
            print(f"  ✓ Pushed TPS={tps:.2f} to Pushgateway")
    except Exception as e:
        print(f"  Pushgateway push failed: {e}")


def run_benchmark(num_queries=30, model="llama2"):
    """Run parallel benchmark via client service"""
    print(f"\nPARALLEL BENCHMARK: {num_queries} queries\n")
    
    try:
        # Load client service IP
        client_files = sorted(glob.glob('output/client_ip_*.txt'), key=lambda x: x, reverse=True)
        if not client_files:
            raise FileNotFoundError("No client_ip_*.txt found. Is client service running?")
        
        with open(client_files[0], 'r') as f:
            client_ip = f.read().strip()
        
        url = f"http://{client_ip}:5000/benchmark"
        payload = {"num_queries": num_queries, "model": model, "parallel": True}
        
        print(f"Sending request to {url}...")
        response = requests.post(url, json=payload, timeout=600)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        result = response.json()
        
        # Calculate tokens and TPS for each result, push to Pushgateway
        pushgateway_ip = _load_pushgateway_ip()
        total_tokens = 0
        total_tps = 0
        successful_with_response = 0
        
        if 'results' in result:
            for i, query_result in enumerate(result['results']):
                if 'error' not in query_result and 'response' in query_result:
                    num_tokens = _calculate_tokens(query_result)
                    elapsed = query_result.get('request_time', 0)
                    tps = num_tokens / elapsed if elapsed > 0 else 0
                    
                    total_tokens += num_tokens
                    total_tps += tps
                    successful_with_response += 1
                    
                    # Push to Pushgateway
                    client_id = f"benchmark_query_{i}"
                    _push_to_pushgateway(tps, model, client_id, pushgateway_ip)
        
        avg_tps = total_tps / successful_with_response if successful_with_response > 0 else 0
        
        print("\n" + "="*60)
        print("BENCHMARK RESULTS")
        print("="*60)
        print(f"Total queries:    {result['total_queries']}")
        print(f"Successful:       {result['successful']}")
        print(f"Failed:           {result['failed']}")
        print(f"Total time:       {result['total_time']:.2f}s")
        print(f"Avg request time: {result['avg_request_time']:.2f}s")
        print(f"Total tokens:     {total_tokens}")
        print(f"Avg TPS:          {avg_tps:.2f}")
        print(f"Queries/sec:      {result['queries_per_second']:.2f}")
        print("="*60 + "\n")
        
        return result
        
    except Exception as e:
        print(f"ERROR: {e}")
        return {"error": str(e), "total": num_queries, "successful": 0, "failed": num_queries}


if __name__ == "__main__":
    num_queries = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    result = run_benchmark(num_queries)
    sys.exit(0 if result.get('failed', 0) == 0 else 1)
