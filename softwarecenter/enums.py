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

import os
from gettext import gettext as _

# pkgname of this app itself (used for "self-awareness", see spec)
SOFTWARE_CENTER_PKGNAME = 'software-center'

# name of the app in the keyring, untranslated, see bug #773214 for the
# rational
SOFTWARE_CENTER_NAME_KEYRING = "Ubuntu Software Center"
SOFTWARE_CENTER_SSO_DESCRIPTION = _(
    "To reinstall previous purchases, sign in to the "
    "Ubuntu Single Sign-On account you used to pay for them.")

SOFTWARE_CENTER_DEBUG_TABS = os.environ.get(
    'SOFTWARE_CENTER_DEBUG_TABS', False)

SOFTWARE_CENTER_BUY_HOST = os.environ.get(
    "SOFTWARE_CENTER_BUY_HOST", "https://software-center.ubuntu.com")

# buy-something base url
#BUY_SOMETHING_HOST = "http://localhost:8000/"
BUY_SOMETHING_HOST = os.environ.get(
    "SOFTWARE_CENTER_AGENT_HOST", SOFTWARE_CENTER_BUY_HOST)

BUY_SOMETHING_HOST_ANONYMOUS = BUY_SOMETHING_HOST

# recommender
RECOMMENDER_HOST = os.environ.get(
    "SOFTWARE_CENTER_RECOMMENDER_HOST", "https://rec.ubuntu.com")

# for the sso login.  ussoc expects the USSOC_SERVICE_URL environment variable
# to be a full path to the service root (including /api/1.0), not just the
# hostname, so we use the same convention for UBUNTU_SSO_SERVICE:
UBUNTU_SSO_SERVICE = os.environ.get(
    "USSOC_SERVICE_URL", "https://login.ubuntu.com/api/1.0")

# the terms-of-service links (the first is for display in a web browser
# as it has the header and footer, the second is for display in a dialog
# as it lacks them and so looks better)
SOFTWARE_CENTER_TOS_LINK = "https://apps.ubuntu.com/cat/tos/"
SOFTWARE_CENTER_TOS_LINK_NO_HEADER = "https://apps.ubuntu.com/cat/tos/plain/ "

# version of the database, every time something gets added (like
# terms for mime-type) increase this (but keep as a string!)
DB_SCHEMA_VERSION = "7"

# the default limit for a search
DEFAULT_SEARCH_LIMIT = 10000

# the server size "page" for ratings&reviews
REVIEWS_BATCH_PAGE_SIZE = 10


# the various "views" that the app has
class ViewPages:
    AVAILABLE = "view-page-available"
    INSTALLED = "view-page-installed"
    HISTORY = "view-page-history"
    SEPARATOR_1 = "view-page-separator-1"
    PENDING = "view-page-pending"
    CHANNEL = "view-page-channel"

    # items considered "permanent", that is, if a item disappears
    # (e.g. progress) then switch back to the previous on in permanent
    # views (LP:  #431907)
    PERMANENT_VIEWS = (AVAILABLE,
                       INSTALLED,
                       CHANNEL,
                       HISTORY
                       )


# define ID values for the various buttons found in the navigation bar
class NavButtons:
    CATEGORY = "category"
    LIST = "list"
    SUBCAT = "subcat"
    DETAILS = "details"
    SEARCH = "search"
    PURCHASE = "purchase"
    PREV_PURCHASES = "prev-purchases"


# define ID values for the action bar buttons
class ActionButtons:
    INSTALL = "install"
    ADD_TO_LAUNCHER = "add_to_launcher"
    CANCEL_ADD_TO_LAUNCHER = "cancel_add_to_launcher"


# icons
class Icons:
    APP_ICON_SIZE = 48

    FALLBACK = "applications-other"
    MISSING_APP = FALLBACK
    MISSING_PKG = "dialog-question"   # XXX: Not used?
    GENERIC_MISSING = "gtk-missing-image"
    INSTALLED_OVERLAY = "software-center-installed"


# sorting
class SortMethods:
    (UNSORTED,
     BY_ALPHABET,
     BY_SEARCH_RANKING,
     BY_CATALOGED_TIME,
     BY_TOP_RATED,
     ) = range(5)


class ReviewSortMethods:
    REVIEW_SORT_METHODS = ['helpful', 'newest']
    REVIEW_SORT_LIST_ENTRIES = [_('Most helpful first'), _('Newest first')]


# values used in the database
class XapianValues:
    APPNAME = 170
    PKGNAME = 171
    ICON = 172
    GETTEXT_DOMAIN = 173
    ARCHIVE_SECTION = 174
    ARCHIVE_ARCH = 175
    POPCON = 176
    SUMMARY = 177
    ARCHIVE_CHANNEL = 178
    DESKTOP_FILE = 179
    PRICE = 180
    ARCHIVE_PPA = 181
    ARCHIVE_DEB_LINE = 182
    ARCHIVE_SIGNING_KEY_ID = 183
    PURCHASED_DATE = 184
    SCREENSHOT_URLS = 185             # multiple urls, comma separated
    ICON_NEEDS_DOWNLOAD = 186         # no longer used
    THUMBNAIL_URL = 187               # no longer used
    SC_DESCRIPTION = 188
    APPNAME_UNTRANSLATED = 189
    ICON_URL = 190
    CATEGORIES = 191
    LICENSE_KEY = 192
    LICENSE_KEY_PATH = 193           # no longer used
    LICENSE = 194
    VIDEO_URL = 195
    DATE_PUBLISHED = 196
    SUPPORT_SITE_URL = 197
    VERSION_INFO = 198
    SC_SUPPORTED_DISTROS = 199
    WEBSITE = 200
    CURRENCY = 201
    # this is used to provide a cataloged time if there is no a-x-i in use
    # or if a-x-i is not available yet
    DB_CATALOGED_TIME = 202
    # download size as the agent provides it
    DOWNLOAD_SIZE = 203


class AppInfoFields:
    ARCH = 'ARCH'
    CHANNEL = 'CHANNEL'
    DEB_LINE = 'DEB_LINE'
    DEB_LINE_ORIG = 'DEB_LINE_ORIG'
    DOWNLOAD_SIZE = 'DOWNLOAD_SIZE'
    CATEGORIES = 'CATEGORIES'
    DATE_PUBLISHED = 'DATE_PUBLISHED'
    DESCRIPTION = 'DESCRIPTION'
    GENERIC_NAME = 'GENERIC_NAME'
    GETTEXT_DOMAIN = 'GETTEXT_DOMAIN'
    ICON = 'ICON'
    ICON_URL = 'ICON_URL'
    IGNORE = 'IGNORE'
    KEYWORDS = 'KEYWORDS'
    LICENSE = 'LICENSE'
    LICENSE_KEY = 'LICENSE_KEY'
    LICENSE_KEY_PATH = 'LICENSE_KEY_PATH'
    MIMETYPE = 'MIMETYPE'
    NAME = 'NAME'
    NAME_UNTRANSLATED = 'NAME_UNTRANSLATED'
    PACKAGE = 'PACKAGE'
    POPCON = 'POPCON'
    PPA = 'PPA'
    PRICE = 'PRICE'
    PURCHASED_DATE = 'PURCHASED_DATE'
    SECTION = 'SECTION'
    SIGNING_KEY_ID = 'SIGNING_KEY_ID'
    SCREENSHOT_URLS = 'SCREENSHOT_URLS'
    SUMMARY = 'SUMMARY'
    SUPPORT_URL = 'SUPPORT_URL'
    SUPPORTED_DISTROS = 'SUPPORTED_DISTROS'
    TAGS = 'TAGS'
    THUMBNAIL_URL = 'THUMBNAIL_URL'
    TYPE = 'TYPE'
    VERSION = 'VERSION'
    VIDEO_URL = 'VIDEO_URL'
    WEBSITE = 'WEBSITE'
    CURRENCY = 'CURRENCY'


# fake channels
AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME = "available-for-pay"


# custom keys for the new-apps repository, correspond
# control file custom fields:
#  XB-AppName, XB-Icon, XB-Screenshot-Url, XB-Thumbnail-Url, XB-Category
class CustomKeys:
    APPNAME = "AppName"
    ICON = "Icon"
    SCREENSHOT_URLS = "Screenshot-Url"
    THUMBNAIL_URL = "Thumbnail-Url"
    CATEGORY = "Category"


# pkg action state constants
class PkgStates:
    # current
    INSTALLED = "installed"
    UNINSTALLED = "uninstalled"
    UPGRADABLE = "upgradable"
    REINSTALLABLE = "reinstallable"
    # progress
    INSTALLING = "installing"
    REMOVING = "removing"
    UPGRADING = "upgrading"
    ENABLING_SOURCE = "enabling_source"
    INSTALLING_PURCHASED = "installing_purchase"
    # special
    NEEDS_SOURCE = "needs_source"
    NEEDS_PURCHASE = "needs_purchase"
    PURCHASED_BUT_REPO_MUST_BE_ENABLED = "purchased_but_repo_must_be_enabled"
    ERROR = "error"
    FORCE_VERSION = "force_version"
    # the package is not found in the DB or cache
    NOT_FOUND = "not_found"
    # its purchased but not found for the current series
    PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES = \
        "purchased_but_not_available_for_series"
    # something went wrong and we don't have a state for this PKG
    UNKNOWN = "unknown"


# visibility of non-applications in the search results
class NonAppVisibility:
    ALWAYS_VISIBLE = "non-apps-always-visible"
    MAYBE_VISIBLE = "non-apps-maybe-visible"
    NEVER_VISIBLE = "non-apps-never-visible"


# application actions
class AppActions:
    INSTALL = "install"
    REMOVE = "remove"
    UPGRADE = "upgrade"
    APPLY = "apply_changes"
    PURCHASE = "purchase"


# transaction types
class TransactionTypes:
    INSTALL = "install"
    REMOVE = "remove"
    UPGRADE = "upgrade"
    APPLY = "apply_changes"
    REPAIR = "repair_dependencies"


# Search separators
class SearchSeparators:
    REGULAR = " "
    PACKAGE = ","


# action values for recommendations feedback
class RecommenderFeedbackActions:
    VIEWED = "viewed"
    INSTALLED = "installed"

# mouse event codes for back/forward buttons
# TODO: consider whether we ought to get these values from gconf so that we
#       can be sure to use the corresponding values used by Nautilus:
#           /apps/nautilus/preferences/mouse_forward_button
#           /apps/nautilus/preferences/mouse_back_button
MOUSE_EVENT_FORWARD_BUTTON = 9
MOUSE_EVENT_BACK_BUTTON = 8

# delimiter for directory path separator in app-install
APP_INSTALL_PATH_DELIMITER = "__"

#carousel app limit to override limit in .menu file for category
TOP_RATED_CAROUSEL_LIMIT = 12
WHATS_NEW_CAROUSEL_LIMIT = 9
LOBBY_RECOMMENDATIONS_CAROUSEL_LIMIT = 9
DETAILS_RECOMMENDATIONS_CAROUSEL_LIMIT = 4

# Transaction ID for the "fake" purchase transaction
PURCHASE_TRANSACTION_ID = "FakePurchaseTransactionID"

from .version import VERSION, DISTRO, RELEASE, CODENAME
WEBKIT_USER_AGENT_SUFFIX = "SoftwareCenter/%s %s/%s (%s)" % (
    VERSION, DISTRO, RELEASE, CODENAME)

# global backend switch, prefer aptdaemon, if that can not be found, use PK
USE_PACKAGEKIT_BACKEND = False
try:
    import aptdaemon
    aptdaemon  # pyflakes
    USE_PACKAGEKIT_BACKEND = False
except ImportError:
    try:
        from gi.repository import PackageKitGlib
        PackageKitGlib  # pyflakes
        USE_PACKAGEKIT_BACKEND = True
    except ImportError:
        raise Exception("Need either aptdaemon or PackageKitGlib")
# allow force via env (useful for testing)
if "SOFTWARE_CENTER_FORCE_PACKAGEKIT" in os.environ:
    USE_PACKAGEKIT_BACKEND = True
