import os


def try_to_create_directory(directory_name_path, include_default=True):
    if include_default:
        path = os.getcwd() + f"/val_output/{directory_name_path}"
    else:
        path = os.getcwd() + "/" + directory_name_path
    if not is_path_existing(path):
        os.makedirs(path)
    return path


def is_path_existing(directory_path):
    return os.path.exists(directory_path)


def get_scenario_paths(scenario_path):
    os_cwd = os.getcwd()
    full_path = os_cwd + "/" + scenario_path
    if not is_path_existing(full_path):
        raise FileNotFoundError(full_path)
    if len(scenario_path.split(".json")) > 1:
        return [full_path]

    return [os_cwd + "/" + path for path in os.listdir(full_path)]
