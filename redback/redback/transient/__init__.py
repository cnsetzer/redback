import os
import numpy as np

from . import grb

dirname = os.path.dirname(__file__)


DATA_MODES = []


class Transient(object):

    def __init__(self, time, time_err, y, y_err, redshift=np.nan, data_mode=None, name=''):
        """
        Base class for all transients
        """
        self.time = time
        self.time_err = time_err
        self.data_mode = data_mode
        self.y = y
        self.y_err = y_err
        self.redshift = redshift
        self.name = name

    def get_flux_density(self):
        pass

    def get_integrated_flux(self):
        pass

    def analytical_flux_to_luminosity(self):
        pass

    def get_optical(self):
        pass

    def _process_data(self):
        pass

    def _set_photon_index(self):
        pass

    def _get_redshift(self):
        pass

    def _set_t90(self):
        pass

    def plot_data(self, axes=None, colour='k'):
        pass
