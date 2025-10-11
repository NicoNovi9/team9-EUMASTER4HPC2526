#!/usr/bin/env python3

import requests
import json
import time
import sys

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

if __name__ == "__main__":
    success = test_client_service()
    sys.exit(0 if success else 1)