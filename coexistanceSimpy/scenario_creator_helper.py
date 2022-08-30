import json
import random
from dataclasses import dataclass

from coexistanceSimpy import DeterministicBackoffFBE, FBEVersion
from coexistanceSimpy import FBETimers
from coexistanceSimpy import FixedMutingFBE
from coexistanceSimpy import FloatingFBE
from coexistanceSimpy import RandomMutingFBE
from coexistanceSimpy import StandardFBE


def collect_cot_ffp_offset_zip(cot_list, ffp_list, offset_list):
    max_size = max(len(cot_list), len(ffp_list), len(offset_list))
    last_ffp_value = ffp_list[-1]
    last_cot_value = cot_list[-1]
    last_offset_value = offset_list[-1]
    for i in range(0, max_size - len(ffp_list)):
        ffp_list.append(last_ffp_value)
    for i in range(0, max_size - len(cot_list)):
        cot_list.append(last_cot_value)
    for i in range(0, max_size - len(offset_list)):
        offset_list.append(last_offset_value)
    check_for_random_params(cot_list)
    check_for_random_params(ffp_list)
    check_for_random_params(offset_list)

    return zip([int(cot) for cot in cot_list], [int(ffp) for ffp in ffp_list], [int(offset) for offset in offset_list])


def check_for_random_params(variable_list):
    for i in range(len(variable_list)):
        if ".." in variable_list[i]:
            bounds = variable_list[i].split("..")
            random_num = random.randint(int(bounds[0]), int(bounds[1]))
            variable_list[i] = str(random_num)


def get_base_fbe_rows(table, row):
    ffp_list = table.takeItem(row, 3).text().split(';')
    cot_list = table.takeItem(row, 2).text().split(';')
    name = table.takeItem(row, 0).text()
    offset = int(table.takeItem(row, 1).text())
    cot_ffp_zip = collect_cot_ffp_offset_zip(cot_list, ffp_list)
    return cot_ffp_zip, name, offset


def get_standard_fbe_rows(table, station_list):
    for row in range(table.rowCount()):
        cot_ffp_zip, name, offset = get_base_fbe_rows(table, row)
        create_standard_fbe(cot_ffp_zip, name, offset, station_list)


def create_standard_fbe(cot_ffp_offset_zip, name, station_list):
    standard_stations_list = []
    for cot, ffp, offset in cot_ffp_offset_zip:
        timers = FBETimers(ffp, cot)
        standard_stations_list.append(StandardFBE(name, timers, offset=offset))
    station_list.append(standard_stations_list)


def get_fixed_muting_fbe_rows(table, station_list):
    for row in range(table.rowCount()):
        cot_ffp_zip, name, offset = get_base_fbe_rows(table, row)
        max_muted_periods = int(table.takeItem(row, 4).text())
        create_fixed_muting_fbe(cot_ffp_zip, max_muted_periods, name, offset, station_list)


def create_fixed_muting_fbe(cot_ffp_offset_zip, max_muted_periods, name, station_list):
    fixed_muting_stations_list = []
    for cot, ffp, offset in cot_ffp_offset_zip:
        timers = FBETimers(ffp, cot)
        fixed_muting_stations_list.append(
            FixedMutingFBE(name, timers, offset=offset, max_number_of_muted_periods=max_muted_periods))
    station_list.append(fixed_muting_stations_list)


def get_random_muting_fbe_rows(table, station_list):
    for row in range(table.rowCount()):
        cot_ffp_zip, name, offset = get_base_fbe_rows(table, row)
        max_muted_periods = int(table.takeItem(row, 4).text())
        max_transmissions = int(table.takeItem(row, 5).text())
        create_random_muting_fbe(cot_ffp_zip, max_muted_periods, max_transmissions, name, offset, station_list)


def create_random_muting_fbe(cot_ffp_offset_zip, max_muted_periods, max_transmissions, name, station_list):
    random_muting_stations_list = []
    for cot, ffp, offset in cot_ffp_offset_zip:
        timers = FBETimers(ffp, cot)
        random_muting_stations_list.append(
            RandomMutingFBE(name, timers, offset=offset, max_muted_periods=max_muted_periods,
                            max_frames_in_a_row=max_transmissions))
    station_list.append(random_muting_stations_list)


def get_floating_fbe_rows(table, station_list):
    for row in range(table.rowCount()):
        cot_ffp_zip, name, offset = get_base_fbe_rows(table, row)
        create_floating_fbe(cot_ffp_zip, name, offset, station_list)


def create_floating_fbe(cot_ffp_offset_zip, name, station_list):
    floating_fbe_station_list = []
    for cot, ffp, offset in cot_ffp_offset_zip:
        timers = FBETimers(ffp, cot)
        floating_fbe_station_list.append(FloatingFBE(name, timers, offset=offset))
    station_list.append(floating_fbe_station_list)


def get_db_fbe_rows(table, station_list):
    for row in range(table.rowCount()):
        cot_ffp_zip, name, offset = get_base_fbe_rows(table, row)
        max_retransmissions = int(table.takeItem(row, 4).text())
        init_backoff = int(table.takeItem(row, 5).text())
        threshold = int(table.takeItem(row, 6).text())
        create_db_fbe(cot_ffp_zip, init_backoff, max_retransmissions, name, offset, station_list, threshold)


def create_db_fbe(cot_ffp_offset_zip, init_backoff, max_retransmissions, name, station_list, threshold):
    db_fbe_stations_list = []
    for cot, ffp, offset in cot_ffp_offset_zip:
        timers = FBETimers(ffp, cot)
        db_fbe_stations_list.append(
            DeterministicBackoffFBE(name, timers, offset=offset, init_backoff_value=init_backoff,
                                    threshold=threshold, maximum_number_of_retransmissions=max_retransmissions))
    station_list.append(db_fbe_stations_list)


def get_station_list(standard_fbe_table, fixed_muting_fbe_table, random_muting_fbe_table, floating_fbe_table,
                     db_fbe_table):
    station_list = []
    get_standard_fbe_rows(standard_fbe_table, station_list)
    get_fixed_muting_fbe_rows(fixed_muting_fbe_table, station_list)
    get_random_muting_fbe_rows(random_muting_fbe_table, station_list)
    get_floating_fbe_rows(floating_fbe_table, station_list)
    get_db_fbe_rows(db_fbe_table, station_list)
    print(station_list)
    return station_list


def get_station_params_from_json(j, fbe_version: FBEVersion):
    if fbe_version == FBEVersion.STANDARD_FBE:
        return StandardFBEJsonParams(**j)
    elif fbe_version == FBEVersion.FIXED_MUTING_FBE:
        return FixedMutingFBEJsonParams(**j)
    elif fbe_version == FBEVersion.RANDOM_MUTING_FBE:
        return RandomMutingFBEJsonParams(**j)
    elif fbe_version == FBEVersion.FLOATING_FBE:
        return FloatingFBEJsonParams(**j)
    elif fbe_version == FBEVersion.DETERMINISTIC_BACKOFF_FBE:
        return DeterministicBackoffFBEJsonParams(**j)
    raise RuntimeError(f'Not supported FBEVersion {fbe_version}')


def get_scenario_directly_from_json(json_path):
    f = open(json_path)
    j = json.load(f)
    f.close()
    standard_fbe_json_list = j[FBEVersion.STANDARD_FBE.name] if FBEVersion.STANDARD_FBE.name in j else []
    fixed_muting_fbe_json_list = j[FBEVersion.FIXED_MUTING_FBE.name] if FBEVersion.FIXED_MUTING_FBE.name in j else []
    random_muting_fbe_json_list = j[FBEVersion.RANDOM_MUTING_FBE.name] if FBEVersion.RANDOM_MUTING_FBE.name in j else []
    floating_fbe_json_list = j[FBEVersion.FLOATING_FBE.name] if FBEVersion.FLOATING_FBE.name in j else []
    db_fbe_json_list = j[
        FBEVersion.DETERMINISTIC_BACKOFF_FBE.name] if FBEVersion.DETERMINISTIC_BACKOFF_FBE.name in j else []
    station_list = get_station_list_from_json_lists(standard_fbe_json_list, fixed_muting_fbe_json_list,
                                                    random_muting_fbe_json_list, floating_fbe_json_list,
                                                    db_fbe_json_list)
    simulation_time = int(j["SIMULATION_TIME"]) if "SIMULATION_TIME" in j else 1000000
    plot_params_json = j["PLOT_PARAMS"] if "PLOT_PARAMS" in j else None
    plot_params = PlotParams(**plot_params_json)
    is_separate_run = j["RUN_SEPARATELY"] if "RUN_SEPARATELY" in j else False
    return station_list, simulation_time, plot_params, is_separate_run


def get_standard_fbe_from_json_list(standard_fbe_json_list, stations_list):
    i = 1
    for standard_fbe_json in standard_fbe_json_list:
        params = get_station_params_from_json(standard_fbe_json, FBEVersion.STANDARD_FBE)
        cot_ffp_offset_zip = collect_cot_ffp_offset_zip(params.cot.split(';'), params.ffp.split(';'),
                                                        params.offset.split(';'))
        create_standard_fbe(cot_ffp_offset_zip, params.name.format(i), stations_list)
        i += 1


def get_fixed_muting_fbe_from_json_list(fixed_muting_fbe_json_list, stations_list):
    i = 1
    for fixed_muting_fbe_json in fixed_muting_fbe_json_list:
        params = get_station_params_from_json(fixed_muting_fbe_json, FBEVersion.FIXED_MUTING_FBE)
        cot_ffp_offset_zip = collect_cot_ffp_offset_zip(params.cot.split(';'), params.ffp.split(';'),
                                                        params.offset.split(';'))
        create_fixed_muting_fbe(cot_ffp_offset_zip, params.max_muted_periods, params.name.format(i),
                                stations_list)
        i += 1


def get_random_muting_fbe_from_json_list(random_muting_fbe_json_list, stations_list):
    i = 1
    for random_muting_fbe_json in random_muting_fbe_json_list:
        params = get_station_params_from_json(random_muting_fbe_json, FBEVersion.RANDOM_MUTING_FBE)
        cot_ffp_offset_zip = collect_cot_ffp_offset_zip(params.cot.split(';'), params.ffp.split(';'),
                                                        params.offset.split(';'))
        create_random_muting_fbe(cot_ffp_offset_zip, params.max_muted_periods, params.max_frames_in_row,
                                 params.name.format(i), stations_list)
        i += 1


def get_floating_fbe_from_json_list(floating_fbe_json_list, stations_list):
    i = 1
    for floating_fbe_json in floating_fbe_json_list:
        params = get_station_params_from_json(floating_fbe_json, FBEVersion.FLOATING_FBE)
        cot_ffp_offset_zip = collect_cot_ffp_offset_zip(params.cot.split(';'), params.ffp.split(';'),
                                                        params.offset.split(';'))
        create_floating_fbe(cot_ffp_offset_zip, params.name.format(i), stations_list)
        i += 1


def get_db_fbe_from_json_list(db_fbe_json_list, stations_list):
    i = 1
    for db_fbe_json in db_fbe_json_list:
        params = get_station_params_from_json(db_fbe_json, FBEVersion.DETERMINISTIC_BACKOFF_FBE)
        cot_ffp_offset_zip = collect_cot_ffp_offset_zip(params.cot.split(';'), params.ffp.split(';'),
                                                        params.offset.split(';'))
        create_db_fbe(cot_ffp_offset_zip, params.init_backoff, params.max_retransmissions, params.name.format(i),
                      stations_list, params.threshold)
        i += 1


def get_station_list_from_json_lists(standard_fbe_json_list, fixed_muting_fbe_json_list, random_muting_fbe_json_list,
                                     floating_fbe_json_list,
                                     db_fbe_json_list):
    stations_list = []
    get_standard_fbe_from_json_list(standard_fbe_json_list, stations_list)
    get_fixed_muting_fbe_from_json_list(fixed_muting_fbe_json_list, stations_list)
    get_random_muting_fbe_from_json_list(random_muting_fbe_json_list, stations_list)
    get_floating_fbe_from_json_list(floating_fbe_json_list, stations_list)
    get_db_fbe_from_json_list(db_fbe_json_list, stations_list)
    return stations_list


class StandardFBEJsonParams:

    def __init__(self, name, offset, cot, ffp) -> None:
        super().__init__()
        self.ffp = ffp
        self.cot = cot
        self.offset = offset
        self.name = name


class FixedMutingFBEJsonParams(StandardFBEJsonParams):

    def __init__(self, name, offset, cot, ffp, max_muted_periods) -> None:
        super().__init__(name, offset, cot, ffp)
        self.max_muted_periods = int(max_muted_periods)


class RandomMutingFBEJsonParams(StandardFBEJsonParams):

    def __init__(self, name, offset, cot, ffp, max_muted_periods, max_frames_in_row) -> None:
        super().__init__(name, offset, cot, ffp)
        self.max_frames_in_row = int(max_frames_in_row)
        self.max_muted_periods = int(max_muted_periods)


class FloatingFBEJsonParams(StandardFBEJsonParams):

    def __init__(self, name, offset, cot, ffp) -> None:
        super().__init__(name, offset, cot, ffp)


class DeterministicBackoffFBEJsonParams(StandardFBEJsonParams):

    def __init__(self, name, offset, cot, ffp, max_retransmissions, init_backoff, threshold) -> None:
        super().__init__(name, offset, cot, ffp)
        self.threshold = int(threshold)
        self.init_backoff = int(init_backoff)
        self.max_retransmissions = int(max_retransmissions)


@dataclass
class PlotParams:
    x_axis: str
    y_axis: str
    title: str
    x_label: str
    y_label: str
    file_name: str
    folder_name: str


if __name__ == '__main__':
    js = {
        "name": "GNB_FBE {}",
        "offset": "0",
        "cot": "250;750;1250;1750;2250;2750;3250;3750;4250;4750",
        "ffp": "5000"
    }
    test = "250;1..20;11..54;1750;2250;2750;3250;3750;4250;4750".split(";")
    check_for_random_params(test)
    print(test)
