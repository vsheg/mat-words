from loguru import logger as log
from tqdm import tqdm

from .config import settings as CONFIG

# SETUP LOGGING
log.remove()
log.add(lambda msg: tqdm.write(msg, end=''), colorize=True, level='WARNING')
log.add('logs/main.log', rotation='10MB', serialize=True, encoding='utf8')
