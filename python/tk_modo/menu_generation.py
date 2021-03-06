# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Menu handling for Modo

"""

import tank
import sys
import os
import unicodedata

from tank.platform.qt import QtGui, QtCore
from tank.platform import restart
import modoshotgunsupport



def menu_callback(cb):
    modoshotgunsupport.log("menu item called",type="DEBUG")
    cb()

class MenuGenerator(object):
    """
    Menu generation functionality for Maya
    """

    def __init__(self, engine):
        self._engine = engine
        self._dialogs = []

    ##########################################################################################
    # public methods

    def create_menu(self, *args):
        """
        Render the entire Shotgun menu.
        In order to have commands enable/disable themselves based on the enable_callback, 
        re-create the menu items every time.
        """
        #import rpdb2;rpdb2.start_embedded_debugger("1234")

        base_widget = modoshotgunsupport.get_shotgun_widget()
        self._menu_handle = menu = base_widget.get_menu()
        #menu.clear()
        
        # now add the context item on top of the main menu
        self._context_menu = self._add_context_menu()

        menu.addSeparator()

        # now enumerate all items and create menu objects for them
        menu_items = []
        for (cmd_name, cmd_details) in self._engine.commands.items():
             menu_items.append( AppCommand(cmd_name, cmd_details) )

        # sort list of commands in name order
        menu_items.sort(key=lambda x: x.name) 

        # now add favourites
        for fav in self._engine.get_setting("menu_favourites"):
            app_instance_name = fav["app_instance"]
            menu_name = fav["name"]
            # scan through all menu items
            for cmd in menu_items:                 
                 if cmd.get_app_instance_name() == app_instance_name and cmd.name == menu_name:
                     # found our match!
                     cmd.add_command_to_menu(self._menu_handle)
                     # mark as a favourite item
                     cmd.favourite = True

        menu.addSeparator()

        # now go through all of the menu items.
        # separate them out into various sections
        commands_by_app = {}
        
        for cmd in menu_items:

            if cmd.get_type() == "context_menu":
                # context menu!
                cmd.add_command_to_menu(self._context_menu)             
                
            else:
                # normal menu
                app_name = cmd.get_app_name()
                if app_name is None:
                    # un-parented app
                    app_name = "Other Items" 
                if not app_name in commands_by_app:
                    commands_by_app[app_name] = []
                commands_by_app[app_name].append(cmd)
        
        # now add all apps to main menu
        self._add_app_menu(commands_by_app)
        
    ##########################################################################################
    # context menu and UI

    def _add_context_menu(self):
        """
        Adds a context menu which displays the current context
        """        
        
        ctx = self._engine.context
        ctx_name = str(ctx)        

        # # create the menu object

        ctx_menu = QtGui.QMenu(ctx_name)
        self._menu_handle.addMenu(ctx_menu)        

        action_reload = ctx_menu.addAction("Reload Shotgun", self._reload_sg)
        action_reload = ctx_menu.addAction("Jump to Shotgun", self._jump_to_sg)
        action_reload = ctx_menu.addAction("Jump to File System", self._jump_to_fs)
        ctx_menu.addSeparator()

        return ctx_menu
                        
                        
    def _jump_to_sg(self):
        """
        Jump to shotgun, launch web browser
        """        
        url = self._engine.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
        
        
    def _reload_sg(self):
        """
        Reload Shotgun scripts
        """        
        restart()
        
        
    def _jump_to_fs(self):
        """
        Jump from context to FS
        """
        # launch one window for each location on disk        
        paths = self._engine.context.filesystem_locations
        for disk_location in paths:
                
            # get the setting        
            system = sys.platform
            
            # run the app
            if system == "linux2":
                cmd = 'xdg-open "%s"' % disk_location
            elif system == "darwin":
                cmd = 'open "%s"' % disk_location
            elif system == "win32":
                cmd = 'cmd.exe /C start "Folder" "%s"' % disk_location
            else:
                raise Exception("Platform '%s' is not supported." % system)
            
            exit_code = os.system(cmd)
            if exit_code != 0:
                self._engine.log_error("Failed to launch '%s'!" % cmd)
        
                        
    ##########################################################################################
    # app menus
        
        
    def _add_app_menu(self, commands_by_app):
        """
        Add all apps to the main menu, process them one by one.
        """
        for app_name in sorted(commands_by_app.keys()):
            
            if len(commands_by_app[app_name]) > 1:
                # more than one menu entry fort his app
                # make a sub menu and put all items in the sub menu
                app_menu = QtGui.QMenu(app_name)
                self._menu_handle.addMenu(app_menu)
                
                # get the list of menu cmds for this app
                cmds = commands_by_app[app_name]
                # make sure it is in alphabetical order
                cmds.sort(key=lambda x: x.name) 
                
                for cmd in cmds:
                    cmd.add_command_to_menu(app_menu)
            
            else:

                # this app only has a single entry. 
                # display that on the menu
                # todo: Should this be labelled with the name of the app 
                # or the name of the menu item? Not sure.
                cmd_obj = commands_by_app[app_name][0]
                if not cmd_obj.favourite:
                    # skip favourites since they are alreay on the menu
                    cmd_obj.add_command_to_menu(self._menu_handle)
                                
        
        
    
            
class AppCommand(object):
    """
    Wraps around a single command that you get from engine.commands
    """
    
    def __init__(self, name, command_dict):        
        self.name = name
        self.properties = command_dict["properties"]
        self.callback = command_dict["callback"]
        self.favourite = False
        
    def get_app_name(self):
        """
        Returns the name of the app that this command belongs to
        """
        if "app" in self.properties:
            return self.properties["app"].display_name
        return None
        
    def get_app_instance_name(self):
        """
        Returns the name of the app instance, as defined in the environment.
        Returns None if not found.
        """
        if "app" not in self.properties:
            return None
        
        app_instance = self.properties["app"]
        engine = app_instance.engine

        for (app_instance_name, app_instance_obj) in engine.apps.items():
            if app_instance_obj == app_instance:
                # found our app!
                return app_instance_name
            
        return None
        
    def get_documentation_url_str(self):
        """
        Returns the documentation as a str
        """
        if "app" in self.properties:
            app = self.properties["app"]
            doc_url = app.documentation_url
            # deal with nuke's inability to handle unicode. #fail
            if doc_url.__class__ == unicode:
                doc_url = unicodedata.normalize('NFKD', doc_url).encode('ascii', 'ignore')
            return doc_url

        return None
        
    def get_type(self):
        """
        returns the command type. Returns node, custom_pane or default
        """
        return self.properties.get("type", "default")
        
    def add_command_to_menu(self, menu):
        """
        Adds an app command to the menu
        """
            
        # create menu sub-tree if need to:
        # Support menu items seperated by '/'
        parent_menu = menu
        parts = self.name.split("/")
        for item_label in parts[:-1]:

            # see if there is already a sub-menu item
            sub_menu = self._find_sub_menu_item(parent_menu, item_label)
            if sub_menu:
                # already have sub menu
                parent_menu = sub_menu
            else:
                new_sub_menu = QtGui.QMenu(item_label)
                parent_menu.addMenu(new_sub_menu)
                parent_menu = new_sub_menu
            
        # finally create the command menu item:
        menu_action = parent_menu.addAction(parts[-1])
        #menu_action.triggered.connect(self.callback)
        menu_action.triggered.connect(lambda: menu_callback(self.callback))
        if "tooltip" in self.properties:
            menu_action.setToolTip(self.properties["tooltip"])
        
        if "enable_callback" in self.properties:
            menu_action.setEnabled( self.properties["enable_callback"]() )
        
    def _find_sub_menu_item(self, menu, label):
        """
        Find the 'sub-menu' menu item with the given label
        """

        for child in menu.children():
            if isinstance(child, QtGui.QMenu):
                if child.title() == label:
                    return child

        return None
