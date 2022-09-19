import os

import duckdb
import pandas as pd
import simpy
from matplotlib import pyplot as plt
from logger_util import enable_logging, log

import coexistanceSimpy
from coexistanceSimpy import FBEVersion
from coexistanceSimpy.scenario_creator_helper import OutputParams
from coexistanceSimpy.scenario_creator_helper import get_scenario_directly_from_json
from coexistanceSimpy.scenario_creator_helper import get_station_list_from_json_lists

marks = ['o', 'v', 's', 'P', '*', 'x', '+']
colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k']
max_ffp = 10000
log_name = "default"


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
        station.set_log_name(log_name)


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


def run_simulation(simulation_time, scenario_runs=1, output_params=None, is_separate_run=False):
    path_to_folder = get_path_to_folder(output_params)
    if output_params.enable_logging:
        enable_logging(output_params.file_name, path_to_folder)
        global log_name
        log_name = output_params.file_name
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
    print(f"Test name: {output_params.file_name} in folder: {output_params.folder_name}")
    log(f"Test name: {output_params.file_name} in folder: {output_params.folder_name}", log_name)
    for i in range(scenario_runs):
        print(f"Running scenario : {i + 1}/{scenario_runs}")
        log(f"Running scenario : {i + 1}/{scenario_runs}", log_name)
        stations_list = get_station_list_from_json_lists()
        if is_separate_run:
            separate_runner(stations_list, simulation_time, result_dict, event_dict_list,
                            db_fbe_backoff_changes_dict_list)
        else:
            runner(simulation_time, stations_list, result_dict, event_dict_list, db_fbe_backoff_changes_dict_list)

    df = pd.DataFrame.from_dict(result_dict)
    if scenario_runs > 1:
        df = prepare_dataframe_after_many_scenario_runs(df)
    if output_params is not None:
        process_results(df, output_params)
        sim_results_path = path_to_folder + output_params.file_name + "_df.csv"
        log(f"Saving simulation results to:{sim_results_path} ...", log_name)
        df.to_csv(sim_results_path)
        events_df = merge_dicts_into_df(event_dict_list)
        events_path = path_to_folder + output_params.file_name + "_events.csv"
        log(f"Saving simulation events to:{events_path} ...", log_name)
        events_df.to_csv(events_path)
        db_fbe_backoff_changes_df = merge_dicts_into_df(db_fbe_backoff_changes_dict_list)
        db_fbe_backoff_changes_path = path_to_folder + output_params.file_name + "_db_fbe_backoff.csv"
        log(f"Saving db fbe backoff changes to: {db_fbe_backoff_changes_path} ...", log_name)
        db_fbe_backoff_changes_df.to_csv(db_fbe_backoff_changes_path)


def prepare_dataframe_after_many_scenario_runs(df):
    return duckdb.query("SELECT station_name, avg(air_time) as air_time, "
                        "cot, normalized_cot, "
                        "ffp, normalized_ffp, "
                        "avg(normalized_air_time) as normalized_air_time, "
                        "avg(successful_transmissions) as successful_transmissions, "
                        "avg(failed_transmissions) as failed_transmissions, "
                        "fbe_version, avg(fairness) as fairness, "
                        "avg(summary_air_time) as summary_air_time "
                        "FROM df "
                        "GROUP BY station_name, cot, normalized_cot,ffp, normalized_ffp,fbe_version").df()


def merge_dicts_into_df(dict_list):
    df = None
    for result_dict in dict_list:
        if df is None:
            df = pd.DataFrame.from_dict(result_dict)
        else:
            df = pd.concat([df, pd.DataFrame.from_dict(result_dict)])
    return df


def runner(simulation_time, stations_list, result_dict, event_dict_list, db_fbe_backoff_changes_dict_list):
    total_run_number = get_total_run_number(stations_list)
    print(f'Total run number: {total_run_number}')
    for run_number in range(total_run_number):
        print(f'Running simulation:{run_number + 1}/{total_run_number}')
        log(f'Running simulation:{run_number + 1}/{total_run_number}', log_name)
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


def separate_runner(stations_list, simulation_time, result_dict, event_dict_list, db_fbe_backoff_changes_dict_list):
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


def process_results(df, output_params: OutputParams):
    log("Processing results ...", log_name)
    if output_params.all_in_one is not None:
        plot_all_in_one(df, output_params)
    if output_params.fairness is not None:
        plot_fairness(df, output_params)
    if output_params.summary_airtime is not None:
        plot_summary_airtime(df, output_params)
    if output_params.separate_plots is not None:
        plot_separate(df, output_params)


def plot_separate(df: pd.DataFrame, output_params: OutputParams):
    axis_label_zip = zip_plot_params(output_params.all_in_one["x_axis"], output_params.all_in_one["x_label"],
                                     output_params.all_in_one["y_axis"], output_params.all_in_one["y_label"])
    plot_num = 0
    for x_axis, x_label, y_axis, y_label in axis_label_zip:

        for key, grp in df.groupby(["station_name"]):
            ax = grp.plot(marker=marks[0], x=x_axis, y=y_axis, label=key, c=colors[0])
            ax.set(xlabel=x_label, ylabel=y_label, title=output_params.all_in_one["title"])
            if y_axis == "normalized_airtime":
                ax.set_ylim(bottom=0)
            plt.tight_layout()
            save_plot(output_params, f"{key}", plot_num)
        plot_num += 1


def plot_all_in_one(df: pd.DataFrame, output_params: OutputParams):
    axis_label_zip = zip_plot_params(output_params.all_in_one["x_axis"], output_params.all_in_one["x_label"],
                                     output_params.all_in_one["y_axis"], output_params.all_in_one["y_label"])
    plot_num = 0
    for x_axis, x_label, y_axis, y_label in axis_label_zip:
        fig, ax = plt.subplots()
        i = 0

        for key, grp in df.groupby(["station_name"]):
            ax = grp.plot(ax=ax, marker=marks[i], x=x_axis, y=y_axis, label=key, c=colors[i])
            i += 1

        ax.set(xlabel=x_label, ylabel=y_label, title=output_params.all_in_one["title"])
        if y_axis == "normalized_airtime":
            ax.set_ylim(bottom=0)
        plt.tight_layout()
        save_plot(output_params, "all_in_one", plot_num)
        plot_num += 1


def plot_fairness(df: pd.DataFrame, output_params: OutputParams):
    x_axis_label_zip = zip_plot_params(output_params.fairness["x_axis"], output_params.fairness["x_label"])
    plot_num = 0
    for x_axis, x_label in x_axis_label_zip:
        fig, ax = plt.subplots()
        i = 0
        for key, grp in df.groupby(["fbe_version"]):
            ax = grp.plot(ax=ax, marker=marks[i], x=x_axis, y='fairness', label=key, c=colors[i])
            i += 1
        ax.set(xlabel=x_label, ylabel='Fairness', title=output_params.fairness["title"])
        ax.set_ylim(bottom=0)
        plt.tight_layout()
        save_plot(output_params, "fairness", plot_num)
        plot_num += 1


def plot_summary_airtime(df: pd.DataFrame, output_params: OutputParams):
    x_axis_label_zip = zip_plot_params(output_params.summary_airtime["x_axis"],
                                       output_params.summary_airtime["x_label"])
    plot_num = 0
    for x_axis, x_label in x_axis_label_zip:
        fig, ax = plt.subplots()
        i = 0
        for key, grp in df.groupby(["fbe_version"]):
            ax = grp.plot(ax=ax, marker=marks[i], x=x_axis, y='summary_air_time', label=key, c=colors[i])
            i += 1
        ax.set(xlabel=x_label, ylabel='Summary Airtime', title=output_params.summary_airtime["title"])
        plt.tight_layout()
        save_plot(output_params, "summary_airtime", plot_num)
        plot_num += 1


def get_path_to_folder(output_params: OutputParams):
    path_to_folder = None
    if output_params.folder_name is None:
        path_to_folder = os.getcwd() + '/val_output/images/'
    else:
        path_to_folder = os.getcwd() + f'/val_output/images/{output_params.folder_name}'
        if not os.path.exists(path_to_folder):
            os.makedirs(path_to_folder)
        path_to_folder += '/'
    return path_to_folder


def save_plot(output_params: OutputParams, plot_type, plot_num):
    path_to_save = get_path_to_folder(output_params)

    if plot_num > 0:
        path_to_save += output_params.file_name + "_" + plot_type + "_" + str(plot_num)
    else:
        path_to_save += output_params.file_name + "_" + plot_type
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


def run_test(json_path):
    simulation_time, output_params, is_separate_run, scenario_runs = get_scenario_directly_from_json(
        json_path)

    run_simulation(simulation_time, output_params=output_params, is_separate_run=is_separate_run,
                   scenario_runs=scenario_runs)

