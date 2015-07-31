# Copyright (C) 2011-2014 Canonical Ltd.
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

# py3 compat
try:
    from configparser import SafeConfigParser
    SafeConfigParser  # pyflakes
except ImportError:
    from ConfigParser import SafeConfigParser
import os
import logging

from paths import SOFTWARE_CENTER_CONFIG_FILE

LOG = logging.getLogger(__name__)


class SoftwareCenterConfig(SafeConfigParser, object):

    SECTIONS = ("general", "reviews")

    def __init__(self, config):
        super(SoftwareCenterConfig, self).__init__()
        # imported here to avoid cycle
        from utils import safe_makedirs
        safe_makedirs(os.path.dirname(config))
        # we always want this sections, even on fresh installs
        for section in self.SECTIONS:
            self.add_section(section)

        # read the config
        self.configfile = config
        try:
            self.read(self.configfile)
        except Exception as e:
            # don't crash on a corrupted config file
            LOG.warn("Could not read the config file '%s': %s",
                     self.configfile, e)
            pass

    def write(self):
        tmpname = self.configfile + ".new"
        # see LP: #996333, its ok to remove the old configfile as
        # its rewritten anyway
        from utils import ensure_file_writable_and_delete_if_not
        ensure_file_writable_and_delete_if_not(tmpname)
        ensure_file_writable_and_delete_if_not(self.configfile)
        try:
            f = open(tmpname, "w")
            SafeConfigParser.write(self, f)
            f.close()
            os.rename(tmpname, self.configfile)
        except Exception as e:
            # don't crash if there's an error when writing to the config file
            # (LP: #996333)
            LOG.warn("Could not write the config file '%s': %s",
                     self.configfile, e)
            pass

    # generic property helpers
    def _generic_get(self, option, section="general", default=""):
        if not self.has_option(section, option):
            self.set(section, option, default)
        return self.get(section, option)

    def _generic_set(self, option, value, section="general"):
        self.set(section, option, value)

    def _generic_getbool(self, option, section="general", default=False):
        if not self.has_option(section, option):
            self.set(section, option, str(default))
        return self.getboolean(section, option)

    def _generic_setbool(self, option, value, section="general"):
        if value:
            self.set(section, option, "True")
        else:
            self.set(section, option, "False")

    # our properties that will automatically sync with the configfile
    add_to_unity_launcher = property(
        lambda self: self._generic_getbool("add_to_launcher", default=True),
        lambda self, value: self._generic_setbool("add_to_launcher", value),
        None,
        "Defines if apps should get added to the unity launcher")
    app_window_maximized = property(
        lambda self: self._generic_getbool("maximized", default=False),
        lambda self, value: self._generic_setbool("maximized", value),
        None,
        "Defines if apps should be started maximized")
    recommender_uuid = property(
        # remove any dashes for the case where a user has opted in before
        # we required UUIDs without dashes
        lambda self: self._generic_get("recommender_uuid").replace("-", ""),
        lambda self, value: self._generic_set("recommender_uuid",
                                              value),
        None,
        "The UUID generated for the recommendations")
    recommender_profile_id = property(
        lambda self: self._generic_get("recommender_profile_id"),
        lambda self, value: self._generic_set("recommender_profile_id", value),
        None,
        "The recommendation profile id of the user")
    recommender_opt_in_requested = property(
        lambda self: self._generic_getbool(
            "recommender_opt_in_requested", default=False),
        lambda self, value: self._generic_setbool(
            "recommender_opt_in_requested", value),
        None,
        "The user has requested a opt-in and its pending")
    user_accepted_tos = property(
        lambda self: self._generic_getbool("accepted_tos", default=False),
        lambda self, value: self._generic_setbool("accepted_tos", value),
        None,
        "The user has accepted the terms-of-service")
    email = property(
        lambda self: self._generic_get("email", default=""),
        lambda self, value: self._generic_set("email", value),
        None,
        "The preferred email of the user, automatically set via ubuntu-sso")
    # the review section
    reviews_username = property(
        lambda self: self._generic_get(
            "username", section="reviews", default=""),
        lambda self, value: self._generic_set(
            "username", value, section="reviews"),
        None,
        "The sso username")
    reviews_post_via_gwibber = property(
        lambda self: self._generic_getbool(
            "gwibber_send", section="reviews", default=False),
        lambda self, value: self._generic_setbool(
            "gwibber_send", value, section="reviews"),
        None,
        "Also post reviews via gwibber")
    reviews_gwibber_account_id = property(
        lambda self: self._generic_get(
            "account_id", section="reviews", default=""),
        lambda self, value: self._generic_setbool(
            "account_id", value, section="reviews"),
        None,
        "The account id to use when sending via gwibber")

    # app_window_size is special as its a tuple
    def _app_window_size_get(self):
        size_as_string = self._generic_get("size", default="-1, -1")
        return [int(v) for v in size_as_string.split(",")]

    def _app_window_size_set(self, size_tuple):
        size_as_string = "%s, %s" % (size_tuple[0], size_tuple[1])
        self._generic_set("size", size_as_string)
    app_window_size = property(
        _app_window_size_get, _app_window_size_set,
        None, "Defines the size of the application window as a tuple (x,y)")


# one global instance of the config
_software_center_config = None


def get_config(filename=SOFTWARE_CENTER_CONFIG_FILE):
    """ get the global config class """
    global _software_center_config
    if not _software_center_config:
        _software_center_config = SoftwareCenterConfig(filename)
    return _software_center_config
