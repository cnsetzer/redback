from __future__ import annotations

from os.path import join
from typing import Any, Union

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import redback
from redback.utils import KwargsAccessorWithDefault


class _FilenameGetter(object):
    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    def __get__(self, instance: Plotter, owner: object) -> str:
        return instance.get_filename(default=f"{instance.transient.name}_{self.suffix}.png")

    def __set__(self, instance: Plotter, value: object) -> None:
        pass


class _FilePathGetter(object):

    def __init__(self, directory_property: str, filename_property: str) -> None:
        self.directory_property = directory_property
        self.filename_property = filename_property

    def __get__(self, instance: Plotter, owner: object) -> str:
        return join(getattr(instance, self.directory_property), getattr(instance, self.filename_property))


class Plotter(object):

    capsize = KwargsAccessorWithDefault("capsize", 0.)
    color = KwargsAccessorWithDefault("color", "k")
    band_labels = KwargsAccessorWithDefault("band_labels", None)
    dpi = KwargsAccessorWithDefault("dpi", 300)
    elinewidth = KwargsAccessorWithDefault("elinewidth", 2)
    errorbar_fmt = KwargsAccessorWithDefault("errorbar_fmt", "x")
    model = KwargsAccessorWithDefault("model", None)
    ms = KwargsAccessorWithDefault("ms", 1)
    x_axis_tick_params_pad = KwargsAccessorWithDefault("x_axis_tick_params_pad", 10)

    max_likelihood_alpha = KwargsAccessorWithDefault("max_likelihood_alpha", 0.65)
    random_sample_alpha = KwargsAccessorWithDefault("random_sample_alpha", 0.05)
    max_likelihood_color = KwargsAccessorWithDefault("max_likelihood_color", "blue")
    random_sample_color = KwargsAccessorWithDefault("random_sample_color", "red")

    bbox_inches = KwargsAccessorWithDefault("bbox_inches", "tight")
    linewidth = KwargsAccessorWithDefault("linewidth", 2)
    zorder = KwargsAccessorWithDefault("zorder", -1)

    xy = KwargsAccessorWithDefault("xy", (0.95, 0.9))
    xycoords = KwargsAccessorWithDefault("xycoords", "axes fraction")
    horizontalalignment = KwargsAccessorWithDefault("horizontalalignment", "right")
    annotation_size = KwargsAccessorWithDefault("annotation_size", 20)

    fontsize_axes = KwargsAccessorWithDefault("fontsize_axes", 18)
    fontsize_figure = KwargsAccessorWithDefault("fontsize_figure", 30)
    hspace = KwargsAccessorWithDefault("hspace", 0.04)
    wspace = KwargsAccessorWithDefault("wspace", 0.15)

    plot_others = KwargsAccessorWithDefault("plot_others", True)
    random_models = KwargsAccessorWithDefault("random_models", 100)

    xlim_high_multiplier = 2.0
    xlim_low_multiplier = 0.5
    ylim_high_multiplier = 2.0
    ylim_low_multiplier = 0.5

    def __init__(self, transient: redback.transient.Transient, **kwargs) -> None:
        self.transient = transient
        self.kwargs = kwargs
        self._posterior_sorted = False

    def _get_times(self, axes: matplotlib.axes.Axes) -> np.ndarray:
        """
        :param axes: The axes used in the plotting procedure.
        :type axes: matplotlib.axes.Axes

        :return: Linearly or logarithmically scaled time values depending on the y scale used in the plot.
        :rtype: np.ndarray
        """
        if isinstance(axes, np.ndarray):
            ax = axes[0]
        else:
            ax = axes

        if ax.get_yscale() == 'linear':
            times = np.linspace(self._xlim_low, self._xlim_high, 200)
        else:
            times = np.exp(np.linspace(np.log(self._xlim_low), np.log(self._xlim_high), 200))
        return times

    @property
    def _xlim_low(self) -> float:
        default = self.xlim_low_multiplier * self.transient.x[0]
        if default == 0:
            default += 1e-3
        return self.kwargs.get("xlim_low", default)

    @property
    def _xlim_high(self) -> float:
        if self._x_err is None:
            default = self.xlim_high_multiplier * self.transient.x[-1]
        else:
            default = self.xlim_high_multiplier * (self.transient.x[-1] + self._x_err[1][-1])
        return self.kwargs.get("xlim_high", default)

    @property
    def _ylim_low(self) -> float:
        default = self.ylim_low_multiplier * min(self.transient.y)
        return self.kwargs.get("ylim_low", default)

    @property
    def ylim_high(self) -> float:
        default = self.ylim_high_multiplier * np.max(self.transient.y)
        return self.kwargs.get("ylim_high", default)

    @property
    def _x_err(self) -> Union[np.ndarray, None]:
        if self.transient.x_err is not None:
            return np.array([np.abs(self.transient.x_err[1, :]), self.transient.x_err[0, :]])
        else:
            return None

    @property
    def _y_err(self) -> np.ndarray:
        return np.array([np.abs(self.transient.y_err[1, :]), self.transient.y_err[0, :]])

    @property
    def _lightcurve_plot_outdir(self) -> str:
        return self._get_outdir(join(self.transient.directory_structure.directory_path, self.model.__name__))

    @property
    def _data_plot_outdir(self) -> str:
        return self._get_outdir(self.transient.directory_structure.directory_path)

    def _get_outdir(self, default: str) -> str:
        return self._get_kwarg_with_default(kwarg="outdir", default=default)

    def get_filename(self, default: str) -> str:
        return self._get_kwarg_with_default(kwarg="filename", default=default)

    def _get_kwarg_with_default(self, kwarg: str, default: Any) -> Any:
        return self.kwargs.get(kwarg, default) or default

    @property
    def _model_kwargs(self) -> dict:
        return self._get_kwarg_with_default("model_kwargs", dict())

    @property
    def _posterior(self) -> pd.DataFrame:
        posterior = self.kwargs.get("posterior", pd.DataFrame())
        if not self._posterior_sorted and posterior is not None:
            posterior.sort_values(by='log_likelihood', inplace=True)
            self._posterior_sorted = True
        return posterior

    @property
    def _max_like_params(self) -> pd.core.series.Series:
        return self._posterior.iloc[-1]

    def _get_random_parameters(self) -> list[pd.core.series.Series]:
        return [self._posterior.iloc[np.random.randint(len(self._posterior))] for _ in range(self.random_models)]

    _data_plot_filename = _FilenameGetter(suffix="data")
    _lightcurve_plot_filename = _FilenameGetter(suffix="lightcurve")
    _residual_plot_filename = _FilenameGetter(suffix="residual")
    _multiband_data_plot_filename = _FilenameGetter(suffix="multiband_data")
    _multiband_lightcurve_plot_filename = _FilenameGetter(suffix="multiband_lightcurve")

    _data_plot_filepath = _FilePathGetter(
        directory_property="_data_plot_outdir", filename_property="_data_plot_filename")
    _lightcurve_plot_filepath = _FilePathGetter(
        directory_property="_lightcurve_plot_outdir", filename_property="_lightcurve_plot_filename")
    _residual_plot_filepath = _FilePathGetter(
        directory_property="_lightcurve_plot_outdir", filename_property="_residual_plot_filename")
    _multiband_data_plot_filepath = _FilePathGetter(
        directory_property="_data_plot_outdir", filename_property="_multiband_data_plot_filename")
    _multiband_lightcurve_plot_filepath = _FilePathGetter(
        directory_property="_lightcurve_plot_outdir", filename_property="_multiband_lightcurve_plot_filename")

    def _save_and_show(self, filepath: str, save: bool, show: bool) -> None:
        plt.tight_layout()
        if save:
            plt.savefig(filepath, dpi=self.dpi, bbox_inches=self.bbox_inches)
        if show:
            plt.show()


class IntegratedFluxPlotter(Plotter):

    @property
    def _xlabel(self) -> str:
        return r"Time since burst [s]"

    @property
    def _ylabel(self) -> str:
        return self.transient.ylabel

    def plot_data(
            self, axes: matplotlib.axes.Axes = None, save: bool = True, show: bool = True) -> matplotlib.axes.Axes:
        """Plots the Integrated flux data and returns Axes.

        :param axes: Matplotlib axes to plot the data into. Useful for user specific modifications to the plot.
        :type axes: Union[matplotlib.axes.Axes, None], optional
        :param save: Whether to save the plot. (Default value = True)
        :type save: bool
        :param show: Whether to show the plot. (Default value = True)
        :type show: bool

        :return: The axes with the plot.
        :rtype: matplotlib.axes.Axes
        """
        ax = axes or plt.gca()

        ax.errorbar(self.transient.x, self.transient.y, xerr=self._x_err, yerr=self._y_err,
                    fmt=self.errorbar_fmt, c=self.color, ms=self.ms, elinewidth=self.elinewidth, capsize=self.capsize)

        ax.set_xscale('log')
        ax.set_yscale('log')

        ax.set_xlim(self._xlim_low, self._xlim_high)
        ax.set_ylim(self._ylim_low, self.ylim_high)
        ax.set_xlabel(self._xlabel, fontsize=self.fontsize_axes)
        ax.set_ylabel(self._ylabel, fontsize=self.fontsize_axes)

        ax.annotate(
            self.transient.name, xy=self.xy, xycoords=self.xycoords,
            horizontalalignment=self.horizontalalignment, size=self.annotation_size)

        ax.tick_params(axis='x', pad=self.x_axis_tick_params_pad)

        self._save_and_show(filepath=self._data_plot_filepath, save=save, show=show)
        return ax

    def plot_lightcurve(
            self, axes: matplotlib.axes.Axes = None, save: bool = True, show: bool = True) -> matplotlib.axes.Axes:
        """Plots the Integrated flux data and the lightcurve and returns Axes.

        :param axes: Matplotlib axes to plot the lightcurve into. Useful for user specific modifications to the plot.
        :type axes: Union[matplotlib.axes.Axes, None], optional
        :param save: Whether to save the plot. (Default value = True)
        :type save: bool
        :param show: Whether to show the plot. (Default value = True)
        :type show: bool

        :return: The axes with the plot.
        :rtype: matplotlib.axes.Axes
        """
        axes = axes or plt.gca()

        axes = self.plot_data(axes=axes, save=False, show=False)
        times = self._get_times(axes)

        self._plot_lightcurves(axes, times)

        self._save_and_show(filepath=self._lightcurve_plot_filepath, save=save, show=show)
        return axes

    def _plot_lightcurves(self, axes: matplotlib.axes.Axes, times: np.ndarray) -> None:
        ys = self.model(times, **self._max_like_params, **self._model_kwargs)
        axes.plot(times, ys, color=self.max_likelihood_color, alpha=self.max_likelihood_alpha, lw=self.linewidth)
        for params in self._get_random_parameters():
            self._plot_single_lightcurve(axes=axes, times=times, params=params)

    def _plot_single_lightcurve(self, axes: matplotlib.axes.Axes, times: np.ndarray, params: dict) -> None:
        ys = self.model(times, **params, **self._model_kwargs)
        axes.plot(times, ys, color=self.random_sample_color, alpha=self.random_sample_alpha, lw=self.linewidth,
                  zorder=self.zorder)

    def plot_residuals(
            self, axes: matplotlib.axes.Axes = None, save: bool = True, show: bool = True) -> matplotlib.axes.Axes:
        """Plots the residual of the Integrated flux data returns Axes.

        :param axes: Matplotlib axes to plot the lightcurve into. Useful for user specific modifications to the plot.
        :param save: Whether to save the plot. (Default value = True)
        :param show: Whether to show the plot. (Default value = True)

        :return: The axes with the plot.
        :rtype: matplotlib.axes.Axes
        """
        if axes is None:
            fig, axes = plt.subplots(
                nrows=2, ncols=1, sharex=True, sharey=False, figsize=(10, 8), gridspec_kw=dict(height_ratios=[2, 1]))

        axes[0] = self.plot_lightcurve(axes=axes[0], save=False, show=False)
        axes[1].set_xlabel(axes[0].get_xlabel(), fontsize=self.fontsize_axes)
        axes[0].set_xlabel("")
        ys = self.model(self.transient.x, **self._max_like_params, **self._model_kwargs)
        axes[1].errorbar(
            self.transient.x, self.transient.y - ys, xerr=self._x_err, yerr=self._y_err,
            fmt=self.errorbar_fmt, c=self.color, ms=self.ms, elinewidth=self.elinewidth, capsize=self.capsize)
        axes[1].set_yscale("log")
        axes[1].set_ylabel("Residual", fontsize=self.fontsize_axes)
        self._save_and_show(filepath=self._residual_plot_filepath, save=save, show=show)
        return axes


class LuminosityPlotter(IntegratedFluxPlotter):
    pass


class MagnitudePlotter(Plotter):

    xlim_low_phase_model_multiplier = 0.9
    xlim_high_phase_model_multiplier = 1.1
    xlim_high_multiplier = 1.2
    ylim_low_magnitude_multiplier = 0.8
    ylim_high_magnitude_multiplier = 1.2
    ncols = KwargsAccessorWithDefault("ncols", 2)

    @property
    def _colors(self) -> str:
        return self.kwargs.get("colors", self.transient.get_colors(self._filters))

    @property
    def _xlabel(self) -> str:
        if self.transient.use_phase_model:
            default = f"Time since {self._reference_mjd_date} MJD [days]"
        else:
            default = self.transient.xlabel
        return self.kwargs.get("xlabel", default)

    @property
    def _ylabel(self) -> str:
        return self.kwargs.get("ylabel", self.transient.ylabel)

    @property
    def _xlim_low(self) -> float:
        if self.transient.use_phase_model:
            default = (self.transient.x[0] - self._reference_mjd_date) * self.xlim_low_phase_model_multiplier
        else:
            default = self.xlim_low_multiplier * self.transient.x[0]
        if default == 0:
            default += 1e-3
        return self.kwargs.get("xlim_low", default)

    @property
    def _xlim_high(self) -> float:
        if self.transient.use_phase_model:
            default = (self.transient.x[-1] - self._reference_mjd_date) * self.xlim_high_phase_model_multiplier
        else:
            default = self.xlim_high_multiplier * self.transient.x[-1]
        return self.kwargs.get("xlim_high", default)

    @property
    def _ylim_low_magnitude(self) -> float:
        return self.ylim_low_magnitude_multiplier * min(self.transient.y)

    @property
    def _ylim_high_magnitude(self) -> float:
        return self.ylim_high_magnitude_multiplier * np.max(self.transient.y)

    def _get_ylim_low_with_indices(self, indices: list) -> float:
        return self.ylim_low_multiplier * min(self.transient.y[indices])

    def _get_ylim_high_with_indices(self, indices: list) -> float:
        return self.ylim_high_multiplier * np.max(self.transient.y[indices])

    def _get_x_err(self, indices: list) -> np.ndarray:
        return self.transient.x_err[indices] if self.transient.x_err is not None else self.transient.x_err

    def _set_y_axis_data(self, ax: matplotlib.axes.Axes) -> None:
        if self.transient.magnitude_data:
            ax.set_ylim(self._ylim_low_magnitude, self._ylim_high_magnitude)
            ax.invert_yaxis()
        else:
            ax.set_ylim(self._ylim_low, self.ylim_high)
            ax.set_yscale("log")

    def _set_y_axis_multiband_data(self, ax: matplotlib.axes.Axes, indices: list) -> None:
        if self.transient.magnitude_data:
            ax.set_ylim(self._ylim_low_magnitude, self._ylim_high_magnitude)
            ax.invert_yaxis()
        else:
            ax.set_ylim(self._get_ylim_low_with_indices(indices=indices),
                        self._get_ylim_high_with_indices(indices=indices))
            ax.set_yscale("log")

    def _set_x_axis(self, axes: matplotlib.axes.Axes) -> None:
        if self.transient.use_phase_model:
            axes.set_xscale("log")
        axes.set_xlim(self._xlim_low, self._xlim_high)

    @property
    def _nrows(self) -> int:
        default = int(np.ceil(len(self._filters) / 2))
        return self._get_kwarg_with_default("nrows", default=default)

    @property
    def _npanels(self) -> int:
        npanels = self._nrows * self.ncols
        if npanels < len(self._filters):
            raise ValueError(f"Insufficient number of panels. {npanels} panels were given "
                             f"but {len(self._filters)} panels are needed.")
        return npanels

    @property
    def _figsize(self) -> tuple:
        default = (4 + 4 * self.ncols, 2 + 2 * self._nrows)
        return self._get_kwarg_with_default("figsize", default=default)

    @property
    def _reference_mjd_date(self) -> int:
        if self.transient.use_phase_model:
            return self.kwargs.get("reference_mjd_date", int(self.transient.x[0]))
        return 0

    @property
    def band_label_generator(self):
        if self.band_labels is not None:
            return (bl for bl in self.band_labels)

    def plot_data(
            self, axes: matplotlib.axes.Axes = None, save: bool = True, show: bool = True) -> matplotlib.axes.Axes:
        """Plots the Magnitude data and returns Axes.

        :param axes: Matplotlib axes to plot the data into. Useful for user specific modifications to the plot.
        :type axes: Union[matplotlib.axes.Axes, None], optional
        :param save: Whether to save the plot. (Default value = True)
        :type save: bool
        :param show: Whether to show the plot. (Default value = True)
        :type show: bool

        :return: The axes with the plot.
        :rtype: matplotlib.axes.Axes
        """
        ax = axes or plt.gca()

        band_label_generator = self.band_label_generator

        for indices, band in zip(self.transient.list_of_band_indices, self.transient.unique_bands):
            if band in self._filters:
                color = self._colors[list(self._filters).index(band)]
                if band_label_generator is None:
                    label = band
                else:
                    label = next(band_label_generator)
            elif self.plot_others:
                color = "black"
                label = None
            else:
                continue
            if isinstance(label, float):
                label = f"{label:.2e}"
            ax.errorbar(
                self.transient.x[indices] - self._reference_mjd_date, self.transient.y[indices],
                xerr=self._get_x_err(indices), yerr=self.transient.y_err[indices],
                fmt=self.errorbar_fmt, ms=self.ms, color=color,
                elinewidth=self.elinewidth, capsize=self.capsize, label=label)

        self._set_x_axis(axes=ax)
        self._set_y_axis_data(ax)

        ax.set_xlabel(self._xlabel, fontsize=self.fontsize_axes)
        ax.set_ylabel(self._ylabel, fontsize=self.fontsize_axes)

        ax.tick_params(axis='x', pad=self.x_axis_tick_params_pad)
        ax.legend(ncol=2, loc='best')

        self._save_and_show(filepath=self._data_plot_filepath, save=save, show=show)
        return ax

    def plot_lightcurve(
            self, axes: matplotlib.axes.Axes = None, save: bool = True, show: bool = True)\
            -> matplotlib.axes.Axes:
        """Plots the Magnitude data and returns Axes.

        :param axes: Matplotlib axes to plot the lightcurve into. Useful for user specific modifications to the plot.
        :type axes: Union[matplotlib.axes.Axes, None], optional
        :param save: Whether to save the plot. (Default value = True)
        :type save: bool
        :param show: Whether to show the plot. (Default value = True)
        :type show: bool

        :return: The axes with the plot.
        :rtype: matplotlib.axes.Axes
        """
        axes = axes or plt.gca()

        axes = self.plot_data(axes=axes, save=False, show=False)
        axes.set_yscale('log')

        times = self._get_times(axes)

        random_params = self._get_random_parameters()

        for band, color in zip(self.transient.active_bands, self.transient.get_colors(self.transient.active_bands)):
            frequency = redback.utils.bands_to_frequency([band])
            self._model_kwargs["frequency"] = np.ones(len(times)) * frequency
            ys = self.model(times, **self._max_like_params, **self._model_kwargs)
            axes.plot(times - self._reference_mjd_date, ys, color=color, alpha=0.65, lw=2)

            for params in random_params:
                ys = self.model(times, **params, **self._model_kwargs)
                axes.plot(times - self._reference_mjd_date, ys, color='red', alpha=0.05, lw=2, zorder=-1)

        self._save_and_show(filepath=self._lightcurve_plot_filepath, save=save, show=show)
        return axes

    def _check_valid_multiband_data_mode(self) -> bool:
        if self.transient.luminosity_data or self.transient.flux_data:
            redback.utils.logger.warning(
                f"Plotting multiband lightcurve/data not possible for {self.transient.data_mode}. Returning.")
            return False
        return True

    def plot_multiband(
            self, figure: matplotlib.figure.Figure = None, axes: matplotlib.axes.Axes = None, save: bool = True,
            show: bool = True) -> matplotlib.axes.Axes:
        """Plots the Magnitude multiband data and returns Axes.

        :param figure: Matplotlib figure to plot the data into.
        :type figure: matplotlib.figure.Figure
        :param axes: Matplotlib axes to plot the data into. Useful for user specific modifications to the plot.
        :type axes: Union[matplotlib.axes.Axes, None], optional
        :param save: Whether to save the plot. (Default value = True)
        :type save: bool
        :param show: Whether to show the plot. (Default value = True)
        :type show: bool

        :return: The axes with the plot.
        :rtype: matplotlib.axes.Axes
        """
        if not self._check_valid_multiband_data_mode():
            return

        if figure is None or axes is None:
            figure, axes = plt.subplots(ncols=self.ncols, nrows=self._nrows, sharex='all', figsize=self._figsize)

        axes = axes.ravel()

        band_label_generator = self.band_label_generator

        i = 0
        for indices, band, freq in zip(
                self.transient.list_of_band_indices, self.transient.unique_bands, self.transient.unique_frequencies):
            if band not in self._filters:
                continue

            x_err = self._get_x_err(indices)
            color = self._colors[list(self._filters).index(band)]
            if band_label_generator is None:
                label = self._get_multiband_plot_label(band, freq)
            else:
                label = next(band_label_generator)

            axes[i].errorbar(
                self.transient.x[indices] - self._reference_mjd_date, self.transient.y[indices], xerr=x_err,
                yerr=self.transient.y_err[indices], fmt=self.errorbar_fmt, ms=self.ms, color=color,
                elinewidth=self.elinewidth, capsize=self.capsize,
                label=label)

            self._set_x_axis(axes[i])
            self._set_y_axis_multiband_data(axes[i], indices)
            axes[i].legend(ncol=2)
            axes[i].tick_params(axis='both', which='major', pad=8)
            i += 1

        figure.supxlabel(self._xlabel, fontsize=self.fontsize_figure)
        figure.supylabel(self._ylabel, fontsize=self.fontsize_figure)
        plt.subplots_adjust(wspace=self.wspace, hspace=self.hspace)

        self._save_and_show(filepath=self._multiband_data_plot_filepath, save=save, show=show)
        return axes

    @staticmethod
    def _get_multiband_plot_label(band: str, freq: float) -> str:
        if isinstance(band, str):
            if 1e10 < float(freq) < 1e15:
                label = band
            else:
                label = freq
        else:
            label = f"{band:.2e}"
        return label

    @property
    def _filters(self) -> list[str]:
        filters = self.kwargs.get("filters", self.transient.active_bands)
        if filters is None:
            return self.transient.active_bands
        elif str(filters) == 'default':
            return self.transient.default_filters
        return filters

    def plot_multiband_lightcurve(
            self, axes: matplotlib.axes.Axes = None, save: bool = True, show: bool = True) -> matplotlib.axes.Axes:
        """Plots the Magnitude multiband lightcurve and returns Axes.

        :param axes: Matplotlib axes to plot the data into. Useful for user specific modifications to the plot.
        :type axes: Union[matplotlib.axes.Axes, None], optional
        :param save: Whether to save the plot. (Default value = True)
        :type save: bool
        :param show: Whether to show the plot. (Default value = True)
        :type show: bool

        :return: The axes with the plot.
        :rtype: matplotlib.axes.Axes
        """
        if not self._check_valid_multiband_data_mode():
            return

        axes = axes or plt.gca()
        axes = self.plot_multiband(axes=axes, save=False, show=False)

        times = self._get_times(axes)
        frequency = self.transient.bands_to_frequency(self._filters)
        for ii in range(len(frequency)):
            new_model_kwargs = self._model_kwargs.copy()
            new_model_kwargs['frequency'] = frequency[ii]
            ys = self.model(times, **self._max_like_params, **new_model_kwargs)
            axes[ii].plot(
                times - self._reference_mjd_date, ys, color=self.max_likelihood_color,
                alpha=self.max_likelihood_alpha, lw=self.linewidth)
            random_ys_list = [self.model(times, **random_params, **new_model_kwargs)
                              for random_params in self._get_random_parameters()]
            for random_ys in random_ys_list:
                axes[ii].plot(times - self._reference_mjd_date, random_ys, color=self.random_sample_color,
                              alpha=self.random_sample_alpha, lw=self.linewidth, zorder=self.zorder)

        self._save_and_show(filepath=self._multiband_lightcurve_plot_filepath, save=save, show=show)
        return axes


class FluxDensityPlotter(MagnitudePlotter):
    pass
