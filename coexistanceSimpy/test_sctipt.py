import os

from simulation_runner import run_test

floating_cot_fixed_ffp_scenarios = ['/floating_cot_fixed_ffp/' + f for f in
                                    os.listdir(os.getcwd() + '/sim_configs/floating_cot_fixed_ffp')]
floating_ffp_fixed_cot_scenarios = ['/floating_ffp_fixed_cot/' + f for f in
                                    os.listdir(os.getcwd() + '/sim_configs/floating_ffp_fixed_cot')]
four_stations_no_offset_scenarios = ['/four_stations_no_offset/' + f for f in
                                     os.listdir(os.getcwd() + '/sim_configs/four_stations_no_offset')]
four_stations_with_offset_scenarios = ['/four_stations_with_offset/' + f for f in
                                       os.listdir(os.getcwd() + '/sim_configs/four_stations_with_offset')]
random_offset_five_stations_scenario = 'random_offset/random_offset_five_stations.json'
synchronize_start_five_stations_scenario = 'synchronized_start/synchronized_start_five_stations.json'
floating_fbe_test_scenario = 'floating_fbe_test/floating_fbe_test.json'
random_muting_test_scenario = 'random_muting_test/random_muting_fbe_test.json'
fixed_muting_test_scenario = 'fixed_muting_fbe_test/fixed_muting_fbe_test.json'


def get_json_path(sim_config_name):
    path = os.getcwd() + '/sim_configs/' + sim_config_name
    return path


if __name__ == '__main__':
    for floating_cot_fixed_ffp_scenario_path in floating_cot_fixed_ffp_scenarios:
        run_test(get_json_path(floating_cot_fixed_ffp_scenario_path))
    for floating_ffp_fixed_cot_scenario_path in floating_ffp_fixed_cot_scenarios:
        run_test(get_json_path(floating_ffp_fixed_cot_scenario_path))

    for four_stations_no_offset_scenario in four_stations_no_offset_scenarios:
        run_test(get_json_path(four_stations_no_offset_scenario))
    for four_stations_with_offset_scenario in four_stations_with_offset_scenarios:
        run_test(get_json_path(four_stations_with_offset_scenario))
    run_test(get_json_path(random_offset_five_stations_scenario))
    run_test(get_json_path(synchronize_start_five_stations_scenario))
    run_test(get_json_path(floating_fbe_test_scenario))
    run_test(get_json_path(random_muting_test_scenario))
    run_test(get_json_path(fixed_muting_test_scenario))
