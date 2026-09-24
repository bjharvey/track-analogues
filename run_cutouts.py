"""Routines for extracting cutouts for ERA5 and CANARI data"""

import datetime
import glob
import warnings
import numpy as np
import cftime
import iris
import iris.cube
import iris.plot as iplt
import iris.coord_systems as cs
import pandas as pd

from track_utils import \
    plot_tracks, \
    _get_track_segment, \
    load_single_era5_track, \
    decode_360_time
from run_analogues import \
    reload_analogues, \
    settings, \
    cases, \
    output_dir


def _get_le_info_from_track_filename(fn):
    """
    Assume of the form: */<EXP>/ST/<SUITEID>a/<MEM>/<SUITEID>a_<MEM>_*/ff_trs_pos.*.nc_984
    """
    exp = fn.split('/ST/')[0].split('/')[-1]
    if exp == 'HIST': exp = 'HIST2'
    suiteid = fn.split('/ST/')[1].split('/')[0].strip('a')
    mem = fn.split(suiteid)[1].split('/')[1]
    return exp, suiteid, mem


def load_track_le_variable(trackid, track, ftag, constraint=None, offsethrs=0):
    """
    Load priority data at times in a track cube.

    trackid: Assumed to be <track_file_path>_<trackid>
    ftag: LE filename <suite-id>_<mem>_<ftag>*.nc is loaded
          E.g. for ua use ftag='6hr_pt_m01s30i201'
    """
    print(f'LOAD_TRACK_LE_DATA: Loading {ftag} for track {trackid}')
    priority_dir = '/gws/ssde/j25b/canari/shared/large-ensemble/priority'
    exp, suiteid, mem = _get_le_info_from_track_filename(trackid)
    track_times = [decode_360_time(value) for value in track['time'].values]
    years_needed = np.unique([t.year for t in track_times])
    print(f'LOAD_TRACK_LE_DATA: {exp}, {suiteid}, {mem}, {years_needed}')

    # Construct time constraint for the track times
    times = [t - datetime.timedelta(hours=offsethrs)
             for t in track_times]
    timecon = iris.Constraint(time=lambda t: t.point in times)

    cl = iris.cube.CubeList()
    for year in years_needed:
        fn = glob.glob(f'{priority_dir}/{exp}/{mem}/ATM/yearly/'\
                       f'{year}/{suiteid}a_{mem}_{ftag}*nc')
        if len(fn) > 1:
            print('Error: Found multiple files')
            return None
        else:
            fn = fn[0]
        print(f'LOAD_TRACK_LE_DATA: Loading file:\n{fn}')
        # Hide UserWarning about cellarea
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            cl.append(iris.load_cube(fn))
    # Fix issue where some longitude bounds don't exactly match
    for cube in cl:
        cube.coord('longitude').bounds = None
        cube.coord('longitude').guess_bounds()
    iris.util.equalise_attributes(cl)
    cube = cl.concatenate_cube().extract(timecon & constraint)
    if not cube.coord_dims('time'):
        cube = iris.util.new_axis(cube, 'time')
    return cube


def load_track_le_cutouts(trackid, track, lonrange, latrange):
    """Load a set of global met variables for all times in a track"""
    # Get lons and lats for this track
    mslp = load_track_le_variable(trackid, track, '6hr_m01s16i222', offsethrs=3).\
        intersection(longitude=lonrange, latitude=latrange)
    mslp.convert_units('hPa')
    u = load_track_le_variable(trackid, track, '6hr_pt_m01s30i201').\
        intersection(longitude=lonrange, latitude=latrange)
    v = load_track_le_variable(trackid, track, '6hr_pt_m01s30i202').\
        intersection(longitude=lonrange, latitude=latrange)
    pcon850 = iris.Constraint(air_pressure=850)
    wsp850 = ((u.extract(pcon850)**2 + v.extract(pcon850)**2)**0.5)
    wsp850.rename('wind_speed')
    density = iris.cube.Cube(1e3, units='kg m-3')
    pr = load_track_le_variable(trackid, track, '1hr_m01s05i216', offsethrs=0.5).\
        intersection(longitude=lonrange, latitude=latrange)
    pr2 = pr.copy()
    pr2.data *= 3600.
    pr2.units = 'mm hr-1'
    return [mslp, wsp850, pr2]


def shift_cube_time_by_years(cube, n_years):
    """
    (from co-pilot) Shift an Iris cube's time coordinate points and bounds by n_years.

    Parameters
    ----------
    cube : iris.cube.Cube
        Input cube.
    n_years : int
        Number of years to shift (can be negative).

    Returns
    -------
    iris.cube.Cube
        Cube with shifted time coordinate.
    """
    print(f'Shifting dates by {n_years} years')

    time_coord = cube.coord("time")
    units = time_coord.units

    def shift_dt(dt):
        return type(dt)(
            dt.year + n_years,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
            dt.microsecond,
        )

    # Shift points
    dts = units.num2date(time_coord.points)
    shifted_dts = [shift_dt(dt) for dt in dts]
    time_coord.points = units.date2num(shifted_dts)

    # Shift bounds if present
    if time_coord.has_bounds():
        bounds_dts = units.num2date(time_coord.bounds)

        shifted_bounds = np.empty_like(time_coord.bounds)

        for i in range(bounds_dts.shape[0]):
            for j in range(bounds_dts.shape[1]):
                shifted_bounds[i, j] = units.date2num(
                    shift_dt(bounds_dts[i, j])
                )

        time_coord.bounds = shifted_bounds


def run_cutouts(case, label, setting):
    print('RUN_CUTOUTS:', case, label, setting)
    savefn_cutouts = output_dir / f'{case}/{label}_{case}_cutouts_{setting}.nc'
    def rm_file(filepath):
        if filepath.is_file():
            print(f'RUN_COUTOUTS: Removing existing file\n{filepath}') 
            filepath.unlink()
    rm_file(savefn_cutouts)

    target_track = load_single_era5_track(
        cases[case]['date'],
        cases[case]['trackid'],
        trackvar=cases[case]['trackvar']
    )
    target_point = _get_track_segment(target_track, 0, 0, settings[setting]['selection_time'])
    lon = target_point['longitude'].values[0]
    lat = target_point['latitude'].values[0]
    lonrange = [lon - 30, lon + 30]
    latrange = [lat - 20, lat + 20]

    tracks = reload_analogues(case, label, setting)
    if label not in tracks.keys():
        print('RUN_CUTOUTS: No tracks found - exitting')
        return
    tracks = tracks[label]
    cubes = iris.cube.CubeList()
    for trackid, track in tracks.items():
        point = _get_track_segment(track, 0, 0, settings[setting]['selection_time'])
        cubes0 = load_track_le_cutouts(trackid, point, lonrange, latrange)
        for cube in cubes0:
            tracklon = iris.coords.AuxCoord(
                point['longitude'].values[0],
                long_name='track_longitude'
            )
            tracklat = iris.coords.AuxCoord(
                point['latitude'].values[0],
                long_name='track_latitude'
            )
            cube.add_aux_coord(tracklon, cube.coord_dims('time')[0])
            cube.add_aux_coord(tracklat, cube.coord_dims('time')[0])
            mem = int(cube.attributes['realization_index'])
            shift_cube_time_by_years(cube, 200 * mem)
        cubes.extend(cubes0)        
    iris.util.equalise_attributes(cubes)
    iris.util.unify_time_units(cubes)
    cubes = cubes.concatenate()
    print(f'Saving file: {savefn_cutouts}')
    iris.save(cubes, savefn_cutouts)


def reload_cutouts(case, label, setting):
    """
    Reload precomputed cutouts from run_cutouts.

    Wildcards allowed in label to allow for reloading multiple files
    (e.g. all members)

    Returns: cubelist

    Note: track_longitude and track_latitude need help reloading properly.
    This is because they are aux coords to the time dimension, but the different
    variables have different time coord metadata. On save, theit relation to the
    time coordinates is lost.
    """
    savefn = output_dir.glob(f'{case}/{label}_{case}_cutouts_{setting}.nc')
    print(f'Loading files: {savefn}')
    cubes = iris.load(savefn)
    for cube in cubes:
        cube.var_name = None
        cube.coord('time').var_name = None
        cube.attributes = None
    new_cubes = iris.cube.CubeList(
        iris.util.new_axis(cube, 'time')
        if not cube.coords('time', dim_coords=True)
        else cube
        for cube in cubes
        )
    cubes = new_cubes.concatenate()
    iris.util.unify_time_units(cubes)
    iris.util.equalise_attributes(cubes)
    # Put track_longitude and track_latitude back into cubes they're missing from
    # First find it (always the first cube?)
    track_longitude = cubes[0].coord('track_longitude')
    track_latitude = cubes[0].coord('track_latitude')
    for cube in cubes[1:]:
        if 'time' in [co.name() for co in cube.coords()]:
            print(f'RELOAD_CUTOUTS: Adding track_longitude and track_latitude to {cube.name()}')
            cube.add_aux_coord(track_longitude, cube.coord_dims('time'))
            cube.add_aux_coord(track_latitude, cube.coord_dims('time'))
    return cubes


############################


def get_storm_centred_map(cube, centre_lat, centre_lon, size=15, dx=0.5):
    """Extract a size x size degree box from a cube centred on a specific point,
    interpolated to a rotated lat/lon grid"""
    # cube needs a coord_system:
    geog_cs = cs.GeogCS(6371229.0)  # common UM/CF earth radius
    if cube.coord('latitude').coord_system is None:
        cube.coord('latitude').coord_system = geog_cs
    if cube.coord('longitude').coord_system is None:
        cube.coord('longitude').coord_system = geog_cs
    rotated_cs = cs.RotatedGeogCS(
        grid_north_pole_latitude=90.0-centre_lat,
        grid_north_pole_longitude=centre_lon+180.0
    )
    rlons = np.arange(-size, size+0.1, dx)
    rlats = np.arange(-size, size+0.1, dx)
    rlonc = iris.coords.DimCoord(
        rlons,
        standard_name="grid_longitude",
        units="degrees",
        coord_system=rotated_cs,
    )
    rlatc = iris.coords.DimCoord(
        rlats,
        standard_name="grid_latitude",
        units="degrees",
        coord_system=rotated_cs,
    )
    target_cube = iris.cube.Cube(
        np.zeros((len(rlats), len(rlons))),
        dim_coords_and_dims=[(rlatc, 0), (rlonc, 1)],
    )
    regridded = cube.regrid(target_cube, iris.analysis.Linear())
    return regridded


def extract_storm_centred_box_all(cube, track, size=15, dx=0.5):
    """
    Extract track-centred maps.
    
    Assumes cube is a single cube covering the same times as track.
    """
    lons = track['longitude'].values
    lats = track['latitude'].values
    out = []
    for cube0, lat0, lon0 in zip(cube.slices_over('time'), lats, lons):
        out.append(extract_cutout_single_time(cube0, lat0, lon0, size, dx))
    return out


def compute_cutouts_single_track(trackid, track, times_lab='max_RV'):
    if times_lab == 'max_RV':
        track = _get_track_segment(track, 0, 0, 'max_RV')
    cubes = load_track_le_cutouts(trackid, track)
    return cubes