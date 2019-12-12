#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

.. moduleauthor:: Zaleos <admin@zaleos.net>

"""

import sipplauncher.utils.Init
from . import Run
from . import Network
import logging
import sys
import inspect
from .utils.Signals import SignalException, capture_all_signals, check_signal
from .utils.Utils import is_tls_transport

# import warnings
# warnings.filterwarnings("ignore", category=DeprecationWarning)

logger = logging.getLogger("main")


def my_main_fun():
    # Issue #35: We should rebind signal handlers ASAP.
    # Otherwise deadlock is likely to happen on catching signal.
    # This was seen even with default Python signal handlers,
    # when we didn't rebind signal handlers at all.
    capture_all_signals()

    PYTHON_VERSION_MIN = (3, 6, 0)
    if sys.version_info < PYTHON_VERSION_MIN:
        msg = "Required Python version  at least {0}".format('.'.join(str(n) for n in PYTHON_VERSION_MIN))
        raise Exception(msg)

    if not sys.platform.startswith('linux'):
        raise Exception("Must be using Linux")

    def _interfaces_cleaning(args):
        """Helper to perform a cleanup on network interfaces"""
        # Do initial interfaces cleaning
        if args.dry_run:
            logger.debug('Not doing safety network interface cleaning due to dry-run')
        else:
            logger.debug('Safety network interface cleaning')
            Network.force_cleanup()

    def _setup_tls_key_interception(args):
        """
        Issue #53: Log TLS pre-master keys.
        We preload libsslkeylog.so to patch openssl.so to intercept and dump keys.
        """
        if is_tls_transport(args.sipp_transport):
            app_dir = os.path.dirname(inspect.getfile(sipplauncher))
            libsslkeylog_so_path = os.path.join(app_dir, "../lib", "libsslkeylog.so")
            if os.path.isfile(libsslkeylog_so_path):
                os.environ["SSLKEYLOGFILE"] = "tls_premaster_keys.txt"
                os.environ["LD_PRELOAD"] = libsslkeylog_so_path
            else:
                raise Exception("{0} not found. Please verify it is installed".format(libsslkeylog_so_path))

    # Init ret code - pesimistic
    ret_code = 1

    args = sipplauncher.utils.Init.setup()
    try:
        logging.debug(args)
        _interfaces_cleaning(args)
        _setup_tls_key_interception(args)
        ret_code = Run.run(args)

        # Check pending signal just to display that we caught a signal.
        # Nothing useful besides that.
        check_signal()
    except SignalException as e:
        msg = "Captured signal {0}. Let's cleanup and leave".format(e)
        logger.info(msg)
        # Issue #7: SignalException is expected.
        # Traceback is logged and application cleanly exits.
        # Other exceptions cause abnormal termination.
        logger.debug(e, exc_info = True)
    except Exception as e:
        msg = "Captured exception {0}. Cleaning-up and leaving".format(e)
        logger.info(msg)
        logger.debug(e, exc_info = True)
    finally:
        _interfaces_cleaning(args)

    sys.exit(ret_code)

if __name__ == '__main__':
    my_main_fun()
