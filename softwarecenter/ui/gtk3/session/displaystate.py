# Copyright (C) 2009 Canonical
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

from softwarecenter.utils import utf8

# for DisplayState attribute type-checking
from softwarecenter.db.database import Application
from softwarecenter.db.categories import Category
from softwarecenter.backend.channel import SoftwareChannel
from softwarecenter.db.appfilter import AppFilter


class DisplayState(object):
    """ This represents the display state for the undo history """

    _attrs = {'category': (type(None), Category),
              'channel': (type(None), SoftwareChannel),
              'subcategory': (type(None), Category),
              'search_term': (str,),
              'application': (type(None), Application),
              'limit': (int,),
              'filter': (type(None), AppFilter),
              'vadjustment': (float, ),
              }

    def __init__(self):
        self.category = None
        self.channel = None
        self.subcategory = None
        self.search_term = ""
        self.application = None
        self.limit = 0
        self.filter = None
        self.vadjustment = 0.0

    def __setattr__(self, name, val):
        attrs = self._attrs
        if name not in attrs:
            raise AttributeError("The attr name \"%s\" is not permitted" %
                name)
            Gtk.main_quit()
        if not isinstance(val, attrs[name]):
            msg = "Attribute %s expects %s, got %s" % (name, attrs[name],
                type(val))
            raise TypeError(msg)
            Gtk.main_quit()
        return object.__setattr__(self, name, val)

    def __str__(self):
        s = utf8('%s %s "%s" %s %s') % \
                (self.category,
                 self.subcategory,
                 self.search_term,
                 self.application,
                 self.channel)
        return s

    def copy(self):
        state = DisplayState()
        state.channel = self.channel
        state.category = self.category
        state.subcategory = self.subcategory
        state.search_term = self.search_term
        state.application = self.application
        state.limit = self.limit
        if self.filter:
            state.filter = self.filter.copy()
        else:
            state.filter = None
        state.vadjustment = self.vadjustment
        return state

    def reset(self):
        self.channel = None
        self.category = None
        self.subcategory = None
        self.search_term = ""
        self.application = None
        self.limit = 0
        if self.filter:
            self.filter.reset()
        self.vadjustment = 0.0
