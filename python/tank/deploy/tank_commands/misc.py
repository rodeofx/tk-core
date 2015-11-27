# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from ...errors import TankError
from .action_base import Action

import code
import sys
import os

             

class ClearCacheAction(Action):
    """
    Action that clears the configuration caches
    """    
    def __init__(self):
        Action.__init__(self, 
                        "clear_shotgun_menu_cache", 
                        Action.TK_INSTANCE, 
                        ("Clears the Shotgun Menu Cache associated with this Configuration. "
                         "This is sometimes useful after complex configuration changes if new "
                         "or modified Toolkit menu items are not appearing inside Shotgun."), 
                        "Admin")

        # this method can be executed via the API
        self.supports_api = True
        
    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor. 
        Called when someone runs a tank command through the core API.
        
        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """
        return self._run(log)
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        
        :param log: std python logger
        :param args: command line args
        """
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        return self._run(log)
        
    def _run(self, log):
        """
        Actual execution payload
        """             
        cache_folder = self.tk.pipeline_configuration.get_shotgun_menu_cache_location()
        # cache files are on the form shotgun_mac_project.txt
        for f in os.listdir(cache_folder):
            if f.startswith("shotgun") and f.endswith(".txt"):
                full_path = os.path.join(cache_folder, f)
                log.debug("Deleting cache file %s..." % full_path)
                try:
                    os.remove(full_path)
                except:
                    log.warning("Could not delete cache file '%s'!" % full_path)
        
        log.info("The Shotgun menu cache has been cleared.")


class InterpreterAction(Action):
    """
    Base class for actions that involve running Python scripts, either interactively or from a file.
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor.
        """
        Action.__init__(self, *args, **kwargs)
        # hint that the shell engine should be started for this action, if possible
        self.wants_running_shell_engine = True

    def run_interactive(self, log, args):
        """
        Launches a Python interpreter. tk, shotgun, context and engine variables will
        be exported accordingly. How the interpreter is actually launched is up to the derived
        class in _run_interactive_internal.

        :param log: Log for outputting text.
        :param args: Arguments from the command line after the command's name.
        """
        self._validate_args(args)

        msg = []
        msg.append("Welcome to Shotgun Pipeline Toolkit Python!")
        msg.extend(sys.version.split("\n"))
        msg.append("Running on %s" % sys.platform)
        msg.append("")

        tk_locals = {}

        # add sgtk module to locals:
        import sgtk
        tk_locals["sgtk"] = sgtk

        # add some useful variables:
        if self.tk:
            tk_locals["tk"] = self.tk
            tk_locals["shotgun"] = self.tk.shotgun
            msg.append("- A tk API handle is available via the tk variable")
            msg.append("- A Shotgun API handle is available via the shotgun variable")

        if self.context:
            tk_locals["context"] = self.context
            msg.append("- Your current context is stored in the context variable")

        if self.engine:
            tk_locals["engine"] = self.engine
            msg.append("- The shell engine can be accessed via the engine variable")

        for line in msg:
            log.info(line)
        log.info("")

        self._run_interactive_internal(log, tk_locals, args)


class InteractiveShellAction(InterpreterAction):
    """
    Action that starts an interactive shell
    """
    def __init__(self):
        """
        Constructor.
        """
        InterpreterAction.__init__(
            self,
            "shell",
            Action.TK_INSTANCE,
            "Starts an interactive Python shell for the current location.",
            "Developer"
        )

    def _validate_args(self, args):
        """
        Validates arguments for this command.

        :param args: Arguments passed in.

        :raises TankError: Raised if there are no arguments.
        """
        if len(args) != 0:
            raise TankError("This command takes no arguments!")

    def _run_interactive_internal(self, log, locals, args):
        """
        Launches an interactive Python interpreter.

        :param log: Log for outputting text.
        :param locals: List of locals that need to be exposed to the interpreter.
        :param args: Arguments from the command line after the command's name. Not used.
        """
        # attempt install tab command completion
        try:
            import rlcompleter
            import readline

            if "libedit" in readline.__doc__:
                # macosx, some versions - see 
                # http://stackoverflow.com/questions/7116038
                readline.parse_and_bind("bind ^I rl_complete")
            else:
                readline.parse_and_bind("tab: complete")
        except:
            pass

        code.interact(local=locals)


class ScriptAction(InterpreterAction):
    """
    Action that starts an interactive shell
    """
    def __init__(self):
        """
        Constructor.
        """
        InterpreterAction.__init__(
            self,
            "script",
            Action.TK_INSTANCE,
            "Runs a script using the current environment.",
            "Developer"
        )

    def _validate_args(self, args):
        """
        Validates arguments for this command.

        :param args: Arguments passed in.

        :raises TankError: Raised if there are no arguments.
        """
        if len(args) == 0:
            raise TankError("You must specify at least one script.")

    def _run_interactive_internal(self, log, locals, args):
        """
        Runs the script specified on the command line.

        :param log: Log for outputting text.
        :param locals: List of locals that need to be exposed to the interpreter.
        :param args: Arguments from the command line after the command's name. Not used.
        """

        log.info("Running script '%s'." % args[0])
        if not os.path.exists(args[0]):
            raise TankError("The script '%s' can't be found!")

        locals["log"] = log

        # Override sys.argv so the script can access the arguments as if it was
        # a regular python script.
        sys.argv = args
        code.InteractiveInterpreter(locals=locals).runcode(open(args[0]))
