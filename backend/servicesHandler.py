import json
import subprocess
import ollamaService
import qdrantService


"""
Daniele and Nicola will take care of this file, if needed (eg, adding another service for I/O).

"""

def handle_service_request(data):
    
    # Extract service type from workload
    workload = data.get('job', {})
    service_type = workload.get('service', '')
    
    print(f"Service type requested: {service_type}")
    
    if service_type == 'inference':
        # LLM inference service (Ollama)
        ollamaService.setup_ollama(data)
    elif service_type == 'retrieval':
        # Vector retrieval service (Qdrant)
        # qdrantService.setup_qdrant(data)
        print("Retrieval service not yet implemented")
    else:
        print(f"Unknown service type: {service_type}")
        raise ValueError(f"Unsupported service type: {service_type}")
   # ... add more services if needed eg I/O, this can be an extension point...