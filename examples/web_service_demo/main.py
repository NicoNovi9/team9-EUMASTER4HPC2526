from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/testinAPI", response_class=HTMLResponse)
def read_root():
    html_content = super_fancy_content

    return html_content


super_fancy_content=""" <html>
  <head>
    <title>Benvenuto/a su Meluxina!</title>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;600&display=swap');
      body {
        margin: 0;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        height: 100vh;
        display: flex;
        justify-content: center;
        align-items: center;
        text-align: center;
        flex-direction: column;
      }
      h1 {
        font-size: 4rem;
        margin-bottom: 0.2em;
        text-shadow: 2px 2px 8px rgba(0,0,0,0.2);
      }
      p {
        font-size: 1.5rem;
        max-width: 600px;
        margin: 0 auto;
        text-shadow: 1px 1px 5px rgba(0,0,0,0.1);
      }
      .flag {
        font-size: 3rem;
        margin-top: 0.5em;
        animation: bounce 2s infinite;
      }
      @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-20px); }
      }
      .button {
        margin-top: 2em;
        background: #ff6f61;
        border: none;
        color: white;
        font-weight: 600;
        padding: 15px 40px;
        font-size: 1.2rem;
        border-radius: 30px;
        cursor: pointer;
        box-shadow: 0 6px 12px rgba(255,111,97,0.4);
        transition: background 0.3s ease;
      }
      .button:hover {
        background: #ff3b2e;
      }
    </style>
  </head>
  <body>
    <h1>Ciao Meluxa!! <span class="flag">🇪🇺✨</span></h1>
    <p>Benvenuto nell’esperienza FastAPI super stilosa di Meluxina. Preparati a scoprire cosa l’High Performance Computing può fare per te!</p>
    <button class="button" onclick="alert('Sei pronto a iniziare?')">Inizia ora 🚀</button>
  </body>
</html>
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import platform
import psutil
import subprocess

app = FastAPI(title="Hardware Info Service")


def gpu_info():
    """
    Ritorna informazioni sulla GPU se disponibile:
    - NVIDIA: usa nvidia-smi
    - AMD ROCm: prova rocminfo
    """
    gpus = []
    try:
        # Prova NVIDIA
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        if out:
            for line in out.splitlines():
                name, mem, driver = [x.strip() for x in line.split(",")]
                gpus.append({"vendor": "NVIDIA", "name": name, "memory": mem, "driver": driver})
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    if not gpus:
        # Prova AMD
        try:
            out = subprocess.check_output(["rocminfo"], stderr=subprocess.DEVNULL).decode().strip()
            if out:
                gpus.append({"vendor": "AMD/ROCm", "info": "rocminfo output detected"})
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    return gpus


@app.get("/hardware")
def hardware_info():
    """
    Restituisce info su:
    - Sistema operativo
    - CPU (nome, core)
    - Memoria totale
    - GPU (se presente)
    """
    info = {
        "system": {
            "os": platform.system(),
            "os_version": platform.version(),
            "kernel": platform.release(),
            "machine": platform.machine(),
        },
        "cpu": {
            "model": platform.processor() or "unknown",
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
        },
        "memory": {
            "total_gb": round(psutil.virtual_memory().total / (1024**3), 2)
        },
        "gpu": gpu_info(),
    }
    return JSONResponse(info)
