"""
Useful track functions shared across notebooks.

Approach used: Load Kevin's netcdf track files into an xarray data set
"""

import numpy as np
import datetime
import cftime
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature


"""
Some general functions
"""


def wrap_lons(lon_array):
    """Convert an array of longitudes from 0to360 to -180to180."""
    return ((lon_array + 180) % 360) - 180


def decode_360_time(value):
    """
    Convert a number in YYYYMMDD.X with X decimal fraction of day
    invert a cftime.Datetime360Day object.
    """
    date = int(value)
    fraction = value - date
    year = date // 10000
    month = (date % 10000) // 100
    day = date % 100
    hour = round(fraction * 24)
    return cftime.Datetime360Day(year, month, day, hour)


def encode_360_time(year, month, day, hour=0):
    """
    Convert to YYYYMMDD.X format.
    """
    return year * 10000 + month * 100 + day + hour / 24


def haversine_np(lon1, lat1, lon2, lat2):
    """Vectorized great-circle distance (km)."""
    R = 6371.0
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2.0)**2
    return 2*R*np.arcsin(np.sqrt(a))


def extract_track(ds, track_id, verbose=False):
    """Extract a single track from an xarray dataset."""
    if verbose:
        print(f'Extracting TRACKID {track_id}')
    trackidx = np.where(ds['TRACK_ID'].values == track_id)[0][0]
    sl = slice(
        ds['FIRST_PT'].values[trackidx],
        ds['FIRST_PT'].values[trackidx] + ds['NUM_PTS'].values[trackidx]
    )
    ds = ds.isel(record=sl).drop_dims("tracks")
    return ds


def _get_lonslats(track):
    """Extract longitude and latitude values from a single track."""
    return wrap_lons(track['longitude'].values), track['latitude'].values


def _get_track_segment(track, seg_len_before, seg_len_after, selection_time,
                       **kwargs):
    """
    Extract the segment of a track surrounding the time of max intensity.

    track (xarray.Dataset): The track
    seg_len_before (int)  : Number of timesteps before max intensity to include
    seg_len_after (int)   : Number of timesteps after max intensity to include
    selection_time (str)  : Choice of max intensity ('max_RV' or 'min_MSLP')
    kwargs                : Not used (allows passing of settings dict)

    Raises ValueError if insufficient points before/after max intensity.
    """
    # Get id of target time (will fail if all NaNs)
    if selection_time == "min_MSLP":
        idx = int(np.nanargmin(track["air_pressure_at_sea_level"].values))
    elif selection_time == "max_RV":
        idx = int(np.nanargmax(track["relative_vorticity"].values))
    # Check against seg_lens
    if idx < seg_len_before:
        raise ValueError(f"Need at least {seg_len_before} "
                         f"points before target")
    elif idx > track.sizes['record'] - seg_len_after - 1:
        raise ValueError(f"Need at least {seg_len_after} "
                         f"points after target")
    sl = slice(idx - seg_len_before, idx + seg_len_after + 1)
    return track.isel(record=sl)


"""
Load/Save/Plot tracks
"""


def load_tracks(
    filename,
    subset_dates=False,
    verbose=True,
    add_filename_to_key=False
):
    """
    Load all tracks from an nc track file and put into a dictionary.

    filename (str)     : File to load.
    subset_dates (bool): If True, restrict load to tracks with max intensity
                         falling in a 6 month period to avoid duplicate tracks
                         (see comments for details).
    verbose (bool)     : Print some extra detail for debugging.
    add_filename_to_key (bool): If False, the dictionary keys are just the
                         TRACK_ID. If True, append hte whole filename to this
                         as a quick way of avoiding duplpicate keys when
                         combining multiple files.

    Note (Sep 2026): The CANARI track nc files have been updated to
    have better calendar information:
        ERA5 is gregorian and time values loaded as np.datetime64
        CANARI is 360_day and time values loaded as YYYYMMDD.X with X
            decimal fraction of day (not cf-compliant though?)
    """
    if verbose:
        print(f'LOAD_TRACKS: Loading file {filename}')

    # Load file and massage dates if required
    ds = xr.open_dataset(filename)

    if subset_dates:
        # Assume filename contains one of
        #   mar-octYYYY --> subset to tracks with max in apr-sepYYYY
        #   sep-aprYYYYZZZZ -> subset to tracks with max in octYYYY-marZZZZ
        # Note: Need to handle ERA5 and CANARI differently due to different
        # calendars
        calendar = ds.time.time_calendar.strip()
        if 'mar-oct' in str(filename):
            year = int(str(filename).split('mar-oct')[1][:4])
            if calendar == 'gregorian':
                daterange = [np.datetime64(datetime.datetime(year,  4, 1)),
                             np.datetime64(datetime.datetime(year, 10, 1))]
            elif calendar == '360_day':
                daterange = [encode_360_time(year,  4, 1),
                             encode_360_time(year, 10, 1)]
        elif 'sep-apr' in str(filename):
            year = int(str(filename).split('sep-apr')[1][:4])
            if calendar == 'gregorian':
                daterange = [np.datetime64(datetime.datetime(year,  10, 1)),
                             np.datetime64(datetime.datetime(year+1, 4, 1))]
            elif calendar == '360_day':
                daterange = [encode_360_time(year,  10, 1),
                             encode_360_time(year+1, 4, 1)]
        else:
            raise ValueError('Cannot extract daterange from file:', filename)
        if verbose:
            print(f'LOAD_TRACKS: Subsetting to max intensity in {daterange}')

    tracks = {}
    counts = {'not_in_daterange': 0}
    for track_id in ds['TRACK_ID'].values:
        track = extract_track(ds, track_id).load()
        if subset_dates:
            idx = int(np.nanargmax(track["relative_vorticity"].values))
            time = track['time'].values[idx]
            if (time < daterange[0]) | (daterange[1] <= time):
                counts['not_in_daterange'] += 1
                continue
        key = f'{track_id}'
        if add_filename_to_key:
            key = f'{filename}_' + key
        tracks[key] = track
    if verbose:
        print(f'LOAD_TRACKS: Found {len(tracks)} tracks')
        if counts['not_in_daterange']:
            print(f'Omitted tracks: {counts}')
    ds.close()
    return tracks


def save_tracks(
    tracks,
    filename
):
    """
    Reverse of load_tracks.

    Take a dictionary of tracks, concatenate back to a single dataset
    and save using ds.to_netcdf.
    """
    track_ids = list(tracks.keys())
    if len(track_ids) == 0:
        print(f'No tracks found, not saving file: {filename}')
        return

    # Concatenate records
    ds = xr.concat([tracks[tid] for tid in track_ids], dim="record")

    # Rebuild indexing
    num_pts = np.array([tracks[tid].sizes["record"] for tid in track_ids])
    first_pt = np.zeros(len(num_pts), dtype=int)
    first_pt[1:] = np.cumsum(num_pts[:-1])

    # Add track variables
    ds["FIRST_PT"] = xr.DataArray(num_pts * 0 + first_pt, dims="tracks")
    ds["NUM_PTS"] = xr.DataArray(num_pts, dims="tracks")
    ds["TRACK_ID"] = xr.DataArray(track_ids, dims="tracks")

    print(f'Saving file: {filename}')
    filename.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(filename)


def plot_tracks(
    tracks,
    ax=None,
    trackvar='vor850',
    color='blue',
    show_intensity=True,
    label=None
):
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 4), subplot_kw={'projection': ccrs.PlateCarree()})
        ax.coastlines()
        ax.add_feature(cfeature.BORDERS, linewidth=0.5)
        ax.add_feature(cfeature.LAND, facecolor='lightgray')
        first_track = True
    else:
        first_track = False
    if label is None:
        label = f'{trackvar.upper()} track'
    else:
        first_track = True

    for track_id, track in tracks.items():
        lons, lats = _get_lonslats(track)

        # Line for trajectory
        ax.plot(
            lons, lats, color=color, linewidth=1,
            transform=ccrs.PlateCarree(),
            label=label if first_track else None
        )

        # Dots for intensity
        if show_intensity:
            if 'vor' in trackvar:
                intensity = track['relative_vorticity'].values
                vmin = 0
                vmax = 8 if trackvar == 'vor850' else 20
                cmap = 'Reds'
                maxinti = np.nanargmax(intensity)
                cbarlab = "T42 Rel. Vort. (10$^5$ s$^{-1}$)"
            elif trackvar == 'mslp':
                intensity = track['air_pressure_at_sea_level_anom'].values
                vmin = 0
                vmax = 10
                cmap = 'Blues'
                maxinti = np.nanargmin(intensity)
                cbarlab = "MSLP anom (hPa)"

            sc = ax.scatter(
                lons, lats, c=intensity, s=10,
                transform=ccrs.PlateCarree(), zorder=3,
                vmin=vmin, vmax=vmax, cmap=cmap
            )
            ax.scatter(
                lons[maxinti], lats[maxinti], edgecolor='k', s=10, marker='o',
                transform=ccrs.PlateCarree(), zorder=10,
                label=f'Max int. {track['time'].values[maxinti]}' if first_track else None
            )

        first_track = False

    # Add colorbar
    if show_intensity:
        cbar = plt.colorbar(sc, ax=ax, orientation='vertical', shrink=0.8, pad=0.05)
        cbar.set_label(cbarlab)
    return ax


def plot_timeseries(
    tracks,
    settings,
    axs=None,
    trackvar='vor850',
    color='blue',
    label=None,
    plotstyle='lines',
    varnames=['relative_vorticity', 'wind_speed_10m', 'precipitation_flux']
):
    nplots = len(varnames)
    if axs is None:
        fig, axs = plt.subplots(nplots, 1, figsize=(6, 3*nplots))
        first_track = True
    else:
        first_track = False
    if label is None:
        label = f'{trackvar.upper()} track'
    else:
        first_track = True

    for ax, varname in zip(axs.flatten(), varnames):

        if plotstyle == 'percentiles':
            values_all = []
            zero_pts = []
            xpts_all = []

        for track_id, track in tracks.items():

            segment = _get_track_segment(track, **settings)
            values = segment[varname].values
            xpts = (segment['time'] - segment['time'][settings['seg_len_before']]) / np.timedelta64(1, 'h')

            if plotstyle == 'lines':
                ax.plot(
                    xpts, values, color=color, linewidth=1,
                    label=label if first_track else None
                )
                first_track = False
            elif plotstyle == 'percentiles':
                values_all.append(values)

        if plotstyle == 'percentiles':
            q5 = np.percentile(np.array(values_all), 5, axis=0)
            q50 = np.percentile(np.array(values_all), 50, axis=0)
            q95 = np.percentile(np.array(values_all), 95, axis=0)
            ax.fill_between(xpts, q5, q95, color=color, alpha=0.5)
            ax.plot(xpts, q50, color=color, label=label)
        ax.set_title(varname, loc='left')

        first_track = False


"""
ERA5-specific functions
"""


def make_era5_track_filename(dt, trackvar='vor850'):
    """
    Construct ERA5 track filename for this datetime.
    Note the track files overlap (sep-apr or mar-oct).
    Choose mar-oct for dates in apr-sep and vice versa.
    """
    md = (dt.month, dt.day)
    if md < (4, 1):
        yrtag = f'sep-apr{dt.year-1}{dt.year}'
    elif (4, 1) <= md < (10, 1):
        yrtag = f'mar-oct{dt.year}'
    else:
        yrtag = f'sep-apr{dt.year}{dt.year+1}'
    if 'vor' in trackvar:
        fdir = f'/gws/ssde/j25b/cmip6_track/CANARI/ERA5/ST/ERA5_6hr_{trackvar}_{yrtag}_DET'
        return f'{fdir}/ff_trs_pos.addwind{trackvar.strip('vor')}_addwind10m_addmslp_addprecip.new.nc'
    elif trackvar == 'mslp':
        fdir = f'/gws/ssde/j25b/cmip6_track/CANARI/ERA5/ST/ERA5_MSLP_{yrtag}_NH'
        return f'{fdir}/ff_trs_neg.addwind925_addwind10m_addmslp.new.nc'


def load_single_era5_track(dt, track_id, trackvar='vor850'):
    """
    Load a single ERA5 track as an xarray dataset.
    dt is the datetime (just used to locate correct file).
    """
    filename = make_era5_track_filename(dt, trackvar)
    print(f'Loading file {filename}')
    ds = xr.open_dataset(filename)
    return extract_track(ds, track_id)


"""
Analogue functions
"""


def find_analogues(
    target_track: xr.Dataset,
    tracks: dict[xr.Dataset],
    seg_len_before: int = 4,
    seg_len_after: int = 4,
    selection_time: str = 'max_RV',
    candidate_distance: float = 300.0,
    analogue_distance: float = 500.0,
    analogue_function: str = 'mean',
    filter_mslp: float | None = None,
    filter_rv: float | None = None,
    verbose=True,
):
    """
    Find candidates and anologues of target_track in tracks.

    seg_len_before/after: Number of track points to include in matching segment
    selection_time: Time to centre matching on ('max_RV' or 'min_MSLP')
    candidate_distance: Max candidate distance at selection_time.
    analogue_distance: Max analogue distance along track segment.
    analogue_function: Define analogue distance as segemnt mean or segment max ('mean' or 'max')
    filter_mslp/rv: Subset to tracks exceeding intensity threshold.
    """

    if verbose:
        print('Running FIND_ANALOGUES')
        print(f'Input tracks: {len(tracks)}')

    # 1) Get coordinates of target track segment
    target_segment = _get_track_segment(
        target_track, seg_len_before, seg_len_after, selection_time
    )
    target_lonslats = _get_lonslats(target_segment)
    if verbose:
        print(f'Target segment: {target_lonslats}')

    # 2) Filter to candidate and analogue tracks
    candidate_tracks = {}
    analogue_tracks = {}
    counts = {
        'segment_not_available': 0,
        'filter_mslp': 0,
        'filter_rv': 0,
        'candidate_test': 0,
        'analogue_test': 0,
    }
    for track_id, track in tracks.items():
        try:
            segment = _get_track_segment(
                track, seg_len_before, seg_len_after, selection_time
            )
            lonslats = _get_lonslats(segment)
        except ValueError:
            counts['segment_not_available'] += 1
            continue

        if filter_mslp:
            mslp_values = segment['air_pressure_at_mean_sea_level'].values
            if np.nanmin(mslp_values) > filter_mslp:
                counts['filter_mslp'] += 1
                continue
        if filter_rv:
            rv_values = segment['relative_vorticity'].values
            if np.nanmax(rv_values) < filter_rv:
                counts['filter_rv'] += 1
                continue

        dists = haversine_np(*target_lonslats, *lonslats)
        if dists[seg_len_before] > candidate_distance:
            counts['candidate_test'] += 1
            continue
        else:
            candidate_tracks[track_id] = track

        func = {'mean': np.nanmean, 'max': np.nanmax}[analogue_function]
        if func(dists) > analogue_distance:
            counts['analogue_test'] += 1
            continue
        else:
            analogue_tracks[track_id] = track

    if verbose:
        print(f'Found {len(candidate_tracks)} candidate tracks')
        print(f'Found {len(analogue_tracks)} analogue tracks')
        print(f'Filter counts: {counts}')

    return candidate_tracks, analogue_tracks, counts