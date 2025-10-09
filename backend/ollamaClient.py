import json
import subprocess
import os

class OllamaClient:
    def __init__(self, host=None, port=11434, model="llama2"):
        self.host = host or self._get_ollama_ip()
        self.port = port
        self.model = model
    
    def _get_ollama_ip(self):
        try:
            # Prima prova il nuovo percorso in backend
            with open("output/ollama_ip.txt", "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            try:
                # Fallback al vecchio percorso per compatibilità
                with open(os.path.expanduser("~/ollama_ip.txt"), "r") as f:
                    return f.read().strip()
            except FileNotFoundError:
                return "localhost"
    
    def query(self, prompt):
        url = f"http://{self.host}:{self.port}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        
        cmd = ["curl", "-s", "-X", "POST", url, "-H", "Content-Type: application/json", "-d", json.dumps(payload)]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except:
            pass
        return None
    
    def test_connection(self):
        response = self.query("Hello")
        return response is not None