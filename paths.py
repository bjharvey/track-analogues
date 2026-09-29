"""Shared filesystem paths."""

from pathlib import Path
import yaml

# Source data
track_dir = Path('/gws/ssde/j25b/cmip6_track/CANARI')
priority_dir = Path('/gws/ssde/j25b/canari/shared/large-ensemble/priority')

# Output locations for data and plots
output_dir = Path('/home/users/bjharvey/workspaces/medcyclones/track-analogues/')
data_dir = output_dir / 'data'
plot_dir = output_dir / 'plots'
data_dir.mkdir(parents=True, exist_ok=True)
plot_dir.mkdir(parents=True, exist_ok=True)

# Load cases and settings from YAML files
project_dir = Path(__file__).resolve().parent
with open(project_dir / 'cases.yml') as f:
    cases = yaml.safe_load(f)
with open(project_dir / 'analogue_settings.yml') as f:
    settings = yaml.safe_load(f)


def rm_file(filepath: Path) -> None:
    """
    Remove a Pathlib file with check it is a file.
    (e.g. instead of a directory)
    """
    if filepath.is_file():
        print(f'RM_FILE: Removing existing file\n{filepath}')
        filepath.unlink()