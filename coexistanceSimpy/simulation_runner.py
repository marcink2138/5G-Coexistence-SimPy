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
    standard_fbe_stations = []
    fixed_muting_fbe_stations = []
    random_muting_fbe_stations = []
    floating_fbe_stations = []
    db_fbe_stations = []
    group_stations_by_version(db_fbe_stations, fixed_muting_fbe_stations, floating_fbe_stations,
                              random_muting_fbe_stations, standard_fbe_stations, stations_list)
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
        fairness, summary_air_time = calculate_fairness_and_summary_air_time_wrapper(station.get_fbe_version(),
                                                                                     db_fbe_stations,
                                                                                     fixed_muting_fbe_stations,
                                                                                     floating_fbe_stations,
                                                                                     random_muting_fbe_stations,
                                                                                     standard_fbe_stations)
        result_dict["fairness"].append(fairness)
        result_dict["summary_air_time"].append(summary_air_time)


def calculate_fairness_and_summary_air_time_wrapper(fbe_version, db_fbe_stations, fixed_muting_fbe_stations,
                                                    floating_fbe_stations,
                                                    random_muting_fbe_stations, standard_fbe_stations):
    if fbe_version == FBEVersion.STANDARD_FBE:
        return calculate_fairness_and_summary_air_time(standard_fbe_stations)
    elif fbe_version == FBEVersion.FIXED_MUTING_FBE:
        return calculate_fairness_and_summary_air_time(fixed_muting_fbe_stations)
    elif fbe_version == FBEVersion.RANDOM_MUTING_FBE:
        return calculate_fairness_and_summary_air_time(random_muting_fbe_stations)
    elif fbe_version == FBEVersion.FLOATING_FBE:
        return calculate_fairness_and_summary_air_time(floating_fbe_stations)
    elif fbe_version == FBEVersion.DETERMINISTIC_BACKOFF_FBE:
        return calculate_fairness_and_summary_air_time(db_fbe_stations)


def calculate_fairness_and_summary_air_time(grouped_stations):
    fairness_nominator = 0
    fairness_denominator = 0
    summary_air_time = 0
    n = 0
    for stations in grouped_stations:
        summary_air_time += stations.air_time
        fairness_nominator += stations.air_time
        fairness_denominator += stations.air_time ** 2
        n += 1
    fairness = 0
    if fairness_denominator != 0:
        fairness = round((fairness_nominator ** 2) / (n * fairness_denominator), 4)
    return fairness, summary_air_time


def group_stations_by_version(db_fbe_stations, fixed_muting_fbe_stations, floating_fbe_stations,
                              random_muting_fbe_stations, standard_fbe_stations, stations_list):
    for station in stations_list:
        if station.get_fbe_version() == FBEVersion.STANDARD_FBE:
            standard_fbe_stations.append(station)
        elif station.get_fbe_version() == FBEVersion.FIXED_MUTING_FBE:
            fixed_muting_fbe_stations.append(station)
        elif station.get_fbe_version() == FBEVersion.RANDOM_MUTING_FBE:
            random_muting_fbe_stations.append(station)
        elif station.get_fbe_version() == FBEVersion.FLOATING_FBE:
            floating_fbe_stations.append(station)
        elif station.get_fbe_version() == FBEVersion.DETERMINISTIC_BACKOFF_FBE:
            db_fbe_stations.append(station)


def run_simulation(stations_list, simulation_time, debug_fun=None, plot_params=None, is_separate_run=False):
    result_dict, event_dict_list, db_fbe_backoff_changes_dict_list = runner(simulation_time, stations_list) \
        if not is_separate_run else separate_runner(stations_list, simulation_time)

    df = pd.DataFrame.from_dict(result_dict)
    if plot_params is not None:
        process_results(df, plot_params)
        path_to_folder = get_path_to_folder(plot_params)
        df.to_csv(path_to_folder + plot_params.file_name + "_df.csv")
        events_df = merge_dicts_into_df(event_dict_list)
        events_df.to_csv(path_to_folder + plot_params.file_name + "_events.csv")
        db_fbe_backoff_changes_df = merge_dicts_into_df(db_fbe_backoff_changes_dict_list)
        db_fbe_backoff_changes_df.to_csv(path_to_folder + plot_params.file_name + "_db_fbe_backoff.csv")


def merge_dicts_into_df(dict_list):
    df = None
    for result_dict in dict_list:
        if df is None:
            df = pd.DataFrame.from_dict(result_dict)
        else:
            df = pd.concat([df, pd.DataFrame.from_dict(result_dict)])
    return df


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
                   "fbe_version": [],
                   "fairness": [],
                   "summary_air_time": []}
    event_dict_list = []
    db_fbe_backoff_changes_dict_list = []
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
        event_dict_list.append(channel.event_dict)
        db_fbe_backoff_changes_dict_list.append(channel.db_fbe_backoff_change_dict)
    return result_dict, event_dict_list, db_fbe_backoff_changes_dict_list


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
                   "fbe_version": [],
                   "fairness": [],
                   "summary_air_time": []}
    event_dict_list = []
    db_fbe_backoff_changes_dict_list = []
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
            event_dict_list.append(channel.event_dict)
            db_fbe_backoff_changes_dict_list.append(channel.db_fbe_backoff_change_dict)
        collect_results(stations, result_dict, simulation_time)
    return result_dict, event_dict_list, db_fbe_backoff_changes_dict_list


# def process_results(df, plot_params: PlotParams):
#     axis_label_zip, multiple_plots = get_axis_label_zip(plot_params)
#     for x_axis, y_axis, x_label, y_label in axis_label_zip:
#         fig, ax = plt.subplots()
#         i = 0
#         if x_axis == 'station_name':
#             ax = df.plot(ax=ax, kind='bar', x=x_axis, y=y_axis)
#         else:
#             for key, grp in df.groupby(["station_name"]):
#                 ax = grp.plot(ax=ax, marker=marks[i], x=x_axis, y=y_axis, label=key, c=colors[i])
#                 i += 1
#
#         ax.set(xlabel=x_label, ylabel=y_label, title=plot_params.title)
#         ax.set_ylim(bottom=0)
#         plt.tight_layout()
#         path_to_save = None
#         if plot_params.folder_name is None:
#             path_to_save = os.getcwd() + '/val_output/images/'
#         else:
#             path_to_save = os.getcwd() + f'/val_output/images/{plot_params.folder_name}'
#             if not os.path.exists(path_to_save):
#                 os.makedirs(path_to_save)
#             path_to_save += '/'
#         if multiple_plots:
#             path_to_save += plot_params.file_name + f'_{x_axis}_{y_axis}'
#         else:
#             path_to_save += plot_params.file_name
#         plt.savefig(path_to_save)
#         plt.savefig(path_to_save + '.svg')
#         plt.close()

def process_results(df, plot_params: PlotParams):
    if plot_params.all_in_one is not None:
        plot_all_in_one(df, plot_params)
    if plot_params.fairness is not None:
        plot_fairness(df, plot_params)
    if plot_params.summary_airtime is not None:
        plot_summary_airtime(df, plot_params)
    if plot_params.separate_plots is not None:
        plot_separate(df, plot_params)


def plot_separate(df: pd.DataFrame, plot_params: PlotParams):
    axis_label_zip = zip_plot_params(plot_params.all_in_one["x_axis"], plot_params.all_in_one["x_label"],
                                     plot_params.all_in_one["y_axis"], plot_params.all_in_one["y_label"])
    plot_num = 0
    for x_axis, x_label, y_axis, y_label in axis_label_zip:

        for key, grp in df.groupby(["station_name"]):
            ax = grp.plot(marker=marks[0], x=x_axis, y=y_axis, label=key, c=colors[0])
            ax.set(xlabel=x_label, ylabel=y_label, title=plot_params.all_in_one["title"])
            if y_axis == "normalized_airtime":
                ax.set_ylim(bottom=0)
            plt.tight_layout()
            save_plot(plot_params, f"{key}", plot_num)
        plot_num += 1


def plot_all_in_one(df: pd.DataFrame, plot_params: PlotParams):
    axis_label_zip = zip_plot_params(plot_params.all_in_one["x_axis"], plot_params.all_in_one["x_label"],
                                     plot_params.all_in_one["y_axis"], plot_params.all_in_one["y_label"])
    plot_num = 0
    for x_axis, x_label, y_axis, y_label in axis_label_zip:
        fig, ax = plt.subplots()
        i = 0

        for key, grp in df.groupby(["station_name"]):
            ax = grp.plot(ax=ax, marker=marks[i], x=x_axis, y=y_axis, label=key, c=colors[i])
            i += 1

        ax.set(xlabel=x_label, ylabel=y_label, title=plot_params.all_in_one["title"])
        if y_axis == "normalized_airtime":
            ax.set_ylim(bottom=0)
        plt.tight_layout()
        save_plot(plot_params, "all_in_one", plot_num)
        plot_num += 1


def plot_fairness(df: pd.DataFrame, plot_params: PlotParams):
    x_axis_label_zip = zip_plot_params(plot_params.fairness["x_axis"], plot_params.fairness["x_label"])
    plot_num = 0
    for x_axis, x_label in x_axis_label_zip:
        fig, ax = plt.subplots()
        i = 0
        for key, grp in df.groupby(["fbe_version"]):
            ax = grp.plot(ax=ax, marker=marks[i], x=x_axis, y='fairness', label=key, c=colors[i])
            i += 1
        ax.set(xlabel=x_label, ylabel='Fairness', title=plot_params.fairness["title"])
        ax.set_ylim(bottom=0)
        plt.tight_layout()
        save_plot(plot_params, "fairness", plot_num)
        plot_num += 1


def plot_summary_airtime(df: pd.DataFrame, plot_params: PlotParams):
    x_axis_label_zip = zip_plot_params(plot_params.summary_airtime["x_axis"], plot_params.summary_airtime["x_label"])
    plot_num = 0
    for x_axis, x_label in x_axis_label_zip:
        fig, ax = plt.subplots()
        i = 0
        for key, grp in df.groupby(["fbe_version"]):
            ax = grp.plot(ax=ax, marker=marks[i], x=x_axis, y='summary_air_time', label=key, c=colors[i])
            i += 1
        ax.set(xlabel=x_label, ylabel='Summary Airtime', title=plot_params.summary_airtime["title"])
        plt.tight_layout()
        save_plot(plot_params, "summary_airtime", plot_num)
        plot_num += 1


def get_path_to_folder(plot_params: PlotParams):
    path_to_folder = None
    if plot_params.folder_name is None:
        path_to_folder = os.getcwd() + '/val_output/images/'
    else:
        path_to_folder = os.getcwd() + f'/val_output/images/{plot_params.folder_name}'
        if not os.path.exists(path_to_folder):
            os.makedirs(path_to_folder)
        path_to_folder += '/'
    return path_to_folder


def save_plot(plot_params: PlotParams, plot_type, plot_num):
    path_to_save = get_path_to_folder(plot_params)

    if plot_num > 0:
        path_to_save += plot_params.file_name + "_" + plot_type + "_" + str(plot_num)
    else:
        path_to_save += plot_params.file_name + "_" + plot_type
    plt.savefig(path_to_save)
    plt.savefig(path_to_save + '.svg')
    plt.savefig(path_to_save + '.png')
    plt.close()


def zip_plot_params(*params):
    max_size = 0
    params_outer_list = []
    for param in params:
        params_list = param.split(';')
        params_list_len = len(params_list)
        if params_list_len > max_size:
            max_size = params_list_len
        params_outer_list.append(params_list)

    for params_list in params_outer_list:
        if len(params_list) < max_size:
            last_value = params_list[-1]
            for i in range(max_size - len(params_list)):
                params_list.append(last_value)

    return zip(*params_outer_list)


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
    a = 10 ** 100
    b = 10 ** 90
    print(a / b)
