import json
import subprocess
import ollamaService
import qdrantService


"""
Daniele and Nicola will take care of this file, if needed (eg, adding another service for I/O).

"""

def handle_service_request(data):

    ollamaService.setup_ollama(data)
   # qdrantService.setup_qdrant(data) # retrieval service
   # ... add more services if needed eg I/O, this can be an extension point...