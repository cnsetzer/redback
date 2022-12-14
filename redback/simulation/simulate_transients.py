import numpy as np
from typing import Union
import regex as re
from sncosmo import TimeSeriesSource, Model, get_bandpass
import simsurvey
import redback
import pandas as pd
from redback.utils import logger
from itertools import repeat
from collections import namedtuple
import astropy.units as uu
from scipy.spatial import KDTree


class SimulateOpticalTransient(object):
    """
    Simulate a single optical transient from a given observation dictionary
    """
    def __init__(self, model, parameters, pointings_database=None, survey='Rubin_10yr_baseline',
                 min_dec=None,max_dec=None, start_mjd=None, end_mjd=None, sncosmo_kwargs=None, buffer_days=100,
                 population=False, **kwargs):
        if isinstance(model, str):
            self.model = redback.model_library.all_models_dict[model]
            self.sncosmo_model = self._make_sncosmo_wrapper_for_redback_model()
        elif callable(model):
            self.model = model
            logger.info('Using custom model. Making a SNCosmo wrapper for this model')
            self.sncosmo_model = self._make_sncosmo_wrapper_for_user_model()
        else:
            raise ValueError("The user needs to specify model as either a string or function.")

        if survey is not None:
            self.pointing_database_name = self._survey_to_table_name_lookup(survey)
            self.pointing_database = pd.read_csv(self.pointing_database_name, compression='gzip')
            logger.info(f"Using {self.pointing_database_name} as the pointing database corresponding to {survey}.")
        else:
            self.pointing_database = pointings_database
            self.pointing_database_name = 'user_defined'
            if isinstance(survey, pd.DataFrame):
                logger.info(f"Using the supplied as the pointing database.")
            else:
                raise ValueError("The user needs to specify survey as either a string or a "
                                 "pointings_database pandas DataFrame.")

        self.buffer_days = buffer_days
        self.population = population
        self.parameters = parameters
        self.sncosmo_kwargs = sncosmo_kwargs
        self.min_dec = min_dec
        self.max_dec = max_dec
        self.start_mjd = start_mjd
        self.end_mjd = end_mjd

    @property
    def _get_unique_reference_fluxes(self):
        unique_bands = self.pointing_database.filters.unique()
        redback.utils.bands_to_reference_flux


    @property
    def _initialise_from_pointings(self):
        df = self.pointing_database

        bandflux_errors = redback.utils.bandflux_error_from_limiting_mag(limiting_magnitudes, reference_flux)
        min_dec = np.min(df['_dec'])
        max_dec = np.max(df['_dec'])
        start_mjd = np.min(df['expMJD'])
        end_mjd = np.max(df['expMJD'])
        return min_dec, max_dec, start_mjd, end_mjd

    @property
    def _update_parameters(self):
        parameters = self.parameters
        if self.population:
            size = len(parameters)
        else:
            size = 1
        dec_dist = (np.arccos(2* np.random.uniform(low=(1 - np.sin(self.min_dec)) / 2,
                                                   high=(1 - np.sin(self.max_dec)) / 2,
                                                   size=size)- 1) - np.pi / 2)
        parameters['RA'] = parameters.get("RA", np.random.uniform(0, 2*np.pi, size=size))
        parameters['DEC'] = parameters.get("DEC", dec_dist)
        parameters['MJD'] = parameters.get("MJD", np.random.uniform(self.start_mjd, self.end_mjd, size=size))
        return parameters

    def _make_sncosmo_wrapper_for_redback_model(self):
        model_kwargs = {}
        self.sncosmo_kwargs['max_time'] = self.sncosmo_kwargs.get('max_time', 100)
        model_kwargs['output_format'] = 'sncosmo_source'
        time = self.sncosmo_kwargs.get('dense_times', np.linspace(0, self.sncosmo_kwargs['max_time'], 200))
        full_kwargs = self.parameters.copy()
        full_kwargs.update(model_kwargs)
        source = self.model(time, **full_kwargs)
        return Model(source=source, **self.sncosmo_kwargs)

    def _make_sncosmo_wrapper_for_user_model(self):
        """
        Function to wrap redback models into sncosmo model format for added functionality.
        """
        self.sncosmo_kwargs['max_time'] = self.sncosmo_kwargs.get('max_time', 100)
        self.parameters['wavelength_observer_frame'] = self.parameters.get('wavelength_observer_frame',
                                                                          np.geomspace(100,20000,100))
        time = self.sncosmo_kwargs.get('dense_times', np.linspace(0, self.sncosmo_kwargs['max_time'], 200))
        fmjy = self.model(time, **self.parameters)
        spectra = fmjy.to(uu.mJy).to(uu.erg / uu.cm ** 2 / uu.s / uu.Angstrom,
                equivalencies=uu.spectral_density(wav=self.parameters['wavelength_observer_frame'] * uu.Angstrom))
        source = TimeSeriesSource(phase=time, wave=self.parameters['wavelength_observer_frame'],
                                  flux=spectra)
        return Model(source=source, **self.sncosmo_kwargs)

    def _survey_to_table_name_lookup(self, survey):
        survey_to_table = {'Rubin_10yr_baseline': 'rubin_baseline_nexp1_v1_7_10yrs.tar.gz',
                           'Rubin_10yr_deep': 'rubin_deep_nexp1_v1_7_10yrs.tar.gz',
                           'Rubin_10yr_wfd': 'rubin_wfd_nexp1_v1_7_10yrs.tar.gz',
                           'Rubin_10yr_dcr': 'rubin_dcr_nexp1_v1_7_10yrs.tar.gz',
                           'ZTF_deep': 'ztf_deep_nexp1_v1_7_10yrs.tar.gz',
                           'ZTF_wfd': 'ztf_wfd_nexp1_v1_7_10yrs.tar.gz'}
        return survey_to_table[survey]

    def _make_observation_single(self, sncosmo_model, overlapping_database):
        times = overlapping_database['expMJD'].values - sncosmo_model.mintime()
        filters = overlapping_database['filter']
        limiting_magnitudes = overlapping_database['fiveSigmaDepth'].values

        flux = sncosmo_model.bandflux(times, filters)
        # what can be preprocessed
        observed_flux = np.random.normal(loc=flux, scale=bandflux_errors)
        magnitudes = redback.utils.bandpass_flux_to_magnitude(observed_flux, filters)
        magnitude_errs = redback.utils.magnitude_error_from_flux_error(flux, bandflux_errors)
        observation_dataframe = pd.DataFrame(columns=['event', 'time', 'magnitude', 'e_magnitude', 'band', 'system', 'flux_density(mjy)', 'flux_density_error', 'flux(erg/cm2/s)', 'flux_error', 'time (days)'])
        observation_dataframe['time'] = times + sncosmo_model.mintime()
        observation_dataframe['magnitude'] = magnitudes
        observation_dataframe['e_magnitude'] = magnitude_errs
        observation_dataframe['band'] = filters
        observation_dataframe['system'] = 'AB'
        observation_dataframe['flux_density(mjy)'] =
        observation_dataframe['flux_density_error'] =
        observation_dataframe['flux(erg/cm2/s)'] = observed_flux
        observation_dataframe['flux_error'] = bandflux_errors
        observation_dataframe['time (days)'] = times
        return observation_dataframe

    def _make_observations(self, sncosmo_model):
        if self.population:
            overlapping_indices = self._find_sky_overlaps(survey_fov_rad=9.6)
            overlapping_database_iter = iter(self.pointings_database.iloc(iter(overlapping_indices)))
        else:
            self._make_observation_single(self.pointing_database)

    def _convert_circular_fov_to_radius(self):
        radius = np.sqrt(survey_fov*((np.pi/180.0)**2.0)/np.pi)
        return radius

    def _find_sky_overlaps(self, survey_fov_rad=None):
        """
        Makes a pandas dataframe of pointings from specified settings.

        :param float: ra
        :param float: dec
        :param dict: num_obs
        :param dict: average_cadence
        :param dict: cadence_scatter
        :param dict: limiting_magnitudes

        :return dataframe: pandas dataframe of the mock pointings needed to simulate observations for
        given transient.
        """
        pointings_sky_pos = self.pointings_database[['_ra', '_dec']].to_numpy()
        transient_sky_pos = (parameters.pop['ra'], parameters.pop['dec'])
        transient_sky_pos = transient_sky_pos * (np.pi / 180.)
        pointings_sky_pos = pointings_sky_pos * (np.pi / 180.)
        survey_fov_rad = survey_fov_rad * (np.pi / 180.)

        transient_sky_pos_3D = np.vstack([np.cos(transient_sky_pos[:, 0]) * np.cos(transient_sky_pos[:, 1]),
                                     np.sin(transient_sky_pos[:, 0]) * np.cos(transient_sky_pos[:, 1]),
                                     np.sin(transient_sky_pos[:, 1])]).T
        pointings_sky_pos_3D = np.vstack([np.cos(pointings_sky_pos[:, 0]) * np.cos(pointings_sky_pos[:, 1]),
                                     np.sin(pointings_sky_pos[:, 0]) * np.cos(pointings_sky_pos[:, 1]),
                                     np.sin(pointings_sky_pos[:, 1])]).T

        # law of cosines to compute 3D distance
        max_3D_dist = np.sqrt(2 - 2 * np.cos(survey_fov_rad))
        survey_tree = KDTree(transient_sky_pos_3D)
        overlap_indices = survey_tree.query_ball_point(pointings_sky_pos_3D, max_3D_dist)
        return overlap_indices



    def _save_transient(self):
        pass

    @classmethod
    def simulate_transient(cls, model, parameters, pointings_database=None, survey='Rubin_10yr_baseline',
                           buffer_days=100, population=False, **kwargs):
        """
        Makes a pandas dataframe of pointings from specified settings.

        :param float: ra
        :param float: dec
        :param dict: num_obs
        :param dict: average_cadence
        :param dict: cadence_scatter
        :param dict: limiting_magnitudes

        :return dataframe: pandas dataframe of the mock pointings needed to simulate observations for
        given transient.
        """
        return cls(model, parameters, pointings_database=pointings_database, survey=survey,
                   buffer_days=buffer_days, population=population, **kwargs)

    @classmethod
    def simulate_transient_population(cls, model, parameters, pointings_database=None, survey='Rubin_10yr_baseline',
                           buffer_days=100, population=True, **kwargs):
        """
        Makes a pandas dataframe of pointings from specified settings.

        :param float: ra
        :param float: dec
        :param dict: num_obs
        :param dict: average_cadence
        :param dict: cadence_scatter
        :param dict: limiting_magnitudes

        :return dataframe: pandas dataframe of the mock pointings needed to simulate observations for
        given transient.
        """
        return cls(model, parameters, pointings_database=pointings_database, survey=survey,
                   buffer_days=buffer_days, population=population, **kwargs)

    # @classmethod
    # def simulate_transient(cls, model, parameters, buffer_days=100, survey='Rubin_10yr_baseline', **kwargs):
    #     if isinstance(survey, str):
    #         # load the corresponding file
    #         table = cls._survey_to_table_name_lookup(survey)
    #         simtransient = cls(model, pointings_database=pointings_database, **kwargs)
    #
    #     if isinstance(survey, pd.DataFrame):
    #         # initialise from the datafile.
    #     self.RA = parameters.get("RA", np.random.uniform(0, 2*np.pi))
    #     self.DEC = parameters.get("DEC", np.random.uniform(-np.pi/2, np.pi/2))
    #     self.mjd = parameters.get("mjd", np.random.uniform((self.start_mjd - buffer_days), (self.end_mjd)))
    #     #
    #     #make observations
    #     data = self._make_observations()
    #
    #     #save the file to disk
    #     self._save_transient()
    #     logger.info("Transient simulated and saved to disk.")
    #     return data

        #
        # :param dataframe: pandas dataframe of parameters to make simulated observations for
        # :param outdir: output directory where the simulated observations will be saved
        # :return:
        # """

def make_pointing_table_from_average_cadence(ra, dec, num_obs, average_cadence, cadence_scatter, limiting_magnitudes, **kwargs):
    """
    Makes a pandas dataframe of pointings from specified settings.

    :param float: ra
    :param float: dec
    :param dict: num_obs
    :param dict: average_cadence
    :param dict: cadence_scatter
    :param dict: limiting_magnitudes

    :return dataframe: pandas dataframe of the mock pointings needed to simulate observations for
    given transient.
    """
    pointings_dataframe = pd.DataFrame(columns=['expMJD', '_ra', '_dec', 'filter', 'fiveSigmaDepth'])
    initMJD = kwargs.get("initMJD", 59580)
    for band in average_cadence.keys():
        expMJD = initMJD + np.cumsum(np.random.normal(loc=average_cadence[band], scale=cadence_scatter[band], size=num_obs[band]))
        filters = list(zip(repeat(band, num_obs[band])))
        limiting_mag = list(zip(repeat(limiting_magnitudes[band], num_obs[band])))
        ras = list(zip(repeat(ra, num_obs[band])))
        decs = list(zip(repeat(dec, num_obs[band])))
        band_pointings_dataframe = pd.DataFrame.from_dict({'expMJD': expMJD, '_ra': ras, '_dec': decs, 'filter': filters, 'fiveSigmaDepth': limiting_mag})
        pointings_dataframe = pd.concat([pointings_dataframe, band_pointings_dataframe])
    return pointings_dataframe

class SimulateFullOpticalSurvey(SimulateOpticalTransient):
    """
    Do SimSurvey or SNANA
    """
    def __init__(self, model, parameters, pointings_database=None, survey='Rubin_10yr_baseline',
                 min_dec=None,max_dec=None, start_mjd=None, end_mjd=None, buffer_days=100,
                 population=False, **kwargs):
        super().__init__(model=model, parameters=parameters, pointings_database=pointings_database, survey=survey,
                 min_dec=min_dec,max_dec=max_dec, start_mjd=start_mjd, end_mjd=end_mjd, buffer_days=buffer_days,
                 population=population, **kwargs)

    # def SimulateOpticalTransient(self, dEng=1.0, energy_unit=uu.Hz):
    #     """
    #     :param model:
    #     :type model:
    #     :param energy_unit:
    #     :type energy_unit:
    #     :param parameters:
    #     :type parameters:
    #     :param pointings:
    #     :type pointings:
    #     :param dEng:
    #     :type dEng:
    #     :return:
    #     :rtype:
    #     """
    #     try:
    #         self.pointings
    #     except AttributeError:
    #         get_pointings()
    #     energy_unit = energy_unit.to(uu.Angstrom, equivalencies=uu.spectral())
    #     unique_filter_list = self.pointings.filter.unique()
    #     times = self.pointings.times
    #     min_wave_list = []
    #     max_wave_list = []
    #     for filter_name in unique_filter_list:
    #         bp = get_bandpass(filter_name)
    #         min_wave_list.append(bp.wave.min())
    #         max_wave_list.append(bp.wave.max())
    #     min_wave = min(min_wave_list)
    #     max_wave = max(max_wave_list)
    #     wavelengths = np.linspace(min_wave, max_wave, num=int((max_wave - min_wave)/dAng))
    #     # determine wavelength/frequency range based on spectral width of filters provided
    #     self.sncosmo_model = sncosmo_function_wrapper(model, energy_unit_scale, energy_unit_base, parameters, wavelengths)
    #
    #
    # def get_pointings(self, instrument=None, pointings=None, scheduler=None):
    #     """
    #     :param instrument: The name of the instrument that pointings
    #     :param pointings:
    #     :param scheduler:
    #     """
    #     pointings = pd.DataFrame(columns=['mjd', ])
    #
    #     if pointings and scheduler:
    #         pointings = pointings_from_scheduler(pointings, scheduler)
    #     elif pointings:
    #         pass # could verify provided pointings format here.
    #     else:
    #         if instrument == 'ZTF':
    #             pointings = create_ztf_pointings() # create list of pointings based on ZTF
    #         elif instrument == 'Rubin':
    #             pointings = create_rubin_pointings() # create list of pointings based on Rubin
    #         elif instrument == 'Roman':
    #             pointings = create_roman_pointings() # create list of pointings based on Roman
    #         else:
    #             print('The requested observatory does not have an implemented set of pointings.')
    #     return
    #
    # def pointings_from_scheduler(self, pointings, scheduler):
    #     """
    #
    #     """
    #     # placeholder to set instrument pointings on scheduler call OpSimSummary etc.
    #
    #     return
    #
    #
    # def SimulateMockObservations(self, bands, times, zpsys='ab'):
    #     """
    #     Function to generate mock observations from the given model and pointings, but can be reexecuted for different parameters
    #     """
    #
    #     bandfluxes = self.sncosmo_model.bandflux(bands, times, zpsys)
    #     noisy_bandfluxes = np.random.normal(loc=bandfluxes, scale=self.pointings.sky_noise, size=bandfluxes.shape)
    #     # Return observation table
    #     # What columns do we want to add, time, band, band-wave, bandflux, flux_err,
    #     pd.DataFrame(columns=['Time_mjd', 'Band', 'Bandflux', 'Flux_err'])
    #
    #     return
