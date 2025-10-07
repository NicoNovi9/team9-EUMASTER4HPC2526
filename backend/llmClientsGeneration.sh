#!/bin/bash
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
python $HOME/llmClient.py "{\"n_clients\": 32, \"test_duration\": 60, \"request_rate\": 10}"
