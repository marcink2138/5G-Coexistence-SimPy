import os

import pandas as pd
import simpy
from PyQt5.QtCore import QThread, pyqtSignal
from matplotlib import pyplot as plt

import coexistanceSimpy
from coexistanceSimpy import FBEVersion
from coexistanceSimpy.scenario_creator_helper import PlotParams
from coexistanceSimpy.scenario_creator_helper import get_scenario_directly_from_json

marks = ['o', 'v', 's', 'P', '*', 'x', '+']
colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k']
max_ffp = 10000


def get_total_run_number(stations_list):
    total_run_number = 0
    for stations in stations_list:
        if len(stations) > total_run_number:
            total_run_number = len(stations)
    return total_run_number


def get_stations_for_current_run(stations_list, run_number):
    current_run_stations_list = []
    for stations in stations_list:
        if len(stations) > run_number:
            current_run_stations_list.append(stations[run_number])
    return current_run_stations_list


def set_env_channel(stations_list, env, channel):
    for station in stations_list:
        station.set_channel(channel)
        station.set_environment(env)


def collect_results(stations_list, result_dict, simulation_time):
    for station in stations_list:
        result_dict["station_name"].append(station.name)
        result_dict["air_time"].append(station.air_time)
        result_dict["cot"].append(station.timers.cot)
        result_dict["ffp"].append(station.timers.ffp)
        normalized_air_time = round(station.air_time / simulation_time, 2)
        normalized_ffp = round(station.timers.ffp / max_ffp, 2)
        normalized_cot = round(station.timers.cot / station.timers.ffp, 2)
        result_dict["normalized_air_time"].append(normalized_air_time)
        result_dict["successful_transmissions"].append(station.succeeded_transmissions)
        result_dict["failed_transmissions"].append(station.failed_transmissions)
        result_dict["normalized_ffp"].append(normalized_ffp)
        result_dict["normalized_cot"].append(normalized_cot)
        result_dict["fbe_version"].append(station.get_fbe_version())


def run_simulation(stations_list, simulation_time, debug_fun=None, plot_params=None, is_separate_run=False):
    result_dict = runner(simulation_time, stations_list) if not is_separate_run else separate_runner(stations_list,
                                                                                                     simulation_time)
    df = pd.DataFrame.from_dict(result_dict)
    print(df)
    if plot_params is not None:
        process_results(df, plot_params)


def runner(simulation_time, stations_list):
    result_dict = {"station_name": [],
                   "air_time": [],
                   "cot": [],
                   "normalized_cot": [],
                   "ffp": [],
                   "normalized_ffp": [],
                   "normalized_air_time": [],
                   "successful_transmissions": [],
                   "failed_transmissions": [],
                   "fbe_version": []}
    total_run_number = get_total_run_number(stations_list)
    print(f'Total run number: {total_run_number}')
    for run_number in range(total_run_number):
        print(f'Running simulation:{run_number + 1}/{total_run_number}')
        env = simpy.Environment()
        channel = coexistanceSimpy.Channel(None, simpy.Resource(env, capacity=1), 0, 0, None, None, None, None, None,
                                           simulation_time)
        current_run_stations_list = get_stations_for_current_run(stations_list, run_number)
        set_env_channel(current_run_stations_list, env, channel)
        env.run(until=simulation_time)
        collect_results(current_run_stations_list, result_dict, simulation_time)
        current_run_stations_list.clear()
    return result_dict


def separate_runner(stations_list, simulation_time):
    result_dict = {"station_name": [],
                   "air_time": [],
                   "cot": [],
                   "normalized_cot": [],
                   "ffp": [],
                   "normalized_ffp": [],
                   "normalized_air_time": [],
                   "successful_transmissions": [],
                   "failed_transmissions": [],
                   "fbe_version": []}
    for stations in stations_list:
        print(f'Running stations separately. Current number of stations: {len(stations)}')
        for station in stations:
            print(f'Current station: {station.name}')
            env = simpy.Environment()
            channel = coexistanceSimpy.Channel(None, simpy.Resource(env, capacity=1), 0, 0, None, None, None, None,
                                               None,
                                               simulation_time)
            set_env_channel([station], env, channel)
            env.run(until=simulation_time)
        collect_results(stations, result_dict, simulation_time)
    return result_dict


def process_results(df, plot_params: PlotParams):
    axis_label_zip, multiple_plots = get_axis_label_zip(plot_params)
    for x_axis, y_axis, x_label, y_label in axis_label_zip:
        fig, ax = plt.subplots()
        i = 0
        if x_axis == 'station_name':
            ax = df.plot(ax=ax, kind='bar', x=x_axis, y=y_axis)
        else:
            for key, grp in df.groupby(["station_name"]):
                ax = grp.plot(ax=ax, marker=marks[i], x=x_axis, y=y_axis, label=key, c=colors[i])
                i += 1

        ax.set(xlabel=x_label, ylabel=y_label, title=plot_params.title)
        ax.set_ylim(bottom=0)
        plt.tight_layout()
        path_to_save = None
        if plot_params.folder_name is None:
            path_to_save = os.getcwd() + '/val_output/images/'
        else:
            path_to_save = os.getcwd() + f'/val_output/images/{plot_params.folder_name}'
            if not os.path.exists(path_to_save):
                os.makedirs(path_to_save)
            path_to_save += '/'
        if multiple_plots:
            path_to_save += plot_params.file_name + f'_{x_axis}_{y_axis}'
        else:
            path_to_save += plot_params.file_name
        plt.savefig(path_to_save)
        plt.savefig(path_to_save + '.svg')
        plt.close()


def plot_fairness(df: pd.DataFrame, plot_params: PlotParams):
    axis_label_zip = get_axis_label_zip(plot_params)
    i = 0
    for key, grp in df.groupby(["fbe_version"]):
        ax = grp.plot(ax=ax, marker=marks)


def get_axis_label_zip(plot_params: PlotParams):
    x_axis_list = plot_params.x_axis.split(';')
    y_axis_list = plot_params.y_axis.split(';')
    x_label_list = plot_params.x_label.split(';')
    y_label_list = plot_params.y_label.split(';')
    max_list_size = max(len(x_axis_list), len(y_axis_list), len(x_label_list), len(y_label_list))
    last_x_axis = x_axis_list[-1]
    last_y_axis = y_axis_list[-1]
    last_x_label = x_label_list[-1]
    last_y_label = y_label_list[-1]
    for i in range(max_list_size - len(x_axis_list)):
        x_axis_list.append(last_x_axis)
    for i in range(max_list_size - len(y_axis_list)):
        y_axis_list.append(last_y_axis)
    for i in range(max_list_size - len(x_label_list)):
        x_label_list.append(last_x_label)
    for i in range(max_list_size - len(y_label_list)):
        y_label_list.append(last_y_label)
    multiple_plots = max_list_size > 1
    return zip(x_axis_list, y_axis_list, x_label_list, y_label_list), multiple_plots


def run_test(json_path):
    station_list, simulation_time, plot_params, is_separate_run = get_scenario_directly_from_json(json_path)
    run_simulation(station_list, simulation_time, plot_params=plot_params, is_separate_run=is_separate_run)


class SimulationRunnerWorker(QThread):
    debug_signal = pyqtSignal(str)
    stations_list = None
    simulation_time = None

    def run(self) -> None:
        run_simulation(self.stations_list, self.simulation_time, None)

    def raise_signal(self, message):
        self.debug_signal.emit(message)

    def set_simulation_params(self, stations_list, simulation_time):
        self.stations_list = stations_list
        self.simulation_time = simulation_time


if __name__ == '__main__':
    result_dict = {"station_name": ['name', 'name2'],
                   "air_time": [1, 2],
                   "cot": [1, 2],
                   "normalized_cot": [1, 2],
                   "ffp": [1, 2],
                   "normalized_ffp": [1, 2],
                   "normalized_air_time": [1, 2],
                   "successful_transmissions": [1, 2],
                   "failed_transmissions": [1, 2],
                   "fbe_version": [FBEVersion.STANDARD_FBE, FBEVersion.STANDARD_FBE]}
    df = pd.DataFrame.from_dict(result_dict)
    df = df.groupby(["fbe_version", "air_time"])
    dicst = {}
    for key, grp in df:
        print(key)
        dicst[key] = grp.to_dict()

    print(dicst)
