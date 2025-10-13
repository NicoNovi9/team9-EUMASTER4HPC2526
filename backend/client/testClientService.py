#!/usr/bin/env python3
"""
Simplified test script for client service
"""
import requests
import sys
from pathlib import Path

def get_client_url():
    """Get client service URL"""
    try:
        ip = Path("output/client_ip.txt").read_text().strip()
        return f"http://{ip}:5000"
    except FileNotFoundError:
        print("✗ Error: client_ip.txt not found. Is the service running?")
        sys.exit(1)

def test_endpoint(name, method, endpoint, **kwargs):
    """Generic endpoint test"""
    print(f"\n{name}...")
    try:
        response = requests.request(method, endpoint, timeout=30, **kwargs)
        data = response.json()
        
        if response.status_code == 200:
            print(f"✓ Success")
            if 'response' in data:
                print(f"  Response: {data['response'][:100]}...")
                print(f"  Time: {data.get('request_time', 0):.2f}s")
            else:
                print(f"  Data: {data}")
            return True
        else:
            print(f"✗ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    base_url = get_client_url()
    print(f"Testing client service at: {base_url}")
    
    # Test 1: Health check
    result1 = test_endpoint("Health check", "GET", f"{base_url}/health")
    
    # Test 2: Query test
    result2 = test_endpoint(
        "Query test", 
        "POST", 
        f"{base_url}/query",
        json={"prompt": "What is AI? Answer in 2 sentences.", "model": "mistral"}
    )
    
    if result1 and result2:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())