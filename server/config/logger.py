"""Logging configuration with colors"""
import logging
import sys

import colorlog

# Configure colored logging format
LOG_FORMAT = "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s%(reset)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Color configuration
LOG_COLORS = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red,bg_white',
}

# Create colored handler
handler = colorlog.StreamHandler(sys.stdout)
handler.setFormatter(colorlog.ColoredFormatter(
    LOG_FORMAT,
    datefmt=DATE_FORMAT,
    log_colors=LOG_COLORS
))

# Configure root logger (console only, no file)
logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)

# Create logger for application
logger = logging.getLogger("iot_server")
logger.setLevel(logging.INFO)

