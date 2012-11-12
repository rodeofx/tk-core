"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Adds an engine to an environment.

"""

import optparse
import os
import logging
import sys
import re
import textwrap
import shutil
import datetime
import pprint
import platform

# make sure that the core API is part of the pythonpath
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path.append(python_path)

import tank
from tank.deploy.app_store_descriptor import TankAppStoreDescriptor
from tank.deploy.descriptor import AppDescriptor
from tank.platform import constants
from tank.platform import environment
from tank.deploy import administrator
from tank.errors import TankError


def _format_param_info(log, name, type, summary):
    """
    Formats a release notes summary output for an app, engine or core
    """
    log.info("/%s" % ("-" * 70))
    log.info("| Item:    %s" % name)
    log.info("| Type:    %s" % type)
    str_to_wrap = "Summary: %s" % summary
    for x in textwrap.wrap(str_to_wrap, width=68, initial_indent="| ", subsequent_indent="|          "):
        log.info(x)
    log.info("\%s" % ("-" * 70))


def add_engine(log, project_root, env_name, engine_name):
    """
    Adds an engine to an environment
    """
    log.info("")
    log.info("")
    log.info("Welcome to the Tank Engine installer!")
    log.info("")

    try:
        env_file = constants.get_environment_path(env_name, project_root)
        env = environment.Environment(env_file)
    except Exception, e:
        raise TankError("Environment '%s' could not be loaded! Error reported: %s" % (env_name, e))

    # find engine
    engine_descriptor = TankAppStoreDescriptor.find_item(project_root, AppDescriptor.ENGINE, engine_name)
    log.info("Successfully located %s..." % engine_descriptor)
    log.info("")

    # now assume a convention where we will name the engine instance that we create in the environment
    # the same as the short name of the engine
    engine_instance_name = engine_descriptor.get_system_name()

    # check so that there is not an app with that name already!
    if engine_instance_name in env.get_engines():
        raise TankError("Engine %s exists in the environment!" % engine_instance_name)

    # now make sure all constraints are okay
    try:
        administrator.check_constraints_for_item(project_root, engine_descriptor, env)
    except TankError, e:
        raise TankError("Cannot install: %s" % e)


    # okay to install!

    # note! Some of these methods further down are likely to pull the apps local
    # in order to do deep introspection. In order to provide better error reporting,
    # pull the apps local before we start
    if not engine_descriptor.exists_local():
        log.info("Downloading from App Store, hold on...")
        engine_descriptor.download_local()
        log.info("")

    # create required shotgun fields
    engine_descriptor.ensure_shotgun_fields_exist(project_root)

    # first get data for all new parameter values in the config
    param_diff = administrator.generate_settings_diff(engine_descriptor, None)

    if len(param_diff) > 0:
        log.info("Several settings are associated with this engine.")
        log.info("You will now be prompted to input values for all settings")
        log.info("that do not have default values defined.")
        log.info("")

    params = {}
    for (name, data) in param_diff.items():

        # output info about the setting
        log.info("")
        _format_param_info(log, name, data["type"], data["description"])

        # don't ask user to input anything for default values
        if data["value"] is not None:
            value = data["value"]
            if data["type"] == "hook":
                value = engine_descriptor.install_hook(log, value)
            params[name] = value

            # note that value can be a tuple so need to cast to str
            log.info("Auto-populated with default value '%s'" % str(value))

        else:

            # get value from user
            # loop around until happy
            input_valid = False
            while not input_valid:
                # ask user
                answer = raw_input("Please enter value (enter to skip): ")
                if answer == "":
                    # user chose to skip
                    log.warning("You skipped this value! Please update the environment by hand later!")
                    params[name] = None
                    input_valid = True
                else:
                    # validate value
                    try:
                        obj_value = administrator.validate_parameter(project_root, engine_descriptor, name, answer)
                    except Exception, e:
                        log.error("Validation failed: %s" % e)
                    else:
                        input_valid = True
                        params[name] = obj_value

    # awesome. got all the values we need.

    # next step is to add the new configuration values to the environment
    env.create_engine_settings(engine_instance_name)
    env.update_engine_settings(engine_instance_name, params)
    env.update_engine_location(engine_instance_name, engine_descriptor.get_location())

    log.info("")
    log.info("")
    log.info("Engine Installation Complete!")
    log.info("")
    if engine_descriptor.get_doc_url():
        log.info("For documentation, see %s" % engine_descriptor.get_doc_url())
    log.info("")
    log.info("")




def main(log):


    if len(sys.argv) == 1 or len(sys.argv) != 4:

        desc = """

Adds a new Engine to a Tank Environment.

    Syntax:  %(cmd)s project_root environment_name engine_name

    Example: %(cmd)s /mnt/shows/my_project rigging tk-maya

This command will download an engine from the Tank App Store and add it to
the specified project and environment. You will be prompted to fill in
the various configuration parameters that the app requires.
""" % {"cmd": sys.argv[0]}
        print desc
        return
    else:
        project_root = sys.argv[1]
        env_name = sys.argv[2]
        engine_name = sys.argv[3]

    # run actual activation
    add_engine(log, project_root, env_name, engine_name)

#######################################################################
if __name__ == "__main__":

    # set up logging channel for this script
    log = logging.getLogger("tank.add_engine")
    log.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)

    exit_code = 1
    try:
        # clear the umask so permissions are respected
        old_umask = os.umask(0)
        main(log)
        exit_code = 0
    except TankError, e:
        # one line report
        log.error("An error occurred: %s" % e)
    except Exception, e:
        # callstack
        log.exception("An error occurred: %s" % e)
    finally:
        os.umask(old_umask)

    sys.exit(exit_code)
