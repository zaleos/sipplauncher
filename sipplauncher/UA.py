#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

.. moduleauthor:: Zaleos <admin@zaleos.net>

"""

from enum import Enum
import os
from . import Scenario

class UA:
    class DuplicateScenarioException(Exception):
        """
        Raised on attempt to add 2nd scenario for UA for the same Run ID
        """
        pass

    def __init__(self, name, run_id, scenario):
        """
        :param run_id: alphanumeric Run ID, on which the scenario should be run
        :type run_id: str

        :param scenario: scenario to be run on specified Run ID
        :type scenario: Scenario
        """
        self.__name = name
        self.__run_id_map = {run_id: scenario}
        self.ip = ""
        self.__tls_cert = None
        self.__tls_key = None

    def __eq__(self, other):
        return self.__name == other.__name

    def __hash__(self):
        return hash(self.__name)

    def get_name(self):
        """
        :returns: name of UA (for ex. ua0, ua1, etc)
        :rtype: str
        """
        return self.__name

    def set_scenario(self, run_id, scenario):
        """
        :param run_id: alphanumeric Run ID, on which the scenario should be run
        :type run_id: str

        :param scenario: scenario to be run on specified Run ID
        :type scenario: Scenario
        """
        if run_id in self.__run_id_map:
            msg = "{0}: Unable to set scenario {1} for run ID '{2}' - {3} is already set".format(self.__name,
                                                                                                 scenario.get_filename(),
                                                                                                 run_id,
                                                                                                 self.__run_id_map[run_id].get_filename())
            raise UA.DuplicateScenarioException(msg)
        self.__run_id_map[run_id] = scenario

    def get_scenario(self, run_id):
        """
        :returns: Scenario for the giver run_id
        :rtype: Scenario
        """
        scen = None
        if run_id in self.__run_id_map:
            scen = self.__run_id_map[run_id]
        return scen

    def get_filenames(self):
        """
        :returns: filenames of scenarios for all the Run IDs on which the UA is run
        :rtype: set(str)
        """
        filenames = set()
        scens = self.__run_id_map.values()
        for scen in scens:
            filenames.add(scen.get_filename())
        return filenames

    def get_run_ids(self):
        """
        :returns: all the Run IDs on which the UA should be run
        :rtype: set(str)
        """
        return self.__run_id_map.keys()

    def gen_cert_key(self, cert_gen, folder):
        """
        Generates TLS certificate and private key files into the given folder

        :param cert_gen: certificate generator instance
        :type cert_gen: CAOpenSSL

        :param folder: folder to which to generate the files
        :type folder: str
        """
        filename = os.path.join(os.path.abspath(folder), self.__name)
        self.__tls_cert, self.__tls_key = cert_gen.gen_cert_key(self.ip, filename)

    def get_tls_cert(self):
        """
        :returns: location of the generated TLS certificate
        :rtype: str
        """
        return self.__tls_cert

    def get_tls_key(self):
        """
        :returns: location of the generated TLS private key
        :rtype: str
        """
        return self.__tls_key
