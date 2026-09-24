#!/bin/bash
#SBATCH --output=logs/%x_%3a.out
#SBATCH --error=logs/%x_%3a.err
#SBATCH --account=canari
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --time=10:00
#SBATCH --array=1-40  # nmems

# Load necessary modules
module load jaspy/3.12/v20250704

# Get CASE and SETTING from command line
CASE=$1
SETTING=$2

# Use slurm array for different members
MEM=$((SLURM_ARRAY_TASK_ID))

# Print info
echo "Task $SLURM_ARRAY_TASK_ID"
echo "CASE=$CASE"
echo "SETTING=$SETTING"
echo "MEM=$MEM"

# Run application
python -u <<EOF
from run_cutouts import run_cutouts
run_cutouts('$CASE', 'FUTUREm${MEM}', '$SETTING')
EOF
