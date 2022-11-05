import logging


def station_log(gnb, mes: str) -> None:
    if hasattr(gnb, 'logger_name'):
        logger = logging.getLogger(gnb.logger_name)
    else:
        logger = logging.getLogger('default')
    logger.info(
        f"Time: {gnb.env.now} Station: {gnb.name} Message: {mes}"
    )


def log(mes: str, log_name: str) -> None:
    logger = logging.getLogger(log_name)
    logger.info(mes)


def enable_logging(log_name=None, log_path="") -> None:
    setup_logger(log_name, log_path)


def setup_logger(log_name, log_path) -> None:
    logger = logging.getLogger(log_name)
    formatter = logging.Formatter('%(asctime)s %(message)s')
    file_handler = logging.FileHandler(f'{log_path}/{log_name}.log', mode='w')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
