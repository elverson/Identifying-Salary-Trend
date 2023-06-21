from tqdm import tqdm
import logging


class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
        except Exception:
            self.handleError(record) 


class TqdmLogger(logging.Logger):
    MESSAGE_FORMAT = "[%(levelname)s] %(asctime)s@%(threadName)s: %(message)s"
    DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name)

        formatter = logging.Formatter(self.MESSAGE_FORMAT, datefmt=self.DATE_FORMAT)
        handler = TqdmLoggingHandler()
        handler.setFormatter(formatter)

        self.setLevel(logging.INFO)
        self.addHandler(handler)
