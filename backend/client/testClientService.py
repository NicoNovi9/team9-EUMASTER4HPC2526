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


def run_benchmark(n_clients=1, n_requests_per_client=5, model="llama2"):
    """Run parallel benchmark via client service
    
    Args:
        n_clients: Number of parallel clients to simulate
        n_requests_per_client: Number of requests each client makes
        model: Model name to use
    """
    total_queries = n_clients * n_requests_per_client
    print(f"\nPARALLEL BENCHMARK")
    print(f"  Clients: {n_clients}")
    print(f"  Requests per client: {n_requests_per_client}")
    print(f"  Total queries: {total_queries}\n")
    
    try:
        # Load client service IP
        client_files = sorted(glob.glob('output/client_ip_*.txt'), key=lambda x: x, reverse=True)
        if not client_files:
            raise FileNotFoundError("No client_ip_*.txt found. Is client service running?")
        
        with open(client_files[0], 'r') as f:
            client_ip = f.read().strip()
        
        url = f"http://{client_ip}:5000/benchmark"
        payload = {
            "n_clients": n_clients,
            "n_requests_per_client": n_requests_per_client,
            "model": model
        }
        
        print(f"Sending benchmark request to {url}...")
        print(f"Server will run {n_clients} clients in parallel\n")
        
        # Single request to server - server handles the parallelism
        response = requests.post(url, json=payload, timeout=600)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        result = response.json()
        
        # Process results and push to Pushgateway
        pushgateway_ip = _load_pushgateway_ip()
        total_tokens = 0
        total_tps = 0
        all_request_times = []
        
        if 'results' in result:
            for query_result in result['results']:
                if 'error' not in query_result and 'response' in query_result:
                    num_tokens = _calculate_tokens(query_result)
                    elapsed = query_result.get('request_time', 0)
                    tps = num_tokens / elapsed if elapsed > 0 else 0
                    
                    total_tokens += num_tokens
                    total_tps += tps
                    all_request_times.append(elapsed)
                    
                    # Push to Pushgateway
                    client_id = query_result.get('client_id', 0)
                    request_id = query_result.get('request_id', 0)
                    _push_to_pushgateway(tps, model, f"client_{client_id}_req_{request_id}", pushgateway_ip)
        
        avg_tps = total_tps / len(all_request_times) if all_request_times else 0
        
        print("\n" + "="*60)
        print("BENCHMARK RESULTS")
        print("="*60)
        print(f"Clients:          {result.get('n_clients', n_clients)}")
        print(f"Requests/client:  {result.get('n_requests_per_client', n_requests_per_client)}")
        print(f"Total queries:    {result.get('total_queries', total_queries)}")
        print(f"Successful:       {result.get('successful', 0)}")
        print(f"Failed:           {result.get('failed', 0)}")
        print(f"Total time:       {result.get('total_time', 0):.2f}s")
        print(f"Avg request time: {result.get('avg_request_time', 0):.2f}s")
        print(f"Total tokens:     {total_tokens}")
        print(f"Avg TPS:          {avg_tps:.2f}")
        print(f"Throughput:       {result.get('queries_per_second', 0):.2f} queries/sec")
        print("="*60 + "\n")
        
        return result
        
    except Exception as e:
        print(f"ERROR: {e}")
        total_queries = n_clients * n_requests_per_client
        return {"error": str(e), "total": total_queries, "successful": 0, "failed": total_queries}


if __name__ == "__main__":
    n_clients = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    n_requests = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    model = sys.argv[3] if len(sys.argv) > 3 else "llama2"
    
    result = run_benchmark(n_clients, n_requests, model)
    sys.exit(0 if result.get('failed', 0) == 0 else 1)
