# src/logger.py

import logging
import sys

# Set up the logger
log = logging.getLogger("gb28181-restreamer")
log.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

# Formatter for logs
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)

# Avoid duplicate handlers on reload
if not log.handlers:
    log.addHandler(console_handler)
