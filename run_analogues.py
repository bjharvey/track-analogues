"""Routines for computing analogues from ERA5 and CANARI-LE tracks"""

from pathlib import Path
import yaml

from track_utils import \
    load_single_era5_track, \
    load_tracks, \
    save_tracks, \
    find_analogues

output_dir = Path('/home/users/bjharvey/workspaces/medcyclones/track-analogues/')
track_dir = Path('/gws/ssde/j25b/cmip6_track/CANARI')

# Define cases and their ERA5 trackids
with open('cases.yml') as f:
    cases = yaml.safe_load(f)

# Define choice of settings passed to find_analogues
with open('analogue_settings.yml') as f:
    settings = yaml.safe_load(f)


def rm_file(filepath):
    """
    Remove a Pathlib file with check it is a file.
    (e.g. instead of a directory)
    """
    if filepath.is_file():
        print(f'RM_FILE: Removing existing file\n{filepath}')
        filepath.unlink()


def compute_analogues(case, label, setting, flist):
    """
    Run find_analogues over a set of track files for a single case.

    case: a key of cases defining the target_track
    label: name to use for analogue track files (specific to case and member)
    settings: a key of settings defining the inputs to find_analogues
    flist: list of netcdf track files to search in
    """
    print(f'\nCOMPUTE_ANALOGUES: Finding analogues for storm '
          f'{case} in dataset {label}')
    print(cases[case])

    # Construct filenames and remove any existing analogue files
    data_dir = output_dir / 'data' / f'{case}'
    savefn_candidates = data_dir / f'{label}_{case}_candidates_{setting}.nc'
    savefn_analogues = data_dir / f'{label}_{case}_analogues_{setting}.nc'
    rm_file(savefn_candidates)
    rm_file(savefn_analogues)

    # Load target track
    target_track = load_single_era5_track(
        cases[case]['date'],
        cases[case]['trackid'],
        trackvar=cases[case]['trackvar']
    )

    # Loop over files and search for candidates and analogues in each
    candidate_tracks = {}
    analogue_tracks = {}
    for filename in flist:
        tracks = load_tracks(
            filename,
            subset_dates=True,
            verbose=True,
            add_filename_to_key=True
        )
        ct, at, counts = find_analogues(
            target_track,
            tracks,
            **settings[setting],
            verbose=True
        )
        candidate_tracks.update(ct)
        analogue_tracks.update(at)

    # Save
    save_tracks(candidate_tracks, savefn_candidates)
    save_tracks(analogue_tracks, savefn_analogues)


def reload_analogues(case, label, setting, get_candidates=False):
    """
    Reload precomputed analogue (or candidate) tracks from compute_analogues.

    Wildcards allowed in label to allow for reloading multiple files
    (e.g. all members)

    Returns: {label: {track_id: track}}
    """
    data_dir = output_dir / 'data' / f'{case}'
    if get_candidates:
        savefn = data_dir.glob(f'{label}_{case}_candidates_{setting}.nc')
    else:
        savefn = data_dir.glob(f'{label}_{case}_analogues_{setting}.nc')
    tracks = {fn.name.split('_')[0]: load_tracks(fn) for fn in savefn}
    nfiles = len(tracks)
    ntracks = sum([len(v) for k, v in tracks.items()])
    print(f'RELOAD_ANALOGUES({case}, {label}, {setting}, '
          f'{'candidates' if get_candidates else 'analogues'}): '
          f'Loaded {nfiles} files, {ntracks} tracks')
    return tracks


def run_analogues(case, label, setting):
    """
    Run compute_analogues over a single case and .

    case: a key of cases defining the target_track
    label: One of ERA5, PRESENTm<ens>, FUTUREm<ens>
    settings: a key of settings defining the inputs to find_analogues
    """
    print(f'RUN_ANALOGUES: {case}, {label}, {setting}')
    trackvar = cases[case]['trackvar']
    addwindlev = trackvar.strip('vor')

    def collect_files(base_dir, patterns):
        print(f'Looking for files in {base_dir}')
        files = []
        b = Path(base_dir)
        for pat in patterns:
            print(f'-- Matching {pat}')
            newfiles = list(b.glob(pat))
            print(f'-- Found {len(newfiles)} files')
            files += newfiles
        print(f'Found {len(files)} files in total')
        return sorted(files)

    if label == 'ERA5':
        # ERA5 (mar-oct1950 to sep-apr19992000 [50 complete years])
        era5_dir = track_dir / 'ERA5' / 'ST'
        era5_pat = [
            f'ERA5_6hr_{trackvar}_{datestr}_DET/'
            f'ff_trs_pos.addwind{addwindlev}_addwind10m_'
            f'addmslp_addprecip.new.nc'
            for datestr in ['mar-oct19[5-9][0-9]', 'sep-apr19[5-9][0-9]????']
        ]
        files = collect_files(era5_dir, era5_pat)

    elif 'PRESENT' in label:
        mem = label.split('m')[-1]
        # CANARI Present (mar-oct1950 to sep-apr19992000 [50 complete years])
        pres_dir = track_dir / 'HIST' / 'ST'
        pres_pat = [
            f'?????a/{mem}/?????a_{mem}_{trackvar}_{datestr}/'
            f'ff_trs_pos.addwind{addwindlev}_addwind10m_'
            f'addmslp_addprec.new.nc'
            for datestr in ['mar-oct19[5-9][0-9]', 'sep-apr19[5-9][0-9]????']
        ]
        files = collect_files(pres_dir, pres_pat)

    elif 'FUTURE' in label:
        mem = label.split('m')[-1]
        # CANARI Future (mar-oct2050 to sep-apr20992100 [50 complete years])
        fut_dir = track_dir / 'SSP370' / 'ST'
        fut_pat = [
            f'?????a/{mem}/?????a_{mem}_{trackvar}_{datestr}/'
            f'ff_trs_pos.addwind{addwindlev}_addwind10m_'
            f'addmslp_addprec.new.nc'
            for datestr in ['mar-oct20[5-9][0-9]', 'sep-apr20[5-9][0-9]????']
        ]
        files = collect_files(fut_dir, fut_pat)

    compute_analogues(case, label, setting, files)