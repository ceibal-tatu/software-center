# Copyright (C) 2010 Canonical
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

from gi.repository import Gtk
import logging

from gettext import gettext as _

import softwarecenter.paths
from softwarecenter.ui.gtk3.dialogs import SimpleGtkbuilderDialog

from softwarecenter.distro import get_distro
from softwarecenter.enums import Icons
from softwarecenter.ui.gtk3.views.pkgnamesview import PackageNamesView

LOG = logging.getLogger(__name__)

#FIXME: These need to come from the main app
ICON_SIZE = 24

# for the unittests only
_DIALOG = None


def confirm_install(parent, app, db, icons):
    """Confirm install of the given app

       (currently only shows a dialog if a installed app needs to be removed
        in order to install the application)
    """
    cache = db._aptcache
    distro = get_distro()
    appdetails = app.get_details(db)

    if not appdetails.pkg:
        return True
    depends = cache.get_packages_removed_on_install(appdetails.pkg)
    if not depends:
        return True
    (primary, button_text) = distro.get_install_warning_text(cache,
        appdetails.pkg, app.name, depends)
    return _confirm_internal(parent, app, db, icons, primary,
        button_text, depends, cache)


def confirm_remove(parent, app, db, icons):
    """ Confirm removing of the given app """
    cache = db._aptcache
    distro = get_distro()
    appdetails = app.get_details(db)
    # FIXME: use
    #  backend = get_install_backend()
    #  backend.simulate_remove(app.pkgname)
    # once it works
    if not appdetails.pkg:
        return True
    if app.pkgname in distro.IMPORTANT_METAPACKAGES:
        displayed_depends = set([app.pkgname])
    else:
        displayed_depends = cache.get_packages_removed_on_remove(
            appdetails.pkg)
    if not displayed_depends:
        return True
    (primary, button_text) = distro.get_removal_warning_text(
        db._aptcache, appdetails.pkg, app.name, displayed_depends)
    return _confirm_internal(parent, app, db, icons, primary,
        button_text, displayed_depends, cache)


def _get_confirm_internal_dialog(parent, app, db, icons, primary,
                                 button_text, depends, cache):
    glade_dialog = SimpleGtkbuilderDialog(
        softwarecenter.paths.datadir, domain="software-center")
    dialog = glade_dialog.dialog_dependency_alert
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_default_size(360, -1)

    # get icon for the app
    appdetails = app.get_details(db)
    icon_name = appdetails.icon
    if icon_name is None or not icons.has_icon(icon_name):
        icon_name = Icons.MISSING_APP
    glade_dialog.image_package_icon.set_from_icon_name(icon_name,
                                                       Gtk.IconSize.DIALOG)

    # set the texts
    glade_dialog.label_dependency_primary.set_text(
        "<span font_weight=\"bold\" font_size=\"large\">%s</span>" % primary)
    glade_dialog.label_dependency_primary.set_use_markup(True)
    glade_dialog.button_dependency_do.set_label(button_text)

    # add the dependencies
    view = PackageNamesView(_("Dependency"), cache, depends, icons, ICON_SIZE,
        db)
    view.set_headers_visible(False)
    # FIXME: work out how not to select?/focus?/activate? first item
    glade_dialog.scrolledwindow_dependencies.add(view)
    glade_dialog.scrolledwindow_dependencies.show_all()
    return dialog


def _confirm_internal(*args):
    dialog = _get_confirm_internal_dialog(*args)
    global _DIALOG
    _DIALOG = dialog
    result = dialog.run()
    dialog.hide()
    return result == Gtk.ResponseType.ACCEPT
