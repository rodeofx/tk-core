"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Defines the base class for all Tank Apps.

"""

import os
import sys
import uuid
import imp

from .. import hook
from .. import loader
from . import constants 

from ..errors import TankError

class Framework(object):
    """
    Base class for an app in Tank.
    """
    
    def __init__(self, engine, descriptor, settings):
        """
        Called by the framework loader. The constructor
        is not supposed to be overridden by deriving classes.
        
        :param engine: The engine instance to connect this framework to
        :param app_descriptor: descriptor describing location on disk etc.
        :param settings: a settings dictionary for this app
        """
        
        self.__descriptor = descriptor 
        self.__engine = engine
        self.__settings = settings        
        self.log_debug("Framework init: Instantiating %s" % self)

    def __repr__(self):        
        return "<Tank Framework 0x%08x: %s, engine: %s>" % (id(self), self.name, self.engine)

    ##########################################################################################
    # properties
    
    @property
    def name(self):
        """
        The short name of the app (e.g. tk-maya-publish)
        
        :returns: app name as string
        """
        return self.__descriptor.get_short_name()
    
    @property
    def display_name(self):
        """
        The displayname of the app (e.g. Maya Publish)
        
        :returns: app display name as string
        """
        return self.__descriptor.get_display_name()

    @property
    def description(self):
        """
        A short description of the app
        
        :returns: string
        """
        return self.__descriptor.get_description()

    @property
    def version(self):
        """
        The version of the app (e.g. v0.2.3)
        
        :returns: string representing the version
        """
        return self.__descriptor.get_version()
    
    @property
    def documentation_url(self):
        """
        Return the relevant documentation url for this app.
        
        :returns: url string, None if no documentation was found
        """
        return self.__descriptor.get_doc_url()            

    @property
    def disk_location(self):
        """
        The folder on disk where this app is located
        """
        path_to_this_file =  os.path.abspath(sys.modules[self.__module__].__file__)
        return os.path.dirname(path_to_this_file)
    
    @property
    def engine(self):
        """
        The engine that this app is connected to
        """
        return self.__engine
    
    @property
    def tank(self):
        """
        A shortcut to retrieve the Tank API instance from the current engine
        """
        return self.engine.tank

    @property
    def shotgun(self):
        """
        A shortcut to retrieve the Shotgun API instance from the current engine
        """
        return self.engine.shotgun
    
    @property
    def context(self):
        """
        A shortcut to retrieve the context from the current engine

        :returns: context object
        """
        return self.engine.context
                
        
    ##########################################################################################
    # init and destroy
        
    def init_framework(self):
        """
        Implemented by deriving classes in order to initialize the app
        Called by the engine as it loads the app.
        """
        pass

    def destroy_framework(self):
        """
        Implemented by deriving classes in order to tear down the app
        Called by the engine as it is being destroyed.
        """
        pass
    
    ##########################################################################################
    # public methods

    def get_setting(self, key, default=None):
        """
        Get a value from the app's settings

        :param str key: settings key
        :param default: default value to return
        """
        return self.__settings.get(key, default)
    
    def get_template(self, key):
        """
        A shortcut for looking up which template is referenced in the given setting, and
        calling get_template_by_name() on it.
        """
        return self.get_template_by_name(self.get_setting(key))
    
    def get_template_by_name(self, template_name):
        """
        Find the named template.
        """
        return self.tank.templates.get(template_name)
    
    def execute_hook(self, key, **kwargs):
        """
        Shortcut for grabbing the hook name used in the settings, 
        then calling execute_hook_by_name() on it.
        """
        hook_name = self.get_setting(key)
        return self.execute_hook_by_name(hook_name, **kwargs)
    
    def execute_hook_by_name(self, hook_name, **kwargs):
        """
        Execute an arbitrary hook located in the hooks folder for this project.
        The hook_name is the name of the python file in which the hook resides,
        without the file extension.
        
        In most use cases, the execute_hook method is the preferred way to 
        access a hook from an app.
        
        This method is typically only used when you want to execute an arbitrary
        list of hooks, for example if you want to run a series of arbitrary
        user defined pre-publish validation hooks.  
        """
        hook_folder = constants.get_hooks_folder(self.tank.project_path)
        hook_path = os.path.join(hook_folder, "%s.py" % hook_name)
        return hook.execute_hook(hook_path, self, **kwargs)
    
    ##########################################################################################
    # logging methods, delegated to the current engine

    def log_debug(self, msg):
        self.engine.log_debug(msg)

    def log_info(self, msg):
        self.engine.log_info(msg)

    def log_warning(self, msg):
        self.engine.log_warning(msg)

    def log_error(self, msg):
        self.engine.log_error(msg)

    def log_exception(self, msg):
        self.engine.log_exception(msg)

