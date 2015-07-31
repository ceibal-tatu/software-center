# Copyright (C) 2011 Canonical
#
# Authors:
#  Gary Lasker
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import dbus
import logging
import os
import tempfile

LOG = logging.getLogger(__name__)


class UnityLauncherInfo(object):
    """ Simple class to keep track of application details needed for
        Unity launcher integration
    """
    def __init__(self,
                 name,
                 icon_name,
                 icon_file_path,
                 icon_x,
                 icon_y,
                 icon_size,
                 installed_desktop_file_path,
                 trans_id):
        self.name = name
        self.icon_name = icon_name
        self.icon_file_path = icon_file_path
        self.icon_x = icon_x
        self.icon_y = icon_y
        self.icon_size = icon_size
        self.installed_desktop_file_path = installed_desktop_file_path
        self.trans_id = trans_id


class UnityLauncher(object):
    """ Implements the integration between Software Center and the Unity
        launcher
    """

    def __init__(self):
        self._pkgname_to_temp_desktop_file = {}

    def _get_launcher_dbus_iface(self):
        bus = dbus.SessionBus()
        launcher_obj = bus.get_object('com.canonical.Unity.Launcher',
                                      '/com/canonical/Unity/Launcher')
        launcher_iface = dbus.Interface(launcher_obj,
                                        'com.canonical.Unity.Launcher')
        return launcher_iface

    def cancel_application_to_launcher(self, pkgname):
        filename = self._pkgname_to_temp_desktop_file.pop(pkgname, None)
        if filename:
            os.unlink(filename)

    def _get_temp_desktop_file(self, pkgname, launcher_info):
        with tempfile.NamedTemporaryFile(prefix="software-center-agent:",
                                         suffix=":%s.desktop" % pkgname,
                                         delete=False) as fp:
            s = """
[Desktop Entry]
Name=%(name)s
Icon=%(icon_file_path)s
Type=Application""" % {'name': launcher_info.name,
                       'icon_file_path': launcher_info.icon_file_path,
                       }
            fp.write(s)
            fp.flush()
            LOG.debug("create temp desktop file '%s'" % fp.name)
            return fp.name

    def send_application_to_launcher(self, pkgname, launcher_info):
        """ send a dbus message to the Unity launcher service to initiate
            the add-to-launcher functionality for the specified application
        """

        # stuff from the agent has no desktop file so we create a fake
        # one here just for the install
        if (launcher_info.installed_desktop_file_path ==
            "software-center-agent"):
            temp_desktop = self._get_temp_desktop_file(pkgname, launcher_info)
            launcher_info.installed_desktop_file_path = temp_desktop
            self._pkgname_to_temp_desktop_file[pkgname] = temp_desktop

        LOG.debug("sending dbus signal to Unity launcher for application: %r",
                  launcher_info.name)
        LOG.debug("  launcher_info: icon_file_path: %r ",
                     launcher_info.icon_file_path)
        LOG.debug("  launcher_info.installed_desktop_file_path: %r",
                     launcher_info.installed_desktop_file_path)
        LOG.debug("  launcher_info.trans_id: %r", launcher_info.trans_id)
        LOG.debug("  launcher_info.icon_x: %r icon_y: %r",
                     launcher_info.icon_x, launcher_info.icon_y)

        try:
            launcher_iface = self._get_launcher_dbus_iface()
            launcher_iface.AddLauncherItemFromPosition(
                    launcher_info.name,
                    launcher_info.icon_file_path,
                    launcher_info.icon_x,
                    launcher_info.icon_y,
                    launcher_info.icon_size,
                    launcher_info.installed_desktop_file_path,
                    launcher_info.trans_id)
        except Exception as e:
            LOG.warn("could not send dbus signal to the Unity launcher: (%s)",
                     e)
