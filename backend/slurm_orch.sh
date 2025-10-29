#!/bin/bash -l

#SBATCH --time=00:05:00
#SBATCH --qos=default
#SBATCH --partition=cpu
#SBATCH --account=p200981
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --ntasks-per-node=32
#SBATCH --output=ollama_service_orch.out
#SBATCH --error=ollama_service_orch.err

module load Python
pip install -r requirements.txt
python -u orch.py recipe_ex/inference_recipe.json 