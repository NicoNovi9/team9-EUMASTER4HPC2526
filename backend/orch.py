import sys
import json


import subprocess
import clientsHandler
import servicesHandler

""" This is the main script, server side entry point.
    It is responsible for orchestrating the deployment of the services (Ollama and Qdrant),
    client generation and launch the monitoring script (Prometheus) on Meluxina.
"""

if __name__ == "__main__":
    print("starting the orchestrator python")
    json_str = sys.argv[1]
    data = json.loads(json_str)
    servicesHandler.handle_service_request(data);
    clientsHandler.generate_clients(data['client'], data['username'])




