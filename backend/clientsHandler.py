import json
import subprocess

def generate_clients(clientJSON_data, username):
    num_clients = clientJSON_data.get("n_clients", 1)
    json_str = json.dumps(clientJSON_data)  # Convert Python object to JSON string
    escaped_json_str_JSON_DATA = json_str.replace('"', '\\"')  # Escape double quotes
    print("escaped_json_str_JSON_DATA:", escaped_json_str_JSON_DATA)
    json_params = json.dumps(clientJSON_data)

    client_script_template = f"""#!/bin/bash
#SBATCH --job-name=llm_client_generation
#SBATCH --nodes=1
#SBATCH --ntasks=1   
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4G
#SBATCH --time=00:04:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --output=llm_client_generation.out
#SBATCH --error=llm_client_generation.err

sleep 3
module load Python
python /home/users/{username}/llmClient.py {"\""+escaped_json_str_JSON_DATA+"\""}"""
    

#username will have value "u103038 in case of 'ivanalkhayat' went through in the conn_melux.js,"
    with open("llmClientsGeneration.sh", "w") as f:
        f.write(client_script_template)
    # Submit to SLURM
    for i in range(num_clients):
        result = subprocess.run(["sbatch", "llmClientsGeneration.sh"], capture_output=True, text=True)

        
    print("SLURM submission output:", result.stdout)
    print("SLURM submission error:", result.stderr)

