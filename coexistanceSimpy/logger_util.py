import logging
from datetime import datetime

default_logger = logging.getLogger("default")
default_logger.setLevel(logging.INFO)  # chose DEBUG to display stats in debug mode :)
default_logger.disabled = True
default_logger.propagate = False
file_log_name = f"{datetime.today().strftime('%Y-%m-%d-%H-%M-%S')}.log"
logging.basicConfig(filename=file_log_name,
                    format='%(asctime)s %(message)s',
                    filemode='w')


# TODO logging to finish
def station_log(gnb, mes: str) -> None:
    if hasattr(gnb, 'log_name'):
        logger = logging.getLogger(gnb.log_name)
    else:
        logger = logging.getLogger('default')
    logger.info(
        f"Time: {gnb.env.now} Station: {gnb.name} Message: {mes}"
    )


def log(mes: str) -> None:
    default_logger.info(mes)


def enable_logging(log_name=None, log_path="") -> None:
    setup_logger(log_name, log_path)


def setup_logger(log_name, log_path) -> None:
    logger = logging.getLogger(log_name)
    formatter = logging.Formatter('%(asctime)s %(message)s')
    file_handler = logging.FileHandler(log_path + log_name + '.log', mode='w')
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
