# 🚀 Avviare un Web Service (con o senza UI) containerizzato con Apptainer

Questa guida illustra come costruire e lanciare un **web service FastAPI** in un container Apptainer su un cluster HPC (ad esempio **Meluxina**).

---

## 1️⃣ Creazione del container

Prepara due file nella stessa directory:

- **`test.def`** – la *recipe* del container  
- **`test.sif`** – l’immagine risultante

Costruisci l’immagine:

```bash
apptainer build test.sif test.def
```

---

## 2️⃣ Contenuto di `test.def`

```def
Bootstrap: docker
From: python:3.10

%environment
    export LC_ALL=C.UTF-8
    export LANG=C.UTF-8

%post
    pip install fastapi prometheus-client uvicorn numpy pandas psutil
    mkdir -p /app

%runscript
    cd /app
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

> ⚠️ **Attenzione**  
> Il flag `--reload` **non va mai usato in produzione**, perché abilita il *live-reload* del codice.

> se è il primo avvio devi buildare il file .sif, con comando
```bash
build test.sif test.def
```

---

## 3️⃣ Allocare una risorsa computazionale

Richiedi un nodo di calcolo (sceg):

```bash
salloc -q default -p gpu --time=01:30:35 -A p200981
```

---

## 4️⃣ Avviare il container

esegui module load Apptainer


Esegui il servizio web montando la tua home in `/app`, ovvero fai come di seguito:

```bash
apptainer run --bind /home/users/u103038:/app test.sif
```

se vuoi che legga le GPU:
```bash
apptainer run --nv --bind /path/to/your/code:/app test.sif
```
---

## 5️⃣ Port Forwarding per l’accesso dal browser

Apri **due terminali** sul tuo computer locale:

### 🔹 Terminale 1 – SSH verso il *login node*

Mantieni attivo il tunnel dal tuo Mac al login node:

```bash
ssh -L 8000:localhost:8000 -p 8822 u103038@login.lxp.lu
```
poi:
```bash
ssh mel2066
```
attenzione: in questo caso mel2066 è il nodo computazionale che hai ottenuto durante il salloc.
### 🔹 Terminale 2 – SSH verso il *compute node*

All’interno della sessione del login node, apri un secondo tunnel verso il compute node che esegue il container:
```bash
ssh meluxina
```
poi:
```bash
ssh -L 8000:localhost:8000 mel2066
```

> Questo crea un doppio forwarding della porta **8000** fino al compute node.

---

## 6️⃣ Accesso al servizio web

Sul tuo browser locale apri:

```
http://localhost:8000
```

Il traffico verrà tunnelizzato attraverso entrambe le connessioni SSH fino al web service FastAPI.

---

## 7️⃣ File `main.py` di esempio

Assicurati che, nella stessa cartella di `test.sif`, ci sia un file `main.py`:

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/testinAPI", response_class=HTMLResponse)
def read_root():
    html_content = super_fancy_content
    return html_content

super_fancy_content = """ 
<html>
  <head>
    <title>Benvenuto/a su Meluxina!</title>
  </head>
  <body>
    <h1>Hello world! Questo può anche essere un JSON object;
    rimuovendo 'response_class' ottieni un vero REST web service.</h1>
  </body>
</html>
"""
```
se richiami il servizio /hardware ottieni su quali risorse sta girano il webService.


---

✅ **Risultato finale**  
Un web service FastAPI accessibile via browser attraverso un doppio tunnel SSH, completamente containerizzato con **Apptainer**.
