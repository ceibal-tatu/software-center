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

import logging

import softwarecenter.plugin
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.backend.installbackend import get_install_backend

LOG = logging.getLogger(__name__)


class UnityWebappsActivationPlugin(softwarecenter.plugin.Plugin):
    """Webapps activation plugin """

    def init_plugin(self):
        self.pkg_info = get_pkg_info()
        self.install_backend = get_install_backend()
        self.install_backend.connect(
            "transaction-finished", self._on_transaction_finished)

    def _on_transaction_finished(self, backend, result):
        if not result.success or not result.pkgname:
            return
        if not result.pkgname in self.pkg_info:
            return
        pkg = self.pkg_info[result.pkgname]
        if not pkg.candidate:
            return
        webdomain = pkg.candidate.record.get("Ubuntu-Webapps-Domain", None)
        if webdomain:
            self.activate_unity_webapp_for_domain(webdomain)

    def activate_unity_webapp_for_domain(self, domain):
        try:
            from gi.repository import UnityWebapps
        except ImportError:
            LOG.warn("failed to import UnityWebapps GIR")
            return
        LOG.debug("activating webapp for domain '%s'", domain)
        UnityWebapps.permissions_allow_domain(domain)
