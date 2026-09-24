#!/bin/bash

# Extract all cutouts for a single case across PRESENT and FUTURE.
# Need to specify:
# -- the case name, CASE (a value from cases.yml)
# -- the settings to use via SETTINGS (a value from settings.yml)
# To inspect current pending/running jobs:
# squeue -u $USER
# To inspect finished jobs:
# fmt="JobID,JobName%50,Partition%10,Account,AllocCPUS,ReqMem,MaxRSS,MaxVMSize,State,Elapsed,ExitCode";
# sacct --format=$fmt --starttime $(date +%Y-%m-%d --date="yesterday")

# CASES=(Arwen GreatStorm Martin Ophelia Eunice NorthSea)
# SETTINGS=vn1-300

# CASES=(Jul2021 Jul2012)
# SETTINGS=cols

# CASES=(Oct2017jr Ciaran)
# SETTINGS=drws

# CASES=(Daniel Apollo Ianos Andrea Julia Vaia)
# SETTINGS=med1
CASES=(Vaia Ianos Daniel)
SETTINGS=(medvaia medianos meddaniel)

# CASES=(Groundhog Franklin Capella DDay)
# SETTINGS=drws


# Convert SETTINGS to an array of length CASES if it is a string
# Means it can be set as a single value applied to all cases
# or an array off different values
if ! declare -p SETTINGS 2>/dev/null | grep -q 'declare -a'; then
    echo Converting SETTINGS to array
    value="$SETTINGS"
    SETTINGS=()
    for _ in "${CASES[@]}"; do
        SETTINGS+=("$value")
    done
fi
if ((${#SETTINGS[@]} != ${#CASES[@]})); then
    echo "ERROR: CASES and SETTINGS have different lengths" >&2
    exit 1
fi

for i in "${!CASES[@]}"; do
    CASE="${CASES[$i]}"
    SETTINGS="${SETTINGS[$i]}"
    jobname=rc-hist_${CASE}_${SETTING}
    echo Submitting $jobname
    sbatch --job-name="$jobname" run_cutouts_submit-hist.sh $CASE $SETTING
    jobname=rc-ssp370_${CASE}_${SETTING}
    echo Submitting $jobname
    sbatch --job-name="$jobname" run_cutouts_submit-ssp370.sh $CASE $SETTING
done