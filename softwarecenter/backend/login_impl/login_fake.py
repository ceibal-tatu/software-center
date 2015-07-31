#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2012 Canonical
#
# Authors:
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
import random
import string

from softwarecenter.backend.fake_review_settings import (
    FakeReviewSettings,
    network_delay,
)
from softwarecenter.backend.login import LoginBackend

LOG = logging.getLogger(__name__)


class LoginBackendDbusSSOFake(LoginBackend):

    def __init__(self, window_id, appname, help_text):
        super(LoginBackendDbusSSOFake, self).__init__()
        self.appname = appname
        self.help_text = help_text
        self._window_id = window_id
        self._fake_settings = FakeReviewSettings()

    @network_delay
    def login(self):
        response = self._fake_settings.get_setting('login_response')

        if response == "successful":
            self.emit("login-successful", self._return_credentials())
        elif response == "failed":
            self.emit("login-failed")
        elif response == "denied":
            self.cancel_login()

        return

    def login_or_register(self):
        #fake functionality for this is no different to fake login()
        self.login()
        return

    def _random_unicode_string(self, length):
        retval = ''
        for i in range(0, length):
            retval = retval + random.choice(string.letters + string.digits)
        return retval.decode('utf-8')

    def _return_credentials(self):
        c = dbus.Dictionary(
            {
                dbus.String(u'consumer_secret'): dbus.String(
                    self._random_unicode_string(30)),
                dbus.String(u'token'): dbus.String(
                    self._random_unicode_string(50)),
                dbus.String(u'consumer_key'): dbus.String(
                    self._random_unicode_string(7)),
                dbus.String(u'name'): dbus.String(
                    'Ubuntu Software Center @ ' +
                    self._random_unicode_string(6)),
                dbus.String(u'token_secret'): dbus.String(
                    self._random_unicode_string(50))
            },
            signature=dbus.Signature('ss')
        )
        return c
