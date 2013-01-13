"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Defines the base class for all Tank Engines.

"""

import os
import sys
import traceback

from .. import loader
from ..errors import TankError, TankEngineInitError
from ..deploy import descriptor

from . import application
from . import constants
from . import validation
from . import qt
from .environment import Environment
from .bundle import TankBundle
from .framework import setup_frameworks

class Engine(TankBundle):
    """
    Base class for an engine in Tank.
    """

    def __init__(self, tk, context, engine_instance_name, env):
        """
        Constructor. Takes the following parameters:
        
        :param tk: Tank API handle
        :param context: A context object to define the context on disk where the engine is operating
        :param engine_instance_name: The name of the engine as it has been defined in the environment.
        :param env: An Environment object to associate with this engine
        """
        
        self.__env = env
        self.__engine_instance_name = engine_instance_name
        self.__applications = {}
        self.__commands = {}
        self.__currently_initializing_app = None
        self.__created_qt_dialogs = []
        
        # get the engine settings
        settings = self.__env.get_engine_settings(self.__engine_instance_name)
        
        # get the descriptor representing the engine        
        descriptor = self.__env.get_engine_descriptor(self.__engine_instance_name)        
        
        # init base class
        TankBundle.__init__(self, tk, context, settings, descriptor)

        # check that the context contains all the info that the app needs
        validation.validate_context(descriptor, context)
        
        # make sure the current operating system platform is supported
        validation.validate_platform(descriptor)

        # Get the settings for the engine and then validate them
        engine_schema = descriptor.get_configuration_schema()
        validation.validate_settings(self.__engine_instance_name, tk, context, engine_schema, settings)
        
        # set up any frameworks defined
        setup_frameworks(self, self, self.__env, descriptor)
        
        # run the engine init
        self.log_debug("Engine init: Instantiating %s" % self)
        self.log_debug("Engine init: Current Context: %s" % context)

        # now if a folder named python is defined in the engine, add it to the pythonpath
        my_path = os.path.dirname(sys.modules[self.__module__].__file__)
        python_path = os.path.join(my_path, constants.BUNDLE_PYTHON_FOLDER)
        if os.path.exists(python_path):            
            # only append to python path if __init__.py does not exist
            # if __init__ exists, we should use the special tank import instead
            init_path = os.path.join(python_path, "__init__.py")
            if not os.path.exists(init_path):
                self.log_debug("Appending to PYTHONPATH: %s" % python_path)
                sys.path.append(python_path)

        # try to pull in QT classes and assign to tank.platform.qt.XYZ
        (core, gui) = self._define_qt_base()
        qt.QtCore = core
        qt.QtGui = gui
        qt.TankQDialog = self._define_qt_tankdialog()

        # initial init pass on engine
        self.init_engine()
        
        # now load all apps and their settings
        self.__load_apps()
        
        # now run the post app init
        self.post_app_init()
        
        # emit an engine started event
        tk.execute_hook(constants.TANK_ENGINE_INIT_HOOK_NAME, engine=self)
        
        
        self.log_debug("Init complete: %s" % self)
        
        
        
        
    def __repr__(self):
        return "<Tank Engine 0x%08x: %s, env: %s>" % (id(self),  
                                                           self.name, 
                                                           self.__env.name)

    ##########################################################################################
    # properties

    @property
    def environment(self):
        """
        A dictionary with information about the environment.
        Returns keys name, description and disk_location.
         
        :returns: dictionary
        """
        data = {}
        data["name"] = self.__env.name
        data["description"] = self.__env.description
        data["disk_location"] = self.__env.disk_location
        
        return data

    @property
    def instance_name(self):
        """
        The instance name for this engine. The instance name
        is the entry that is defined in the environment file.
        
        :returns: instance name as string
        """
        return self.__engine_instance_name

    @property
    def apps(self):
        """
        Dictionary of apps associated with this engine
        
        :returns: dictionary with keys being app name and values being app objects
        """
        return self.__applications
    
    @property
    def commands(self):
        """
        Returns a dictionary representing all the commands that have been registered
        by apps in this engine. Each dictionary item contains the following keys:
        
        * callback - function pointer to function to execute for this command
        * properties - dictionary with free form options - these are typically
          engine specific and driven by convention.
        
        :returns: commands dictionary, keyed by command name
        """
        return self.__commands
    
    @property
    def has_ui(self):
        """
        Indicates that the host application that the engine is connected to has a UI enabled.
        This always returns False for some engines (such as the shell engine) and may vary 
        for some engines, depending if the host application for example is in batch mode or
        UI mode.
        
        :returns: boolean value indicating if a UI currently exists
        """
        # default implementation is to assume a UI exists
        # this is since most engines are supporting a graphical application
        return True
    
    ##########################################################################################
    # init and destroy
    
    def init_engine(self):
        """
        Sets up the engine into an operational state.
        
        Implemented by deriving classes.
        """
        pass
    
    def post_app_init(self):
        """
        Runs after all apps have been initialized.
        
        Implemented by deriving classes.
        """
        pass
    
    def destroy(self):
        """
        Destroy all apps, then call destroy_engine so subclasses can add their own tear down code.
        
        This method should not be subclassed.
        """
        for fw in self.frameworks.values():
            fw._destroy_framework()

        self.__destroy_apps()
        
        self.log_debug("Destroying %s" % self)
        self.destroy_engine()
        
        # finally remove the current engine reference
        set_current_engine(None)
    
    def destroy_engine(self):
        """
        Called when the engine should tear down itself and all its apps.
        Implemented by deriving classes.
        """
        pass
    
    ##########################################################################################
    # public methods

    def register_command(self, name, callback, properties=None):
        """
        Register a command with a name and a callback function. Properties can store
        implementation specific configuration, like if a tooltip is supported.
        Typically called from the init_app() method of an app.
        """
        if properties is None:
            properties = {}
        if self.__currently_initializing_app is not None:
            # track which apps this request came from
            properties["app"] = self.__currently_initializing_app
        self.__commands[name] = { "callback": callback, "properties": properties }
        
                
    ##########################################################################################
    # simple batch queue
    
    def add_to_queue(self, name, method, args):
        raise NotImplementedError("Queue not implemented by this engine!")
    
    def report_progress(self, percent):
        raise NotImplementedError("Queue not implemented by this engine!")
    
    def execute_queue(self):
        raise NotImplementedError("Queue not implemented by this engine!")
    
    
    ##########################################################################################
    # logging interfaces

    def log_debug(self, msg):
        """
        Debug logging.
        Implemented in deriving class.
        """
        pass
    
    def log_info(self, msg):
        """
        Info logging.
        Implemented in deriving class.
        """
        pass
        
    def log_warning(self, msg):
        """
        Warning logging.
        Implemented in deriving class.
        """
        pass
    
    def log_error(self, msg):
        """
        Debug logging.
        Implemented in deriving class - however we provide a basic implementation here.
        """        
        # fall back to std out error reporting if deriving class does not implement this.
        sys.stderr("Error: %s\n" % msg)
    
    def log_exception(self, msg):
        """
        Helper method. Typically not overridden by deriving classes.
        This method is called inside an except clause and it creates an formatted error message
        which is logged as an error.
        """
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        
        if exc_traceback is None:
            # we are not inside an exception handler right now.
            # someone is calling log_exception from the running code.
            # in this case, present the current stack frame
            # and a sensible message
            stack_frame = traceback.extract_stack()
            traceback_str = "".join(traceback.format_list(stack_frame))
            exc_type = "OK"
            exc_value = "No current exception."
        
        else:    
            traceback_str = "".join( traceback.format_tb(exc_traceback))
        
        message = ""
        message += "\n\n"
        message += "Message: %s\n" % msg
        message += "Environment: %s\n" % self.__env.name
        message += "Exception: %s - %s\n" % (exc_type, exc_value)
        message += "Traceback (most recent call last):\n"
        message += traceback_str
        message += "\n\n"
        self.log_error(message)
        
    ##########################################################################################
    # private and protected methods
    
    def show_dialog(self, dialog_class, *args, **kwargs):
        """
        Shows a dialog window in a way suitable for this engine. The engine will attempt to 
        parent the dialog nicely to the host application.
        
        :param dialog_class: the class to instantiate. This must derive from tank.platform.qt.TankQDialog
        
        Additional parameters specified will be passed through to the dialog_class constructor.
        
        :returns: the created dialog object
        """
        from . import qt 
        if not issubclass(dialog_class, qt.TankQDialog):
            raise TankError("Class %s must derive from TankQDialog in order to be displayed." % dialog_class)
        
        dialog = dialog_class(*args, **kwargs)
        # keep a reference to all created dialogs to make GC happy
        self.__created_qt_dialogs.append(dialog)
        dialog.show()
        return dialog
    
    def show_modal(self, modal_class, *args, **kwargs):
        """
        Shows a modal dialog window in a way suitable for this engine. The engine will attempt to
        integrate it as seamlessly as possible into the host application. This call is blocking 
        until the user closes the dialog.
        
        :param dialog_class: the class to instantiate. This must derive from tank.platform.qt.TankQDialog
        
        Additional parameters specified will be passed through to the dialog_class constructor.

        :returns: a standard QT dialog status return code
        """
        from . import qt 
        if not issubclass(modal_class, qt.TankQDialog):
            raise TankError("Class %s must derive from TankQDialog in order to be displayed." % modal_class)
        
        dialog = modal_class(*args, **kwargs)
        return dialog.exec_()
    
    def _define_qt_base(self):
        """
        This will be called at initialisation time and will set 
        tank.platform.qt.QtCore and tank.platform.qt.QtGui.
        
        Defaults to a straight pyside - can be subclassed if 
        something else is desirable.
        
        :returns: tuple with (QtCoreClass, QtGuiClass)
        """
        try:
            from PySide import QtCore, QtGui
            return (QtCore, QtGui)
        except:
            self.log_debug("Default engine QT definition failed to find QT. "
                           "This may need to be subclassed.")
            return (None, None)
        
    
    def _define_qt_tankdialog(self):
        """
        This will be called at init and will set tank.platform.qt.TankQDialog
        to whatever class this method returns.
        
        Defaults to a straight passthrough class - can be sublcassed by 
        deriving engines. The class needs to be called TankQDialog and 
        take zero constructor parameters.
        
        :returns: TankQDialogClass
        
        """
        try:
            from .qt.tankqdialog import TankQDialog
            return TankQDialog
        except:
            self.log_debug("Default engine TankQDialog definition failed to find QT. "
                           "This may need to be subclassed.")
            return None
        
    ##########################################################################################
    # private         
        
    def __load_apps(self):
        """
        Populate the __applications dictionary, skip over apps that fail to initialize.
        """
        for app_instance_name in self.__env.get_apps(self.__engine_instance_name):
            
            # get a handle to the app bundle
            descriptor = self.__env.get_app_descriptor(self.__engine_instance_name, app_instance_name)
            if not descriptor.exists_local():
                self.log_error("Cannot start app! %s does not exist on disk." % descriptor)
                continue
            
            # Load settings for app - skip over the ones that don't validate
            try:
                # get the app settings data and validate it.
                app_schema = descriptor.get_configuration_schema()
                app_settings = self.__env.get_app_settings(self.__engine_instance_name, app_instance_name)

                # check that the context contains all the info that the app needs
                validation.validate_context(descriptor, self.context)
                
                # make sure the current operating system platform is supported
                validation.validate_platform(descriptor)
                                
                # for multi engine apps, make sure our engine is supported
                supported_engines = descriptor.get_supported_engines()
                if supported_engines and self.name not in supported_engines:
                    raise TankError("The app could not be loaded since it only supports "
                                    "the following engines: %s" % supported_engines)
                
                # now validate the configuration                
                validation.validate_settings(app_instance_name, self.tank, self.context, app_schema, app_settings)
                
                    
            except TankError, e:
                # validation error - probably some issue with the settings!
                # report this as an error message.
                self.log_error("App configuration Error for %s. It will not "
                               "be loaded. \n\nDetails: %s" % (app_instance_name, e))
                continue
            
            except Exception, e:
                # code execution error in the validation. Report this as an error 
                # with the engire call stack!
                self.log_exception("A general exception was caught while trying to" 
                                   "validate the configuration for app %s. "
                                   "The app will not be loaded.\n%s" % (app_instance_name, e))
                continue
            
                                    
            # load the app
            try:
                # now get the app location and resolve it into a version object
                app_dir = descriptor.get_path()

                # create the object, run the constructor
                app = application.get_application(self, app_dir, descriptor, app_settings)
                
                # load any frameworks required
                setup_frameworks(self, app, self.__env, descriptor)
                
                # track the init of the app
                self.__currently_initializing_app = app
                try:
                    app.init_app()
                finally:
                    self.__currently_initializing_app = None
            except Exception, e:
                self.log_exception("App %s failed to initialize - "
                                   "it will not be loaded:\n%s" % (app_dir, e))
            else:
                # note! Apps are keyed by their instance name, meaning that we 
                # could theoretically have multiple instances of the same app.
                self.__applications[app_instance_name] = app

    def __destroy_apps(self):
        """
        Call the destroy_app method on all loaded apps
        """
        
        for app in self.__applications.values():
            app._destroy_frameworks()
            self.log_debug("Destroying %s" % app)
            app.destroy_app()


##########################################################################################
# Engine management

g_current_engine = None

def set_current_engine(eng):
    """
    Sets the current engine
    """
    global g_current_engine
    g_current_engine = eng

def current_engine():
    """
    Returns the current engine
    """
    global g_current_engine
    return g_current_engine
        
def start_engine(engine_name, tk, context):
    """
    Creates an engine and makes it the current engine.
    Returns the newly created engine object.
    
    Raises TankEngineInitError if an engine could not be started 
    for the passed context.    
    """
    # first ensure that an engine is not currently running
    if current_engine():
        raise TankError("An engine (%s) is already running! Before you can start a new engine, "
                        "please shut down the previous one using the command " 
                        "tank.platform.current_engine().destroy()." % current_engine())
    
    # get the environment via the pick_environment hook
    env_name = __pick_environment(engine_name, tk, context)
    
    # get the path to the environment file given its name
    env_path = constants.get_environment_path(env_name, tk.project_path)
    
    # now we can instantiate a wrapper class around the data
    # this will load it and check basic things.
    env = Environment(env_path)
    
    # make sure that the environment has an engine instance with that name
    if not engine_name in env.get_engines():
        raise TankEngineInitError("Cannot find an engine instance %s in %s." % (engine_name, env))
    
    # get the location for our engine    
    engine_descriptor = env.get_engine_descriptor(engine_name)
    
    # make sure it exists locally
    if not engine_descriptor.exists_local():
        raise TankEngineInitError("Cannot start engine! %s does not exist on disk" % engine_descriptor)
    
    # get path to engine code
    engine_path = engine_descriptor.get_path()
    plugin_file = os.path.join(engine_path, constants.ENGINE_FILE)
    
    # Instantiate the engine
    class_obj = loader.load_plugin(plugin_file, Engine)
    obj = class_obj(tk, context, engine_name, env)
    
    # register this engine as the current engine
    set_current_engine(obj)
    
    return obj

##########################################################################################
# utilities

def __pick_environment(engine_name, tk, context):
    """
    Call out to the pick_environment core hook to determine which environment we should load
    based on the current context. The Shotgun engine provides its own implementation.
    """

    # for now, handle shotgun as a special case!
    # if the engine_name is shotgun, then return shotgun as the environment
    if engine_name in constants.SHOTGUN_ENGINES:
        return constants.SHOTGUN_ENVIRONMENT

    try:
        env_name = tk.execute_hook(constants.PICK_ENVIRONMENT_CORE_HOOK_NAME, context=context)
    except Exception, e:
        raise TankEngineInitError("Engine %s cannot initialize - the pick environment hook "
                                 "reported the following error: %s" % (engine_name, e))

    if env_name is None:
        # the pick_environment hook could not determine an environment
        # this may be because an incomplete Context was passed.
        # without an environment, engine creation cannot succeed.
        # raise an exception with a message
        raise TankEngineInitError("Engine %s cannot initialize - the pick environment hook was not "
                                  "able to return an environment to use, given the context %s. "
                                  "Usually this is because the context contains insufficient information "
                                  "for an environment to be determined." % (engine_name, context))

    return env_name
