import json
import subprocess
import ollamaService
import qdrantService
from client import clientServiceHandler

"""
Main service dispatcher that delegates to service-specific handlers.
"""

def handle_service_request(data):
    
    # Extract service type from new structure
    job = data.get('job', {})  
    service = job.get('service', {})
    service_type = service.get('type', '')
    
    print(f"Service type requested: {service_type}")
    
    if service_type == 'inference':
        # Deploy Ollama service
        ollamaService.setup_ollama(data)
        
    elif service_type == 'retrieval':
        # Vector retrieval service (Qdrant)
        # qdrantService.setup_qdrant(data)
        print("Retrieval service not yet implemented")
    else:
        print(f"Unknown service type: {service_type}")
        raise ValueError(f"Unsupported service type: {service_type}")
   # ... add more services if needed eg I/O, this can be an extension point...