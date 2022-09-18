import matplotlib.pyplot as plt
import pandas as pd

from Coexistence import *

simulation_time = 10000000
fbe_version_list = [FBEVersion.STANDARD_FBE,
                    FBEVersion.FLOATING_FBE,
                    FBEVersion.RANDOM_MUTING_FBE,
                    FBEVersion.FIXED_MUTING_FBE,
                    FBEVersion.DETERMINISTIC_BACKOFF_FBE]


def run_single_station(station_number, ffp, cot, airtime_list, fbe_version):
    environment = simpy.Environment()
    channel = Channel(None, simpy.Resource(environment, capacity=1), 0, 0, None, None, None, None, None,
                      simulation_time)
    list_test = []
    timers = FBETimers(ffp, cot)
    if fbe_version == FBEVersion.STANDARD_FBE:
        list_test.append(
            StandardFBE(str(station_number), environment, channel, "\033[30m", timers))
    elif fbe_version == FBEVersion.FLOATING_FBE:
        list_test.append(
            FloatingFBE(str(station_number), environment, channel, "\033[30m", timers))
    elif fbe_version == FBEVersion.FIXED_MUTING_FBE:
        list_test.append(
            FixedMutingFBE(str(station_number), environment, channel, "\033[30m", timers))
    elif fbe_version == FBEVersion.RANDOM_MUTING_FBE:
        list_test.append(
            RandomMutingFBE(str(station_number), environment, channel, "\033[30m", timers, max_muted_periods=10))
    elif fbe_version == FBEVersion.DETERMINISTIC_BACKOFF_FBE:
        list_test.append(
            DeterministicBackoffFBE(str(station_number), environment, channel, "\033[30m", timers))

    environment.run(until=simulation_time)
    for gnb in list_test:
        print(gnb.name)
        print('Successful transmitions {}'.format(gnb.succeeded_transmissions))
        print('Failed transmitions {}'.format(gnb.failed_transmissions))
        print('Air time {}'.format(gnb.air_time))
        airtime_list.append(gnb.air_time)


def run_multiple_stations(offsets, ffp, cot_list, fbe_versions):
    stations_list = []
    all_stations_sim_result_dict = {"station_name": [], "x": [], "y": []}
    for cot in cot_list:
        env = simpy.Environment()
        channel = Channel(None, simpy.Resource(env, capacity=1), 0, 0, None, None, None, None, None, simulation_time)
        timers = FBETimers(ffp, cot)
        print('------------------------------------------')
        print('Cot = {}'.format(cot))
        print(repr(timers))
        indexes = [x for x in range(0, len(fbe_versions))]
        for (offset, fbe_version, i) in zip(offsets, fbe_versions, indexes):
            if fbe_version == FBEVersion.STANDARD_FBE:
                stations_list.append(
                    StandardFBE(str(i), env, channel, "\033[30m", timers))
            elif fbe_version == FBEVersion.FLOATING_FBE:
                stations_list.append(
                    FloatingFBE(str(i), env, channel, "\033[30m", timers))
            elif fbe_version == FBEVersion.FIXED_MUTING_FBE:
                stations_list.append(
                    FixedMutingFBE(str(i), env, channel, "\033[30m", timers))
            elif fbe_version == FBEVersion.RANDOM_MUTING_FBE:
                stations_list.append(
                    RandomMutingFBE(str(i), env, channel, "\033[30m", timers,
                                    max_muted_periods=10))
            elif fbe_version == FBEVersion.DETERMINISTIC_BACKOFF_FBE:
                stations_list.append(DeterministicBackoffFBE(str(i), env, channel, "\033[30m", timers,
                                                             maximum_number_of_retransmissions=8, threshold=3))

        env.run(until=simulation_time)
        for station in stations_list:
            print(station.name)
            print('Successful transmitions {}'.format(station.succeeded_transmissions))
            print('Failed transmitions {}'.format(station.failed_transmissions))
            print('Air time {}'.format(station.air_time))
            all_stations_sim_result_dict["station_name"].append(station.name)
            all_stations_sim_result_dict["x"].append(cot)
            all_stations_sim_result_dict["y"].append(station.air_time)
        stations_list.clear()

    return all_stations_sim_result_dict


def fixed_ffp_single_gnb_variables_cot_runs(cot_list, fbe_version):
    airtime_list = []
    for i in range(len(cot_list)):
        cot = cot_list[i]
        run_single_station(i, 5000, cot, airtime_list, fbe_version)
    return {"cot": cot_list, "air_time": airtime_list}


def fixed_cot_variables_ffp(ffp_list, fbe_version):
    airtime_list = []
    for i in range(len(ffp_list)):
        ffp = ffp_list[i]
        cot = int(ffp * 0.95)
        run_single_station(i, ffp, cot, airtime_list, fbe_version)
    airtime_list = [round(x / simulation_time, 2) for x in airtime_list]
    return {"ffp": ffp_list, "air_time": airtime_list}


def run_test(test_fun, title, xlabel, ylabel, test_name='Test', run_multiple_station=False):
    file_name = test_name
    # csv_file_path = 'val_output/csv/{}.csv'.format(file_name)
    path = os.getcwd() + '/val_output/images'
    if not os.path.exists(path):
        os.makedirs(path)
    image_file_path = 'val_output/images/{}'.format(file_name)
    test_fun_dict = test_fun()
    if run_multiple_station:
        plot_multiple(test_fun_dict, image_file_path, title, xlabel, ylabel)
    else:
        df = pd.DataFrame.from_dict(test_fun_dict)
        plot(df, image_file_path, title, xlabel, ylabel)
        # df.to_csv(csv_file_path, sep=',', index=False)


def plot(df, path_to_save, title, xlabel, ylabel):
    # Group by sum of all flows in a given experiment run (to obtain aggregate throughput)
    # df = df.groupby(['nWifi', 'RngRun'])['Throughput'].sum().reset_index()
    # Group by nWifi and calculate average (mean) aggregate throughput
    # df = df.groupby(['nWifi'])['Throughput'].mean()
    print(df)
    # Plot
    columns = df.columns.get_fbe_versions
    ax = df.plot(title=title, marker='o', legend=False, x=columns[0], y=columns[1])
    ax.set(xlabel=xlabel, ylabel=ylabel)
    # Save to file
    plt.tight_layout()
    plt.savefig(path_to_save + '.png')
    plt.savefig(path_to_save + '.svg')


def plot_multiple(result_dict, path_to_save, title, xlabel, ylabel):
    marks = ['s', 'o', 'd', 'v']
    colors = ['r', 'g', 'b', 'yellow']
    df = pd.DataFrame.from_dict(result_dict)
    fig, ax = plt.subplots()
    i = 0
    for key, grp in df.groupby(["station_name"]):
        ax = grp.plot(ax=ax, marker=marks[i], x='x', y='y', label=key, c=colors[i])
        i += 1

    ax.set(xlabel=xlabel, ylabel=ylabel, title=title)
    plt.tight_layout()
    plt.savefig(path_to_save)
    plt.savefig(path_to_save + '.svg')


if __name__ == "__main__":
    cot_list = [250,
                750,
                1250,
                1750,
                2250,
                2750,
                3250,
                3750,
                4250,
                4750]
    # run_test(lambda: fixed_ffp_single_gnb_variables_cot_runs(cot_list), 'Single station, floating COT', 'COT [us]',
    #          'Airtime [us]')
    ffp_list = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]
    # run_test(lambda: fixed_cot_variables_ffp(ffp_list), "Single station, floating FFP", 'FFP [us]', 'Airtime [us]')
    offset_list = [0, 2500, 5000, 7500]

    # run_test(lambda: run_multiple_stations(offset_list, 10000, cot_list), "Many stations with offsets, floating COT",
    #        "COT [us]", "Airtime [us]", run_multiple_station=True)
    # continuous_enchantment_test(cot_list)
    # run_multiple_stations(offset_list, 10000, cot_list)
    # run_single_station(1, 10000, 5000, [])
    # run_multiple_stations([0, 0], 10000, [5000])
    # for fbe_version in fbe_version_list:
    #     title = fbe_version.name
    #     test_name = 'FIXED_FFP_VARIABLES_COT_' + fbe_version.name
    #     run_test(lambda: fixed_ffp_single_gnb_variables_cot_runs(cot_list, fbe_version), title, 'COT [us]',
    #              'Airtime [us]', test_name=test_name)
    #
    # for fbe_version in fbe_version_list:
    #     title = fbe_version.name
    #     test_name = 'FIXED_COT_VARIABLES_FFP_' + fbe_version.name
    #     run_test(lambda: fixed_cot_variables_ffp(ffp_list, fbe_version), title, 'FFP [us]',
    #              'Airtime [us]', test_name=test_name)

    cot_list = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]

    # for fbe_version in fbe_version_list:
    #     title = fbe_version.name
    #     test_name = 'STATIONS_WO_OFFSET' + fbe_version.name
    #     version_list = []
    #     offset_list = []
    #     for i in range(0, 4):
    #         version_list.append(fbe_version)
    #         offset_list.append(0)
    #     run_test(lambda: run_multiple_stations(offset_list, 10000, cot_list, version_list), title, 'COT [us]',
    #              'Airtime [us]', test_name=test_name, run_multiple_station=True)

    title = FBEVersion.DETERMINISTIC_BACKOFF_FBE.name
    test_name = 'STATIONS_WO_OFFSET' + title
    version_list = []
    offset_list = []
    for i in range(0, 4):
        version_list.append(FBEVersion.DETERMINISTIC_BACKOFF_FBE)
        offset_list.append(0)
    run_test(lambda: run_multiple_stations(offset_list, 10000, cot_list, version_list),
             title,
             'COT [us]',
             'Airtime [us]', test_name=test_name, run_multiple_station=True)
