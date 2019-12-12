#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

.. moduleauthor:: Zaleos <admin@zaleos.net>

"""

import logging
import time
import os
import shutil
import subprocess
import re
import string
import copy
import glob
from jinja2 import (Environment,
                    FileSystemLoader,
                    StrictUndefined)

from . import Network
# Need to import whole module, and refer to its functions by fully qualified name,
# because in unit-tests we're mocking these functions
# And if we import as aliases, mocking doesn't work.
import sipplauncher.utils.Utils
from sipplauncher.utils.Defaults import (DEFAULT_TEMP_FOLDER,
                                         DEFAULT_SCENARIO_FILENAME_REGEX,
                                         DEFAULT_SCENARIO_RUN_ID_FILENAME_REGEX,
                                         DEFAULT_SCRIPT_TIMEOUT)
from .UA import UA
from .PysippProcess import PysippProcess
from .Scenario import Scenario

STATES = ["CREATED", "READY", "DRY-RUNNING", "STARTING", "FAIL", "SUCCESS"]

scenario_regex = re.compile(DEFAULT_SCENARIO_FILENAME_REGEX)
scenario_run_id_regex = re.compile(DEFAULT_SCENARIO_RUN_ID_FILENAME_REGEX)

class SIPpTest(object):
    class InitException(Exception):
        pass

    class PysippProcessException(Exception):
        pass

    class ScriptRunException(Exception):
        pass

    def __init__(self, folder):
        self.key = os.path.basename(folder)
        self.state = STATES[0]
        self.__folder = folder

        def get_uas():
            uas = set()
            root, dirs, files = next(os.walk(self.__folder))
            for file in files:
                basename = os.path.basename(file)

                match = scenario_regex.match(basename)
                if match:
                    # Scenario filename matched simple format, without Run ID
                    ua_name = match.group(2)
                    run_id = ""
                    role = Scenario.Role[match.group(1)]
                else:
                    match = scenario_run_id_regex.match(basename)
                    if match:
                        # Scenario filename matched complex format, with Run ID
                        ua_name = match.group(3)
                        run_id = match.group(1)
                        role = Scenario.Role[match.group(2)]
                    else:
                        continue

                scen = Scenario(basename, role)

                for ua in uas:
                    if ua.get_name() == ua_name:
                        # The UA is already in the set.
                        # Just add the new Scenario to the UA for the given Run ID.
                        ua.set_scenario(run_id, scen)
                        break
                else:
                    uas.add(UA(ua_name, run_id, scen))

            return sorted(uas, key = lambda x: x.get_name())

        self.__uas = get_uas()
        if not self.__uas:
            raise SIPpTest.InitException('Test folder "{0}" doesnt contain UA scenarios'.format(self.key))

        logging.debug('Created SIPpTest "{0}"'.format(self.key))

    def __run_script(self, script):
        script_path = os.path.join(self.__temp_folder, script)
        if os.path.exists(script_path):
            p = subprocess.Popen("sh " + script_path,
                                 shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 preexec_fn=os.setpgrp) # Issue #36: change group to not to propagate signals to subprocess
            try:
                stdoutdata, stderrdata = p.communicate(timeout=DEFAULT_SCRIPT_TIMEOUT)
            except subprocess.TimeoutExpired:
                # Script lasts unexpectedly long.
                # Seems like it has deadlocked.
                p.kill()
                raise
            finally:
                ret = p.wait() # to not to leave zombie
            # Need to strip trailing newline, because logger adds newline too.
            if stdoutdata:
                self.__get_logger().debug(stdoutdata.decode("utf-8").rstrip())
            if stderrdata:
                self.__get_logger().error(stderrdata.decode("utf-8").rstrip())
            if ret != 0:
                raise SIPpTest.ScriptRunException(script + " returned code " + str(ret))

    def __get_logger(self):
        return logging.getLogger(__name__ + "." + self.run_id)

    def __create_temp_folder(self):
        self.__temp_folder = os.path.join(DEFAULT_TEMP_FOLDER, self.key, self.run_id)
        logging.debug("Copying {0} to {1}".format(self.__folder, self.__temp_folder))
        shutil.copytree(self.__folder, self.__temp_folder)

    def __init_logger(self):
        # get base logger instance according to options from config
        l_base = logging.getLogger(__name__)
        # get child logger
        l = self.__get_logger()
        # Check if base logger has DynamicFileHandler specified
        for h in l_base.handlers:
            if isinstance(h, sipplauncher.utils.Log.DynamicFileHandler):
                # Base logger is shared by all SIPpTests.
                # We need to copy it to new instance, to configure per-test logging folder.
                handler = copy.copy(h)
                handler.set_folder(self.__temp_folder)
                l.addHandler(handler)

    def __replace_keywords(self, args):
        """ Loops over files in temp folder and replaces keywords in files.

        :param args: application args
        :type args: dict
        """

        # start with mandatory keywords
        kwargs = {
            "dut": {
                "host": args.dut,
            },
            "test": {
                "name": self.key,
                "run_id": self.run_id,
            },
            "custom_transport": "", # TODO: remove this
        }
        # add our IP addresses
        for ua in self.__uas:
            kwargs[ua.get_name()] = {
                "host": ua.ip,
            }
        # add user-supplied keywords
        if args.keyword_replacement_values:
            kwargs.update(args.keyword_replacement_values)

        #collect files to perform replacement
        files = set()
        for file in glob.glob(os.path.join(self.__temp_folder, "*.sh")):
            files.add(os.path.basename(file))
        for ua in self.__uas:
            files |= ua.get_filenames()

        # loop over files and perform replacement
        for file in files:
            path = os.path.join(self.__temp_folder, file)
            with open(path, 'r') as f:
                content = f.read()

            folders = [self.__temp_folder]
            if args.template_folder:
                folders.append(args.template_folder)

            j2_env = Environment(loader=FileSystemLoader(folders),
                                 undefined=StrictUndefined) # to raise exception when jinja is unable to replace undefined keyword
            template = j2_env.get_template(file)
            rendered_content = template.render(**kwargs)

            # write back file content only if it has actually been replaced
            if rendered_content != content:
                with open(path, 'w') as f:
                    f.write(rendered_content)

    def __gen_certs_keys(self, args):
        if args.sipplauncher_ca:
            for ua in self.__uas:
                ua.gen_cert_key(args.sipplauncher_ca, self.__temp_folder)

    def __remove_temp_folder(self, args):
        if not args.leave_temp:
            logging.debug("Removing {0}".format(self.__temp_folder))
            shutil.rmtree(self.__temp_folder)
        else:
            logging.debug("You can find temp folder at {0}".format(self.__temp_folder))

    def pre_run(self, args):
        # We should rollback prior initialization on exception to not to leave test partially initialized.
        # We should propagate exception to the caller.
        self.run_id = sipplauncher.utils.Utils.generate_id(n=6, just_letters=True)
        self.network = Network.SIPpNetwork(args.dut, args.network_mask, self.run_id)
        try:
            for ua in self.__uas:
                ua.ip = self.network.add_random_ip()

            self.__create_temp_folder()

            try:
                self.__init_logger()
                self.__replace_keywords(args)
                self.__gen_certs_keys(args)

                if args.leave_temp and not args.no_pcap:
                    self.network.sniffer_start(self.__temp_folder)
            except:
                self.__remove_temp_folder(args)
                raise
        except:
            self.network.shutdown()
            raise
        # No exceptions during initialization.
        # Switch to READY state.
        self.state = STATES[1]

    def __print_run_state(self, run_id_prefix, extra=None):
        """ Helper to print the test and status"""
        msg = '%12s %24s (%s-%s)' % (self.state, self.key, run_id_prefix, self.run_id)
        msg += extra if extra is not None else ''
        logging.info(msg)

    def __do_run(self, run_id_prefix, args):
        """
        This method doesn't catch exceptions in order to propagate them to pytest.
        This method is run while calculating time elapsed for a test.
        Therefore this method should perform actual testing only.
        All other initialization (like Network, Sniffer, etc) should be done inside pre_run().
        """
        if args.dry_run:
            self.state = STATES[2]
            self.__print_run_state(run_id_prefix)
        else:
            self.state = STATES[3]
            self.__print_run_state(run_id_prefix)
            self.__run_script("before.sh")
            try:
                p = PysippProcess(self.__uas, self.__temp_folder, args)
                # https://bugs.python.org/issue6721
                # "The python logging module uses a lock to surround many operations.
                # This causes deadlocks in programs that use logging, fork and threading simultaneously."
                # For example, we have Process P1.
                # P1's thread T1 obtains logging lock L1 while logging.
                # Then P1's thread T2 forks a new multiprocessing.Process P2, which inherits L1 in locked state.
                # Then P2 tries to log, and stucks on L1, because noone will ever release it.
                # To workaround this, we acquire L1 before forking, and release L1 immediately after both in P1 and P2.
                logging._acquireLock();
                try:
                    p.start()
                finally:
                    logging._releaseLock();
                p.join()
                if p.exitcode != 0:
                    raise SIPpTest.PysippProcessException(p.exitcode)
            finally:
                self.__run_script("after.sh")
        # All good
        self.state = STATES[5]

    def run(self, run_id_prefix, args):
        if self.state == STATES[0]:
            # pre_run() has failed.
            # We shouldn't run this test.
            # We shouldn't reach this, because currently run() is not invoked if pre_run() has failed.
            assert False, "Don't invoke run() if pre_run() has failed"
        else:
            # pre_run() has succeeded.
            # We can run this test.
            try:
                start = time.time()

                # Put implementation to __do_run() to enable testing it with pytest.
                # We can't completely test run() method with pytest directly, because it swallows exceptions.
                self.__do_run(run_id_prefix, args)
            except SIPpTest.PysippProcessException as e:
                # Expected outcome
                self.__get_logger().info('PysippProcess returned {0}'.format(e))
                self.state = STATES[4]
            except Exception as e:
                self.__get_logger().error('Caught exception while running test: {0}'.format(e))
                self.__get_logger().debug(e, exc_info = True)
                self.state = STATES[4]
            finally:
                # Wrap up timing
                end = time.time()
                elapsed = end - start
                elapsed_str=' - took %.0fs' % (elapsed)
                self.__print_run_state(run_id_prefix, extra=elapsed_str)

    def post_run(self, args):
        if self.state != STATES[0]:
            # pre_run() has succedded.
            # Now we should attempt to cleanup as much as we can.
            # We shouldn't propagate exception to the caller, because caller should post_run other tests as well.
            try:
                self.network.sniffer_stop()
            except Exception as e:
                self.__get_logger().debug(e, exc_info = True)

            try:
                self.__remove_temp_folder(args)
            except Exception as e:
                self.__get_logger().debug(e, exc_info = True)

            # shutdown network always
            try:
                self.network.shutdown()
            except Exception as e:
                self.__get_logger().debug(e, exc_info = True)

    def failed(self):
        """ Returns whether a test failed"""
        return self.state != STATES[5]