#!/bin/bash -l

#SBATCH --time=01:00:00
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

# Clean previous output directory
if [ -d "output" ]; then
    echo "Removing existing output directory..."
    rm -rf output
fi

python -u orch.py recipe_ex/inference_recipe.json "$@"