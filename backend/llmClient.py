
import sys
import json
import subprocess


def getOllamaIpAddress():
    with open("ollama_ip.txt", "r") as f:
        ip = f.read().strip()
    print("Ollama IP Address----->:", ip)

    return ip



"""
example of queryParams:
{'service': 'inference', 'n_clients': 1, 'n_requests_per_client': 10, 'prompt': 'tell me how internet was born?'}
"""
# it must submit requests to the ollama server or servers
if __name__ == "__main__":
    
    print("hello I'm a client!")
    queryParams = sys.argv[1]
    print("queryParams:", queryParams)
    data = json.loads(queryParams)

    n_requests=data['n_requests_per_client'] 

    for i in range(n_requests):
        print(f"Client making request {i+1}/{n_requests} with prompt: {data['prompt']}")
        # Here you would add the code to send the request to the Ollama server


        cmd = [
            "curl", "-s", "-X", "POST", "http://"+getOllamaIpAddress()+":11434/api/generate",
            "-H", "Content-Type: application/json",
            "-d", '{"prompt": "'+data['prompt']+'", "stream": false, "model": "mistral"}'
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("Raw output:\n", result.stdout)

            # Optional: Try to parse as JSON if Ollama returns JSON
            try:
                data = json.loads(result.stdout)
                print("\nParsed JSON:\n", json.dumps(data, indent=2))
            except json.JSONDecodeError:
                print("\nNon-JSON response:\n", result.stdout)

        except subprocess.CalledProcessError as e:
            print(" Ops, something went wrong! Error executing curl:", e)
