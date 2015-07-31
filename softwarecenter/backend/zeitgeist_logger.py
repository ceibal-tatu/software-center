# Copyright (C) 2013 Canonical
#
# Authors:
#  Marco Trevisan <marco.trevisan@canonical.com>
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

import logging
from softwarecenter.utils import get_desktop_id

LOG = logging.getLogger(__name__)
APPLICATION_URI_PREFIX = "application://"
HAVE_MODULE = False

try:
    from zeitgeist.client import ZeitgeistClient
    from zeitgeist import datamodel as ZeitgeistDataModel
    from zeitgeist.datamodel import (Event as ZeitgeistEvent,
                                     Subject as ZeitgeistSubject)
    HAVE_MODULE = True
except ImportError:
    LOG.warn("Support for Zeitgeist disabled")

class ZeitgeistLogger(object):
    def __init__(self, distro):
        self.distro = distro

    def __create_user_event(self):
        event = ZeitgeistEvent()
        event.actor = APPLICATION_URI_PREFIX + self.distro.get_app_id() + ".desktop"
        event.manifestation = ZeitgeistDataModel.Manifestation.EVENT_MANIFESTATION.USER_ACTIVITY
        return event

    def __create_app_subject(self, desktop_file):
        subject = ZeitgeistSubject()
        subject.interpretation = ZeitgeistDataModel.Interpretation.SOFTWARE
        subject.manifestation = ZeitgeistDataModel.Manifestation.SOFTWARE_ITEM
        subject.uri = APPLICATION_URI_PREFIX + get_desktop_id(desktop_file);
        subject.current_uri = subject.uri
        subject.mimetype = "application/x-desktop"
        return subject

    def log_install_event(self, desktop_file):
        """Logs an install event on Zeitgeist"""
        if not HAVE_MODULE:
            LOG.warn("No zeitgeist support, impossible to log event")
            return False

        if not desktop_file or not len(desktop_file):
            LOG.warn("Invalid desktop file provided, impossible to log event")
            return False

        subject = self.__create_app_subject(desktop_file)

        subject.text = "Installed with " + self.distro.get_app_name()
        event = self.__create_user_event()
        event.interpretation = ZeitgeistDataModel.Interpretation.EVENT_INTERPRETATION.CREATE_EVENT
        event.append_subject(subject)
        ZeitgeistClient().insert_event(event)

        subject.text = "Accessed by " + self.distro.get_app_name()
        event = self.__create_user_event()
        event.interpretation = ZeitgeistDataModel.Interpretation.EVENT_INTERPRETATION.ACCESS_EVENT
        event.append_subject(subject)
        ZeitgeistClient().insert_event(event)
        return True

    def log_uninstall_event(self, desktop_file):
        """Logs an uninstall event on Zeitgeist"""
        if not HAVE_MODULE:
            LOG.warn("No zeitgeist support, impossible to log event")
            return False

        if not desktop_file or not len(desktop_file):
            LOG.warn("Invalid desktop file provided, impossible to log event")
            return False

        subject = self.__create_app_subject(desktop_file)
        subject.text = "Uninstalled with " + self.distro.get_app_name()

        event = self.__create_user_event()
        event.interpretation = ZeitgeistDataModel.Interpretation.EVENT_INTERPRETATION.DELETE_EVENT
        event.append_subject(subject)
        ZeitgeistClient().insert_event(event)
        return True

