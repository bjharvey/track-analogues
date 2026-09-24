#!/bin/bash

# Extract all cutouts for a single case across PRESENT and FUTURE.
# Need to specify:
# -- the case name, CASE (a value from cases.yml)
# -- the settings to use via SETTING (a value from settings.yml)
# To inspect current pending/running jobs:
# squeue -u $USER
# To inspect finished jobs:
# fmt="JobID,JobName%50,Partition%10,Account,AllocCPUS,ReqMem,MaxRSS,MaxVMSize,State,Elapsed,ExitCode";
# sacct --format=$fmt --starttime $(date +%Y-%m-%d --date="yesterday")

# CASES=(Arwen GreatStorm Martin Ophelia Eunice NorthSea)
# SETTING=vn1-300

# CASES=(Jul2021 Jul2012)
# SETTING=cols

# CASES=(Oct2017jr Ciaran)
# SETTING=drws

CASES=(Daniel Apollo Ianos Andrea Julia Vaia)
SETTING=med1
# CASES=(Vaia)
# SETTING=medvaia
# CASES=(Daniel)
# SETTING=meddaniel

# CASES=(Groundhog Franklin Capella DDay)
# SETTING=drws

for CASE in "${CASES[@]}"; do
    jobname=rc-hist_${CASE}_${SETTING}
    sbatch --job-name="$jobname" run_cutouts_submit-hist.sh $CASE $SETTING
    jobname=rc-ssp370_${CASE}_${SETTING}
    sbatch --job-name="$jobname" run_cutouts_submit-ssp370.sh $CASE $SETTING
done