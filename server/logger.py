import logging

# ANSI escape codes for colors
COLORS = {
    "GREY": "\033[38;21m",
    "GREEN": "\033[32;21m",
    "CYAN": "\033[36;21m",
    "YELLOW": "\033[33;21m",
    "RED": "\033[31;21m",
    "BOLD_RED": "\033[31;1m",
    "RESET": "\033[0m",
}


class ColorFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(fmt="%(levelname)s %(message)s")
        self.FORMATS = {
            logging.DEBUG: COLORS["CYAN"] + "[%(levelname)s]" + COLORS["RESET"] + " %(message)s",
            logging.INFO: COLORS["GREEN"] + "[%(levelname)s]" + COLORS["RESET"] + " %(message)s",
            logging.WARNING: COLORS["YELLOW"] + "[%(levelname)s]" + COLORS["RESET"] + " %(message)s",
            logging.ERROR: COLORS["RED"] + "[%(levelname)s]" + COLORS["RESET"] + " %(message)s",
            logging.CRITICAL: COLORS["BOLD_RED"] + "[%(levelname)s]" + COLORS["RESET"] + " %(message)s",
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logger = logging.getLogger("readly")
logger.handlers = []
logger.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter())
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
