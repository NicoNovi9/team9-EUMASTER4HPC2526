import json
import subprocess
import os

class OllamaClient:
    def __init__(self, host=None, port=11434, model="mistral"):
        """
        Semplice client per interrogare Ollama
        
        Args:
            host: IP del server Ollama (se None, legge da ollama_ip.txt)
            port: Porta del server Ollama (default 11434)
            model: Modello da usare (default mistral)
        """
        self.host = host
        self.port = port
        self.model = model
        
        # Se host non specificato, prova a leggerlo dal file
        if self.host is None:
            self.host = self._get_ollama_ip()
    
    def _get_ollama_ip(self):
        """Legge l'IP di Ollama dal file salvato dal servizio"""
        try:
            ollama_ip_path = os.path.expanduser("~/ollama_ip.txt")
            with open(ollama_ip_path, "r") as f:
                ip = f.read().strip()
            print(f"Ollama IP trovato: {ip}")
            return ip
        except FileNotFoundError:
            print("File ollama_ip.txt non trovato, uso localhost")
            return "localhost"
    
    def query(self, prompt, stream=False):
        """
        Invia una query a Ollama
        
        Args:
            prompt: Il prompt da inviare
            stream: Se True, streaming response (default False)
            
        Returns:
            dict: Risposta di Ollama o None se errore
        """
        url = f"http://{self.host}:{self.port}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream
        }
        
        cmd = [
            "curl", "-s", "-X", "POST", url,
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload)
        ]
        
        try:
            print(f"Interrogando Ollama: {self.model} @ {self.host}:{self.port}")
            print(f"Prompt: {prompt[:50]}...")
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    print(f"Risposta ricevuta: {len(response.get('response', ''))} caratteri")
                    return response
                except json.JSONDecodeError:
                    print(f"Errore parsing JSON: {result.stdout}")
                    return None
            else:
                print(f"Errore curl: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Errore durante la query: {e}")
            return None
    
    def test_connection(self):
        """Test semplice per vedere se Ollama risponde"""
        print(f"Testing connessione a Ollama {self.host}:{self.port}...")
        response = self.query("Hello", stream=False)
        
        if response:
            print("✅ Connessione OK!")
            return True
        else:
            print("❌ Connessione fallita!")
            return False


# Esempio di utilizzo
if __name__ == "__main__":
    # Crea client
    client = OllamaClient(model="mistral")
    
    # Test connessione
    if client.test_connection():
        # Esempio di query
        response = client.query("What is artificial intelligence?")
        
        if response:
            print("\n" + "="*50)
            print("RISPOSTA OLLAMA:")
            print("="*50)
            print(response.get('response', 'Nessuna risposta'))
            print("="*50)