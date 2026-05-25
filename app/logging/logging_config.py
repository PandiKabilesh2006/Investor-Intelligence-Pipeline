import logging
import os

# Create standard formatting for logs
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Ensure the log file is in the root directory
log_filepath = 'pipeline.log'

# File handler for pipeline.log
file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# Setup loggers
pipeline_logger = logging.getLogger('pipeline')
pipeline_logger.setLevel(logging.INFO)
pipeline_logger.addHandler(file_handler)
pipeline_logger.addHandler(console_handler)

error_logger = logging.getLogger('error')
error_logger.setLevel(logging.ERROR)
error_logger.addHandler(file_handler)
error_logger.addHandler(console_handler)
