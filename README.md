# Track Analogues

Code for identifying and analysing analogue cyclone tracks from the CANARI-LE.

## Installation

Clone the repository:

1. `git clone https://github.com/bjharvey/track-analogues.git`
2. `cd track-analogues`

Create the environment:

1. Currently running under the latest jaspy: `module load jaspy/3.12/v20250704`

## Configuration

Edit `run_analogues.py` to set `output_dir` to where you want to save to.

## Running

1. Use `locate_tracks.ipynb` to locate track ID of observed case in ERA5 and add to `cases.yml`
2. Decide on the analogues settings (i.e. inputs to find_analogues) to use and add to `analogues_settings.yaml`
3. Run `run_analogues_submit-wrapper.sh` in batch from a terminal to search for analogues
   - Must set CASES and SETTINGS variables
   - This calls routines from `run_analogues.py` to search for analogues in ERA5, HIST and SSP370
4. Use `plot_analogues.ipynb` to analyse the statistics of the analogue tracks
5. Run `run_cutouts_submit-wrapper.sh` in batch from a terminal to extract cutouts
   - Must set CASES and SETTINGS variables
   - This calls routines from `run_cutouts.py` to search for analogues in HIST and SSP370
6. Use `plot_cutouts.ipynb` to examine the cutouts

## Input data

Access is required to these locations:
* `/gws/ssde/j25b/cmip6_track/CANARI` for the ERA5 and CANARI-LE track files
* `/gws/ssde/j25b/canari/shared/large-ensemble/priority` for the large ensemble priority outputs
