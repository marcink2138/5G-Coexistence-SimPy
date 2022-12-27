import sys

from coexistanceSimpy.directory_manager_util import get_scenario_paths
from coexistanceSimpy.simulation_runner import run_test

if len(sys.argv) == 1:
    raise AttributeError("Provide simulation scenario path!")

if len(sys.argv) > 2:
    raise AttributeError("Only one argument required!")

scenario_paths = get_scenario_paths(sys.argv[1])
for scenario_path in scenario_paths:
    run_test(scenario_path)
