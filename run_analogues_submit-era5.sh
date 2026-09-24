#!/bin/bash
#SBATCH --output=logs/%x.out
#SBATCH --error=logs/%x.err
#SBATCH --account=canari
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --time=10:00


# Load necessary modules
module load jaspy/3.12/v20250704

# Get CASE and SETTING from command line
CASE=$1
SETTING=$2




# Print info

echo "CASE=$CASE"
echo "SETTING=$SETTING"


# Run application
python -u <<EOF
from run_analogues import run_analogues
run_analogues('$CASE', 'ERA5', '$SETTING')
EOF
