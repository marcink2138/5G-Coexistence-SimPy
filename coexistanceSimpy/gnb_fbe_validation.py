import matplotlib.pyplot as plt
import pandas as pd

from Coexistence import *

simulation_time = 1000000


def run_single_station(station_number, ffp, cot, airtime_list):
    environment = simpy.Environment()
    channel = Channel(None, simpy.Resource(environment, capacity=1), 0, 0, None, None, None, None, None)
    list_test = []
    timers = FBETimers(ffp, cot)
    # for i in range(1, 5):
    list_test.append(
        DeterministicBackoffFBE("GnbFBE {}".format(station_number), environment, channel, "\033[30m", timers))

    environment.run(until=simulation_time)
    for gnb in list_test:
        print(gnb.name)
        print('Successful transmitions {}'.format(gnb.succeeded_transmissions))
        print('Failed transmitions {}'.format(gnb.failed_transmissions))
        print('Air time {}'.format(gnb.air_time))
        airtime_list.append(gnb.air_time)


def run_multiple_stations(offsets, ffp, cot_list):
    stations_list = []
    all_stations_sim_result_dict = {"station_name": [], "x": [], "y": []}
    for cot in cot_list:
        env = simpy.Environment()
        channel = Channel(None, simpy.Resource(env, capacity=1), 0, 0, None, None, None, None, None)
        timers = FBETimers(ffp, cot)
        print('------------------------------------------')
        print('Cot = {}'.format(cot))
        print(repr(timers))
        for i in range(0, len(offsets)):
            gnb = DeterministicBackoffFBE("GnbFBE {}".format(i), env, channel, "\033[30m", timers, True, offsets[i])
            stations_list.append(gnb)
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


def fixed_ffp_single_gnb_variables_cot_runs(cot_list):
    airtime_list = []
    for i in range(len(cot_list)):
        cot = cot_list[i]
        run_single_station(i, 5000, cot, airtime_list)
    return {"cot": cot_list, "air_time": airtime_list}


def fixed_cot_variables_ffp(ffp_list):
    airtime_list = []
    for i in range(len(ffp_list)):
        ffp = ffp_list[i]
        cot = int(ffp * 0.95)
        run_single_station(i, ffp, cot, airtime_list)
    airtime_list = [round(x / simulation_time, 2) for x in airtime_list]
    return {"ffp": ffp_list, "air_time": airtime_list}


def continuous_enchantment_test(cot_list):
    airtime_list = []
    for i in range(len(cot_list)):
        run_single_station(i, 10000, cot_list[i], airtime_list, fbe_enchantment=CONTINUOUS_FRAMES_ENCHANTMENT)


def run_test(test_fun, title, xlabel, ylabel, test_name='Test', run_multiple_station=False):
    time = datetime.now().strftime("%H_%M_%S")
    file_name = test_name + time
    csv_file_path = 'val_output/csv/{}.csv'.format(file_name)
    image_file_path = 'val_output/images/{}.png'.format(file_name)
    test_fun_dict = test_fun()
    if run_multiple_station:
        plot_multiple(test_fun_dict, image_file_path, title, xlabel, ylabel)
    else:
        df = pd.DataFrame.from_dict(test_fun_dict)
        plot(df, image_file_path, title, xlabel, ylabel)
        df.to_csv(csv_file_path, sep=',', index=False)


def plot(df, path_to_save, title, xlabel, ylabel):
    # Group by sum of all flows in a given experiment run (to obtain aggregate throughput)
    # df = df.groupby(['nWifi', 'RngRun'])['Throughput'].sum().reset_index()
    # Group by nWifi and calculate average (mean) aggregate throughput
    # df = df.groupby(['nWifi'])['Throughput'].mean()
    print(df)
    # Plot
    columns = df.columns.values
    ax = df.plot(title=title, marker='o', legend=False, x=columns[0], y=columns[1])
    ax.set(xlabel=xlabel, ylabel=ylabel)

    # Save to file
    plt.tight_layout()
    plt.savefig(path_to_save)


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


if __name__ == "__main__":
    # cot_list = [250,
    #             750,
    #             1250,
    #             1750,
    #             2250,
    #             2750,
    #             3250,
    #             3750,
    #             4250,
    #             4750]
    # run_test(lambda: fixed_ffp_single_gnb_variables_cot_runs(cot_list), 'Single station, floating COT', 'COT [us]',
    #          'Airtime [us]')
    # ffp_list = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]
    # run_test(lambda: fixed_cot_variables_ffp(ffp_list), "Single station, floating FFP", 'FFP [us]', 'Airtime [us]')
    # offset_list = [0, 2500, 5000, 7500]
    # cot_list = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]
    # run_test(lambda: run_multiple_stations(offset_list, 10000, cot_list), "Many stations with offsets, floating COT",
    #        "COT [us]", "Airtime [us]", run_multiple_station=True)
    # continuous_enchantment_test(cot_list)
    # run_multiple_stations(offset_list, 10000, cot_list)
    # run_single_station(1, 10000, 5000, [])
    run_multiple_stations([0, 0], 10000, [5000])
