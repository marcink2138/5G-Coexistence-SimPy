import decimal
import os

import duckdb
import pandas as pd
import simpy
from matplotlib import pyplot as plt
from coexistanceSimpy.logger_util import enable_logging, log
import numpy as np

import coexistanceSimpy
from coexistanceSimpy import FBEVersion, EventType
from coexistanceSimpy.scenario_creator_helper import OutputParams
from coexistanceSimpy.scenario_creator_helper import get_scenario_directly_from_json
from coexistanceSimpy.scenario_creator_helper import get_station_list_from_json_lists
import scipy.stats as st
from decimal import *
from coexistanceSimpy.directory_manager_util import try_to_create_directory

getcontext().prec = 12
getcontext().rounding = decimal.ROUND_HALF_EVEN

marks = ['o', 'v', 's', 'P', '*', 'x', '+']
colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k']
max_ffp = 10000
log_name = "default"
NORMALIZED_COT = 'normalized_cot'
NORMALIZED_FFP = 'normalized_ffp'
NORMALIZED_AIRTIME = 'normalized_air_time'
FAIRNESS = 'fairness'
VERSIONS_WITH_CI = [FBEVersion.RANDOM_MUTING_FBE, FBEVersion.FLOATING_FBE]


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
        normalized_air_time = float(Decimal(station.air_time) / Decimal(simulation_time))
        normalized_ffp = float(Decimal(station.timers.ffp) / Decimal(max_ffp))
        normalized_cot = float(Decimal(station.timers.cot) / Decimal(station.timers.ffp))
        result_dict["normalized_air_time"].append(normalized_air_time)
        result_dict["successful_transmissions"].append(station.succeeded_transmissions)
        result_dict["failed_transmissions"].append(station.failed_transmissions)
        result_dict["normalized_ffp"].append(normalized_ffp)
        result_dict["normalized_cot"].append(normalized_cot)
        result_dict["fbe_version"].append(station.get_fbe_version().name)
        result_dict["offset"].append(station.offset)
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
        # fairness = round((fairness_nominator ** 2) / (n * fairness_denominator), 4)
        fairness = float(Decimal(fairness_nominator ** 2) / Decimal(n * fairness_denominator))
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


def run_simulation(simulation_params):
    output_params = simulation_params.output_params
    scenario_runs = simulation_params.scenario_runs
    is_separate_run = simulation_params.is_separate_run
    simulation_time = simulation_params.simulation_time
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
                   "summary_air_time": [],
                   "offset": []}
    event_dict_list = []
    db_fbe_backoff_changes_dict_list = []
    db_fbe_interrupt_counter_dict_list = []
    print(f"Test name: {output_params.file_name} in folder: {output_params.folder_name}")
    log(f"Test name: {output_params.file_name} in folder: {output_params.folder_name}", log_name)
    for i in range(scenario_runs):
        print(f"Running scenario : {i + 1}/{scenario_runs}")
        log(f"Running scenario : {i + 1}/{scenario_runs}", log_name)
        stations_list = get_station_list_from_json_lists()
        if is_separate_run:
            separate_runner(stations_list, simulation_time, result_dict, event_dict_list,
                            db_fbe_backoff_changes_dict_list, db_fbe_interrupt_counter_dict_list)
        else:
            runner(simulation_time, stations_list, result_dict,
                   event_dict_list, db_fbe_backoff_changes_dict_list, db_fbe_interrupt_counter_dict_list)

    df_full = pd.DataFrame.from_dict(result_dict)
    df_full = duckdb.query("SELECT * FROM df_full ORDER BY cot, station_name").df()
    df = prepare_dataframe(df_full)
    if output_params is not None:
        process_results(df, output_params, scenario_runs)
        sim_results_path = path_to_folder + output_params.file_name + "_df.csv"
        log(f"Saving simulation results to:{sim_results_path} ...", log_name)
        df.to_csv(sim_results_path)
        df_full.to_csv(path_to_folder + output_params.file_name + "_df_full.csv")
        events_df = merge_dicts_into_df(event_dict_list)
        events_path = path_to_folder + output_params.file_name + "_events.csv"
        log(f"Saving simulation events to:{events_path} ...", log_name)
        events_df.to_csv(events_path)
        if scenario_runs > 1:
            first_run_events = int(len(event_dict_list) / scenario_runs)
            log(f"Number of scenario runs is larger than one. Plotting events from first run only ...", log_name)
            plot_events(event_dict_list[0:first_run_events], output_params)
            return
        else:
            log("Plotting events ...", log_name)
            plot_events(event_dict_list, output_params)
        if simulation_params.contains_db_fbe:
            db_fbe_interrupt_df = merge_dicts_into_df(db_fbe_interrupt_counter_dict_list)
            db_fbe_interrupt_df_path = path_to_folder + output_params.file_name + "_db_fbe_interrupt.csv"
            db_fbe_backoff_changes_df = merge_dicts_into_df(db_fbe_backoff_changes_dict_list)
            db_fbe_backoff_changes_path = path_to_folder + output_params.file_name + "_db_fbe_backoff.csv"
            log(f"Saving db fbe backoff changes to: {db_fbe_backoff_changes_path} ...", log_name)
            db_fbe_backoff_changes_df.to_csv(db_fbe_backoff_changes_path)
            log(f"Saving db fbe interrupt counter changes to: {db_fbe_interrupt_df_path} ...", log_name)
            db_fbe_interrupt_df.to_csv(db_fbe_interrupt_df_path)
            log("Plotting db fbe backoff changes", log_name)
            plot_db_fbe_backoff_changes(db_fbe_backoff_changes_dict_list, output_params)
            plot_db_fbe_backoff_changes(db_fbe_backoff_changes_dict_list, output_params, False)
            plot_interrupt_counter_changes(db_fbe_interrupt_counter_dict_list, output_params)


def prepare_dataframe(df):
    return duckdb.query("SELECT station_name, avg(air_time) as air_time, "
                        "cot, normalized_cot, "
                        "ffp, normalized_ffp, "
                        "avg(normalized_air_time) as normalized_air_time, "
                        "avg(successful_transmissions) as successful_transmissions, "
                        "avg(failed_transmissions) as failed_transmissions, "
                        "fbe_version, avg(fairness) as fairness, "
                        "avg(summary_air_time) as summary_air_time,"
                        "stddev_samp(normalized_air_time) as normalized_air_time_std,"
                        "stddev_samp(successful_transmissions) as successful_transmissions_std,"
                        "stddev_samp(failed_transmissions) as failed_transmissions_std "
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


def log_run_stations_params(stations_list):
    for station in stations_list:
        log(repr(station), log_name)


def runner(simulation_time, stations_list, result_dict, event_dict_list, db_fbe_backoff_changes_dict_list,
           db_fbe_interrupt_changes_dict_list):
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
        log_run_stations_params(current_run_stations_list)
        env.run(until=simulation_time)
        collect_results(current_run_stations_list, result_dict, simulation_time)
        current_run_stations_list.clear()
        event_dict_list.append(channel.event_dict)
        db_fbe_backoff_changes_dict_list.append(channel.db_fbe_backoff_change_dict)
        db_fbe_interrupt_changes_dict_list.append(channel.db_interrupt_counter)


def separate_runner(stations_list, simulation_time, result_dict, event_dict_list, db_fbe_backoff_changes_dict_list,
                    db_fbe_interrupt_changes_dict_list):
    for stations in stations_list:
        print(f'Running stations separately. Current number of stations: {len(stations)}')
        for station in stations:
            print(f'Current station: {station.name}')
            env = simpy.Environment()
            channel = coexistanceSimpy.Channel(None, simpy.Resource(env, capacity=1), 0, 0, None, None, None, None,
                                               None,
                                               simulation_time)
            log(repr(station), log_name)
            set_env_channel([station], env, channel)
            env.run(until=simulation_time)
            event_dict_list.append(channel.event_dict)
            db_fbe_backoff_changes_dict_list.append(channel.db_fbe_backoff_change_dict)
            db_fbe_interrupt_changes_dict_list.append(channel.db_interrupt_counter)
        collect_results(stations, result_dict, simulation_time)


def process_results(df, output_params: OutputParams, scenario_runs):
    log("Processing results ...", log_name)
    if output_params.all_in_one is not None:
        plot_all_in_one(df, output_params, scenario_runs)
    if output_params.fairness is not None:
        plot_fairness(df, output_params)
    if output_params.summary_airtime is not None:
        plot_summary_airtime(df, output_params)
    if output_params.separate_plots is not None:
        plot_separate(df, output_params)


def plot_db_fbe_backoff_changes(db_fbe_backoff_changes_dict_list, output_params, init_plot=True):
    for run_number, db_fbe_backoff_changes_dict in enumerate(db_fbe_backoff_changes_dict_list, start=1):
        df = pd.DataFrame.from_dict(db_fbe_backoff_changes_dict)
        if init_plot:
            df = duckdb.query("SELECT * FROM df WHERE is_init = true").df()
        else:
            df = duckdb.query("SELECT * FROM df").df()
        fig, ax = plt.subplots()
        i = 0
        for key, grp in df.groupby(["station_name"]):
            if init_plot:
                ax = grp.plot(ax=ax, x="time", y="backoff", label=key, c=colors[i], drawstyle="steps-post")
            else:
                ax = grp.plot(ax=ax, x="time", y="backoff", label=key, c=colors[i])
            i += 1

        ax.set(xlabel="time", ylabel="backoff")
        plt.tight_layout()
        plot_type = "backoff_changes_init" if init_plot else "backoff_changes"
        save_plot(output_params, plot_type, run_number)


def plot_interrupt_counter_changes(db_fbe_interrupt_counter_changes_dict_list, output_params):
    for run_number, db_fbe_backoff_changes_dict in enumerate(db_fbe_interrupt_counter_changes_dict_list, start=1):
        df = pd.DataFrame.from_dict(db_fbe_backoff_changes_dict)
        df = duckdb.query("SELECT * FROM df WHERE time between 0 AND 1000000").df()
        fig, ax = plt.subplots()
        i = 0
        for key, grp in df.groupby(["station_name"]):
            ax = grp.plot(ax=ax, x="time", y="value", label=key, c=colors[i], drawstyle="steps-post")
            i += 1

        ax.set(xlabel="time", ylabel="interrupt counter")
        plt.tight_layout()
        plot_type = "interrupt_counter_changes"
        save_plot(output_params, plot_type, run_number)


def plot_events(events_dict_list, output_params):
    run_num = len(events_dict_list)
    fig, axes = plt.subplots(nrows=run_num, ncols=1, constrained_layout=False, tight_layout=True)
    for ax, events_dict in zip(axes, reversed(events_dict_list)):
        df = pd.DataFrame.from_dict(events_dict).drop_duplicates(subset=['event_type', 'time']).tail(32)
        events = df["event_type"].tolist()
        station_names = df["station_name"].tolist()
        unique_station_names = duckdb.query("SELECT DISTINCT station_name FROM df").df()["station_name"].tolist()
        station_idx_name_dict = {}
        # for station_idx, unique_station_name in enumerate(unique_station_names, start=1):
        #     station_idx_name_dict[unique_station_name] = station_idx
        for unique_station_name in unique_station_names:
            station_idx_name_dict[unique_station_name] = unique_station_name[-1]

        # fig, ax = plt.subplots()
        # ax.axes.get_yaxis().set_visible(False)
        # ax.set_aspect(1)
        x = 0
        for event, station_name in zip(events, station_names):
            x1 = [x, x + 1]
            y1 = [0, 0]
            y2 = [1, 1]
            if event == EventType.CCA_INTERRUPTED.name:
                # plt.fill_between(x1, y1, y2=y2, color='red', edgecolor='black')
                pass
            elif event == EventType.CHANNEL_COLLISION.name:
                ax.fill_between(x1, y1, y2=y2, color='grey', edgecolor='black')
                ax.text(avg(x1[0], x1[1]), avg(y1[0], y2[0]), '-', horizontalalignment='center',
                        verticalalignment='center')
            else:
                ax.fill_between(x1, y1, y2=y2, color='green', edgecolor='black')
                idx = station_idx_name_dict.get(station_name)
                ax.text(avg(x1[0], x1[1]), avg(y1[0], y2[0]), idx, horizontalalignment='center',
                        verticalalignment='center')
            x += 1
        ax.set_aspect(1)
        ax.set_yticks([0, 1])
        ax.set_xticks([0, 32])
        ax.set_xlim([0, 32])
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.set_ylabel(run_num)
        run_num -= 1
        # plt.yticks([0, 1])
    fig.tight_layout()
    # plt.ylim(0, 1)
    fig.supylabel("Simulation number")
    fig.supxlabel("Events")
    plot_type = "events"
    save_plot(output_params, plot_type, 0)


def avg(a, b):
    return (a + b) / 2.0


def plot_separate(df: pd.DataFrame, output_params: OutputParams):
    axis_label_zip = zip_plot_params(output_params.all_in_one["x_axis"], output_params.all_in_one["x_label"],
                                     output_params.all_in_one["y_axis"], output_params.all_in_one["y_label"],
                                     output_params.separate_plots.get("plot_file_name"))
    plot_num = 0
    is_ci_enabled = output_params.separate_plots[
        "is_ci_enabled"] if "is_ci_enabled" in output_params.separate_plots else False
    plot_file_name_before = ''
    for x_axis, x_label, y_axis, y_label, plot_file_name in axis_label_zip:
        if plot_file_name_before == plot_file_name:
            plot_num += 1
        else:
            plot_file_name_before = plot_file_name
        for key, grp in df.groupby(["station_name"]):
            ax = grp.plot(marker=".", x=x_axis, y=y_axis, label=key, c=colors[0], linestyle='--')
            ax.set(xlabel=x_label, ylabel=y_label, title=output_params.all_in_one["title"])
            if is_ci_enabled:
                x = grp[x_axis].tolist()
                y = grp[y_axis].tolist()
                add_confidence_interval(x, y, ax, colors[0])
            set_plot_ylim(ax, y_axis)
            plt.tight_layout()
            save_plot(output_params, f"{key}", plot_num, plot_file_name=plot_file_name)


def set_plot_ylim(ax: plt.Axes, y_axis: str):
    if y_axis in [NORMALIZED_COT, NORMALIZED_FFP, NORMALIZED_AIRTIME, FAIRNESS]:
        ax.set_ylim(bottom=0, top=1)
    else:
        ax.set_ylim(bottom=0)


def plot_all_in_one(df: pd.DataFrame, output_params: OutputParams, scenario_runs):
    axis_label_zip = zip_plot_params(output_params.all_in_one["x_axis"], output_params.all_in_one["x_label"],
                                     output_params.all_in_one["y_axis"], output_params.all_in_one["y_label"],
                                     output_params.all_in_one.get("plot_file_name"))
    plot_num = 0
    is_ci_enabled = output_params.all_in_one["is_ci_enabled"] if "is_ci_enabled" in output_params.all_in_one else False
    plot_file_name_before = ''
    for x_axis, x_label, y_axis, y_label, plot_file_name in axis_label_zip:
        fig, ax = plt.subplots()
        i = 0
        if plot_file_name_before == plot_file_name:
            plot_num += 1
        else:
            plot_file_name_before = plot_file_name
        for key, grp in df.groupby(["station_name"]):
            ax = grp.plot(ax=ax, marker=marks[i], x=x_axis, y=y_axis, label=key, c=colors[i], linestyle='--', markersize=5)
            version = grp["fbe_version"].tolist()[0]
            # if output_params.is_random or FBEVersion[version] in VERSIONS_WITH_CI:
            x = grp[x_axis].tolist()
            y = grp[y_axis].tolist()
            std = grp[y_axis+"_std"].tolist()
            add_confidence_interval(x, y, ax, colors[i], scenario_runs=scenario_runs, std=std)
            i += 1

        ax.set(xlabel=x_label, ylabel=y_label, title=output_params.all_in_one["title"])
        set_plot_ylim(ax, y_axis)
        plt.tight_layout()
        save_plot(output_params, "all_in_one", plot_num, plot_file_name=plot_file_name)


def add_confidence_interval(x, y, ax, color, scenario_runs=1, std=None):
    if scenario_runs < 2 and std is not None:
        return
    # ci = 1.96 * np.std(y) / np.sqrt(len(x))
    ci = std / np.sqrt(scenario_runs) * st.t.ppf(1 - 0.05 / 2, scenario_runs - 1)
    # ax.fill_between(x, (y - ci), (y + ci), color=color, alpha=.1)
    ax.errorbar(x, y, yerr=ci, fmt=" ", ecolor=color)


def plot_fairness(df: pd.DataFrame, output_params: OutputParams):
    x_axis_label_zip = zip_plot_params(output_params.fairness["x_axis"],
                                       output_params.fairness["x_label"],
                                       output_params.fairness.get("plot_file_name"))
    plot_num = 0
    plot_file_name_before = ''
    for x_axis, x_label, plot_file_name in x_axis_label_zip:
        if plot_file_name_before == plot_file_name:
            plot_num += 1
        else:
            plot_file_name_before = plot_file_name
        fig, ax = plt.subplots()
        i = 0
        for key, grp in df.groupby(["fbe_version"]):
            ax = grp.plot(ax=ax, marker="o", x=x_axis, y='fairness', c=colors[i], linestyle='--', markersize=3)
            i += 1
        ax.set(xlabel=x_label, ylabel='Fairness', title=output_params.fairness["title"])
        ax.get_legend().remove()
        set_plot_ylim(ax, FAIRNESS)
        plt.tight_layout()
        save_plot(output_params, "fairness", plot_num, plot_file_name)


def plot_summary_airtime(df: pd.DataFrame, output_params: OutputParams):
    x_axis_label_zip = zip_plot_params(output_params.summary_airtime["x_axis"],
                                       output_params.summary_airtime["x_label"],
                                       output_params.summary_airtime.get("plot_file_name"))
    plot_num = 0
    is_ci_enabled = output_params.summary_airtime[
        "is_ci_enabled"] if "is_ci_enabled" in output_params.summary_airtime else False
    plot_file_name_before = ''
    for x_axis, x_label, plot_file_name in x_axis_label_zip:
        if plot_file_name_before == plot_file_name:
            plot_num += 1
        else:
            plot_file_name_before = plot_file_name
        fig, ax = plt.subplots()
        i = 0
        for key, grp in df.groupby(["fbe_version"]):
            ax = grp.plot(ax=ax, marker=".", x=x_axis, y='summary_air_time', label=key, c=colors[i],
                          linestyle='--')
            if is_ci_enabled:
                x = grp[x_axis].tolist()
                y = grp["summary_air_time"].tolist()
                add_confidence_interval(x, y, ax, colors[i])
            i += 1
        ax.set_ylim(bottom=0)
        ax.set(xlabel=x_label, ylabel='Summary Airtime', title=output_params.summary_airtime["title"])
        plt.tight_layout()
        save_plot(output_params, "summary_airtime", plot_num, plot_file_name)


def get_path_to_folder(output_params: OutputParams, additional_dir=''):
    if output_params.folder_name is None:
        path_to_folder = try_to_create_directory(f'/val_output/{additional_dir}')
    else:
        path_to_folder = try_to_create_directory(output_params.folder_name + "/" + additional_dir)
        if not os.path.exists(path_to_folder):
            os.makedirs(path_to_folder)
    if additional_dir != '':
        path_to_folder += '/'
    return path_to_folder


def save_plot(output_params: OutputParams, plot_type, plot_num, plot_file_name=None):
    if plot_type == 'backoff_changes_init' \
            or plot_type == 'events' \
            or plot_type == 'backoff_changes' \
            or plot_type == 'interrupt_counter_changes':
        path_to_save = get_path_to_folder(output_params, additional_dir=plot_type)
    else:
        path_to_save = get_path_to_folder(output_params)

    if plot_file_name is not None:
        path_to_save += plot_file_name
    else:
        path_to_save += output_params.file_name + "_" + plot_type
    if plot_num > 0:
        path_to_save += "_" + str(plot_num)
    # plt.savefig(path_to_save)
    plt.savefig(path_to_save + '.svg')
    # plt.savefig(path_to_save + '.png')
    plt.close()


def zip_plot_params(*params):
    max_size = 0
    params_outer_list = []
    for param in params:
        if param is None:
            params_list = [None]
        else:
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
    simulation_params = get_scenario_directly_from_json(
        json_path)

    run_simulation(simulation_params)


if __name__ == '__main__':
    # fig, ax = plt.subplots(nrows=10, ncols=1)
    # x1 = [0, 1]
    # y1 = [0, 0]
    # y2 = [1, 1]
    # i = 1
    # for ax_ in ax:
    #     ax_.set_aspect(1)
    #     ax_.fill_between(x1, y1, y2=y2, color='grey', edgecolor='black')
    #     ax_.set_yticks([0, 1])
    #     ax_.set_xticks([0, 32])
    #     ax_.set_xticklabels([])
    #     ax_.set_yticklabels([])
    #     ax_.set_ylabel(i)
    #     ax_.text(avg(x1[0], x1[1]), avg(y1[0], y2[0]), 1, horizontalalignment='center',
    #              verticalalignment='center')
    #     # ax_.set_tight_layout()
    #     i += 1
    # # plt.yticks([0,1])
    # fig.tight_layout()
    # # plt.ylim(0, 1)
    # # plt.xlim(0, 32)
    # plt.show()
    # num = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    # print(num[0:10])
    zipperinio = zip_plot_params('siema1;siema2', 'kurwa1;kurwa2', None)
    for a, b, c in zipperinio:
        print(f'a = {a}, b = {b}, c = {c}')
