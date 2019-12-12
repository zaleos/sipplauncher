#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

.. moduleauthor:: Zaleos <admin@zaleos.net>

"""


import os
import sys

VERSION = '0.0.11'

# Folder where config files will be stored after
# package installation.
DEFAULT_CONFIG_FILES = os.path.join(sys.prefix,
                                    'local',
                                    'etc',
                                    'sipplauncher')

DEFAULT_LOG_CONFIG_NAME = 'sipplauncher.configlog.conf'
DEFAULT_LOG_CONFIG_PATH = os.path.join(DEFAULT_CONFIG_FILES,
                                       DEFAULT_LOG_CONFIG_NAME)

log_config_paths = [DEFAULT_LOG_CONFIG_PATH]

DEFAULT_GROUP=1
DEFAULT_NETWORK_MASK=24
DEFAULT_GROUP_PAUSE=0.8

DEFAULT_SCENARIO_FILENAME_REGEX='^(ua[cs]+)_(ua[0-9]+).xml$'
DEFAULT_SCENARIO_RUN_ID_FILENAME_REGEX='^([a-zA-Z0-9]+)_(ua[cs]+)_(ua[0-9]+).xml$'

# Issue #9: Create dynamic execution test temp folder for each test execution
DEFAULT_TEMP_FOLDER="/var/tmp/sipplauncher"

# Issue #37: Add timeout to before/after script running to handle deadlocked scripts
DEFAULT_SCRIPT_TIMEOUT = 60

# Issue #44: Specify default folder for testsuite as tmp-testsuite
DEFAULT_TESTSUITE = "tmp-testsuite"

# Issue #45: Enable user to pass less command-line arguments
DEFAULT_SIPP_INFO_FILE = "users.csv"

# Issue #42: Templating engine
DEFAULT_TESTSUITE_TEMPLATES = "TEMPLATES"

DEFAULT_CA_CN = "ca.zaleos.net"