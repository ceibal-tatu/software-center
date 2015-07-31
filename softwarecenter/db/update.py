#!/usr/bin/python
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

import logging
import json
import re
import os
import string
import shutil
import time
import xapian

from aptsources.sourceslist import SourceEntry
from gi.repository import GLib
from piston_mini_client import PistonResponseObject

from softwarecenter.backend.scagent import SoftwareCenterAgent
from softwarecenter.backend.ubuntusso import UbuntuSSO
from softwarecenter.distro import get_distro
from softwarecenter.utils import utf8

from gettext import gettext as _

# py3 compat
try:
    from configparser import RawConfigParser, NoOptionError
    RawConfigParser  # pyflakes
    NoOptionError  # pyflakes
except ImportError:
    from ConfigParser import RawConfigParser, NoOptionError

# py3 compat
try:
    import cPickle as pickle
    pickle  # pyflakes
except ImportError:
    import pickle


from glob import glob
from urlparse import urlparse

import softwarecenter.paths

from softwarecenter.enums import (
    AppInfoFields,
    AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
    DB_SCHEMA_VERSION,
    XapianValues,
)
from softwarecenter.db.database import parse_axi_values_file

from locale import getdefaultlocale
import gettext


from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.distro import (
    get_current_arch,
    get_foreign_architectures,
)
from softwarecenter.region import (
    get_region_cached,
    REGION_BLACKLIST_TAG,
    REGION_WHITELIST_TAG,
)


# weights for the different fields
WEIGHT_DESKTOP_NAME = 10
WEIGHT_DESKTOP_KEYWORD = 5
WEIGHT_DESKTOP_GENERICNAME = 3
WEIGHT_DESKTOP_COMMENT = 1

WEIGHT_APT_PKGNAME = 8
WEIGHT_APT_SUMMARY = 5
WEIGHT_APT_DESCRIPTION = 1

# some globals (FIXME: that really need to go into a new Update class)
popcon_max = 0
seen = set()
LOG = logging.getLogger(__name__)

# init axi
axi_values = parse_axi_values_file()

# get cataloged_times
cataloged_times = {}
CF = "/var/lib/apt-xapian-index/cataloged_times.p"
if os.path.exists(CF):
    try:
        cataloged_times = pickle.load(open(CF))
    except Exception as e:
        LOG.warn("failed to load file %s: %s", CF, e)
del CF

# Enable Xapian's CJK tokenizer (see LP: #745243)
os.environ['XAPIAN_CJK_NGRAM'] = '1'


def process_date(date):
    result = None
    if re.match("\d+-\d+-\d+ \d+:\d+:\d+", date):
        # strip the subseconds from the end of the published date string
        result = str(date).split(".")[0]
    return result


def process_popcon(popcon):
    xapian.sortable_serialise(float(popcon))
    return popcon


def get_pkgname_terms(pkgname):
    result = ["AP" + pkgname,
              # workaround xapian oddness by providing a "mangled" version
              # with a different prefix
              "APM" + pkgname.replace('-', '_')]
    return result


def get_default_locale():
    return getdefaultlocale(('LANGUAGE', 'LANG', 'LC_CTYPE', 'LC_ALL'))[0]


class AppInfoParserBase(object):
    """Base class for reading AppInfo meta-data."""

    # map Application Info Fields to xapian "values"
    FIELD_TO_XAPIAN = {
        AppInfoFields.ARCH: XapianValues.ARCHIVE_ARCH,
        AppInfoFields.CHANNEL: XapianValues.ARCHIVE_CHANNEL,
        AppInfoFields.DEB_LINE: XapianValues.ARCHIVE_DEB_LINE,
        AppInfoFields.DESCRIPTION: XapianValues.SC_DESCRIPTION,
        AppInfoFields.DOWNLOAD_SIZE: XapianValues.DOWNLOAD_SIZE,
        AppInfoFields.CATEGORIES: XapianValues.CATEGORIES,
        AppInfoFields.CURRENCY: XapianValues.CURRENCY,
        AppInfoFields.DATE_PUBLISHED: XapianValues.DATE_PUBLISHED,
        AppInfoFields.ICON: XapianValues.ICON,
        AppInfoFields.ICON_URL: XapianValues.ICON_URL,
        AppInfoFields.GETTEXT_DOMAIN: XapianValues.GETTEXT_DOMAIN,
        AppInfoFields.LICENSE: XapianValues.LICENSE,
        AppInfoFields.LICENSE_KEY: XapianValues.LICENSE_KEY,
        AppInfoFields.LICENSE_KEY_PATH: XapianValues.LICENSE_KEY_PATH,
        AppInfoFields.NAME: XapianValues.APPNAME,
        AppInfoFields.NAME_UNTRANSLATED: XapianValues.APPNAME_UNTRANSLATED,
        AppInfoFields.PACKAGE: XapianValues.PKGNAME,
        AppInfoFields.POPCON: XapianValues.POPCON,
        AppInfoFields.PPA: XapianValues.ARCHIVE_PPA,
        AppInfoFields.PRICE: XapianValues.PRICE,
        AppInfoFields.PURCHASED_DATE: XapianValues.PURCHASED_DATE,
        AppInfoFields.SECTION: XapianValues.ARCHIVE_SECTION,
        AppInfoFields.SIGNING_KEY_ID: XapianValues.ARCHIVE_SIGNING_KEY_ID,
        AppInfoFields.SCREENSHOT_URLS: XapianValues.SCREENSHOT_URLS,
        AppInfoFields.SUMMARY: XapianValues.SUMMARY,
        AppInfoFields.SUPPORT_URL: XapianValues.SUPPORT_SITE_URL,
        AppInfoFields.SUPPORTED_DISTROS: XapianValues.SC_SUPPORTED_DISTROS,
        AppInfoFields.THUMBNAIL_URL: XapianValues.THUMBNAIL_URL,
        AppInfoFields.VERSION: XapianValues.VERSION_INFO,
        AppInfoFields.VIDEO_URL: XapianValues.VIDEO_URL,
        AppInfoFields.WEBSITE: XapianValues.WEBSITE,
    }

    # map Application Info Fields to xapian "terms"
    FIELD_TO_TERMS = {
        AppInfoFields.NAME: lambda name: ('AA' + name,),
        AppInfoFields.CHANNEL: lambda channel: ('AH' + channel,),
        AppInfoFields.SECTION: lambda section: ('AS' + section,),
        AppInfoFields.PACKAGE: get_pkgname_terms,
        AppInfoFields.PPA:
            # add archive origin data here so that its available even if
            # the PPA is not (yet) enabled
            lambda ppa: ('XOOlp-ppa-' + ppa.replace('/', '-'),),
    }

    # map apt cache origins to terms
    ORIGINS_TO_TERMS = {
        "XOA": "archive",
        "XOC": "component",
        "XOL": "label",
        "XOO": "origin",
        "XOS": "site",
    }

    # data that needs a transformation during the processing
    FIELD_TRANSFORMERS = {
        AppInfoFields.DATE_PUBLISHED: process_date,
        AppInfoFields.PACKAGE:
            lambda pkgname, pkgname_extension: pkgname + pkgname_extension,
        AppInfoFields.POPCON: process_popcon,
        AppInfoFields.PURCHASED_DATE: process_date,
        AppInfoFields.SUMMARY: lambda s, name: s if s != name else None,
        AppInfoFields.SUPPORTED_DISTROS: json.dumps,
    }

    # a mapping that the subclasses override, it defines the mapping
    # from the Application Info Fields to the "native" keywords used
    # by the various subclasses, e.g. "
    #   X-AppInstall-Channel for desktop files
    # or
    #   "channel" for the json data
    MAPPING = {}

    NOT_DEFINED = object()
    SPLIT_STR_CHAR = ';'

    def get_value(self, key, translated=True):
        """Get the AppInfo entry for the given key."""
        return getattr(self, self._apply_mapping(key), None)

    def _get_value_list(self, key, split_str=None):
        if split_str is None:
            split_str = self.SPLIT_STR_CHAR
        result = []
        list_str = self.get_value(key)
        if list_str is not None:
            try:
                for item in filter(lambda s: s, list_str.split(split_str)):
                    result.append(item)
            except (NoOptionError, KeyError):
                pass
        return result

    def _apply_mapping(self, key):
        return self.MAPPING.get(key, key)

    def get_categories(self):
        return self._get_value_list(AppInfoFields.CATEGORIES)

    def get_mimetypes(self):
        result = self._get_value_list(AppInfoFields.MIMETYPE)
        if not result:
            result = []
        return result

    def _set_doc_from_key(self, doc, key, translated=True, dry_run=False,
                          **kwargs):
        value = self.get_value(key, translated=translated)
        if value is not None:
            modifier = self.FIELD_TRANSFORMERS.get(key, lambda i, **kw: i)
            value = modifier(value, **kwargs)
            if value is not None and not dry_run:
                # add value to the xapian database if defined
                doc_key = self.FIELD_TO_XAPIAN[key]
                doc.add_value(doc_key, value)
                # add terms to the xapian database
                get_terms = self.FIELD_TO_TERMS.get(key, lambda i: [])
                for t in get_terms(value):
                    doc.add_term(t)

        return value

    @property
    def desktopf(self):
        """Return the file that the AppInfo comes from."""

    @property
    def is_ignored(self):
        ignored = self.get_value(AppInfoFields.IGNORE)
        if ignored:
            ignored = ignored.strip().lower()

        return (ignored == "true")

    def make_doc(self, cache):
        """Build a Xapian document from the desktop info."""
        doc = xapian.Document()
        # app name is the data
        name = self._set_doc_from_key(doc, AppInfoFields.NAME)
        assert name is not None
        doc.set_data(name)
        self._set_doc_from_key(doc, AppInfoFields.NAME_UNTRANSLATED,
                               translated=False)

        # check if we should ignore this file
        if self.is_ignored:
            LOG.debug("%r.make_doc: %r is ignored.",
                      self.__class__.__name__, self.desktopf)
            return

        # architecture
        pkgname_extension = ''
        arches = self._set_doc_from_key(doc, AppInfoFields.ARCH)
        if arches:
            native_archs = get_current_arch() in arches.split(',')
            foreign_archs = list(set(arches.split(',')) &
                                 set(get_foreign_architectures()))
            if not (native_archs or foreign_archs):
                return
            if not native_archs and foreign_archs:
                pkgname_extension = ':' + foreign_archs[0]

        # package name
        pkgname = self._set_doc_from_key(doc, AppInfoFields.PACKAGE,
                                         pkgname_extension=pkgname_extension)
        doc.add_value(XapianValues.DESKTOP_FILE, self.desktopf)

        # display name
        display_name = axi_values.get("display_name")
        if display_name is not None:
            doc.add_value(display_name, name)

        # cataloged_times
        catalogedtime = axi_values.get("catalogedtime")
        if catalogedtime is not None and pkgname in cataloged_times:
            doc.add_value(catalogedtime,
                          xapian.sortable_serialise(cataloged_times[pkgname]))

        # section (mail, base, ..)
        if pkgname in cache and cache[pkgname].candidate:
            section = cache[pkgname].section
            doc.add_term("AE" + section)

        fields = (
            AppInfoFields.CHANNEL,  # channel (third party stuff)
            AppInfoFields.DEB_LINE,  # deb-line (third party)
            AppInfoFields.DESCRIPTION,  # description software-center extension
            AppInfoFields.GETTEXT_DOMAIN,  # check gettext domain
            AppInfoFields.ICON,  # icon
            AppInfoFields.LICENSE,  # license (third party)
            AppInfoFields.LICENSE_KEY,  # license key (third party)
            AppInfoFields.LICENSE_KEY_PATH,  # license keypath (third party)
            AppInfoFields.PPA,  # PPA (third party stuff)
            AppInfoFields.PURCHASED_DATE,  # purchased date
            AppInfoFields.SCREENSHOT_URLS,  # screenshot (for third party)
            AppInfoFields.SECTION,  # pocket (main, restricted, ...)
            AppInfoFields.SIGNING_KEY_ID,  # signing key (third party)
            AppInfoFields.SUPPORT_URL,  # support url (mainly pay stuff)
            AppInfoFields.SUPPORTED_DISTROS,  # supported distros
            AppInfoFields.THUMBNAIL_URL,  # thumbnail (for third party)
            AppInfoFields.VERSION,  # version support (for e.g. the scagent)
            AppInfoFields.VIDEO_URL,  # video support (for third party mostly)
            AppInfoFields.WEBSITE,  # homepage url (developer website)
        )
        for field in fields:
            self._set_doc_from_key(doc, field)

        # date published
        date_published_str = self._set_doc_from_key(
            doc, AppInfoFields.DATE_PUBLISHED)
        # we use the date published value for the cataloged time as well
        if date_published_str is not None:
            LOG.debug("pkgname: %s, date_published cataloged time is: %s",
                      pkgname, date_published_str)
            date_published = time.mktime(time.strptime(date_published_str,
                                                       "%Y-%m-%d  %H:%M:%S"))
            # a value for our own DB
            doc.add_value(XapianValues.DB_CATALOGED_TIME,
                          xapian.sortable_serialise(date_published))
            if "catalogedtime" in axi_values:
                # compat with a-x-i
                doc.add_value(axi_values["catalogedtime"],
                              xapian.sortable_serialise(date_published))

        # icon (for third party)
        url = self._set_doc_from_key(doc, AppInfoFields.ICON_URL)
        if url and self.get_value(AppInfoFields.ICON) is None:
            # prefix pkgname to avoid name clashes
            doc.add_value(XapianValues.ICON,
                          "%s-icon-%s" % (pkgname, os.path.basename(url)))

        # price (pay stuff)
        price = self._set_doc_from_key(doc, AppInfoFields.PRICE)
        if price:
            # this is a commercial app, indicate it in the component value
            doc.add_value(XapianValues.ARCHIVE_SECTION, "commercial")
            # this is hard-coded to US dollar for now, but if the server
            # ever changes we can update
            doc.add_value(XapianValues.CURRENCY, "US$")

        # add donwload size as string (its send as int)
        download_size = self.get_value(AppInfoFields.DOWNLOAD_SIZE)
        if download_size is not None:
            doc.add_value(XapianValues.DOWNLOAD_SIZE,
                          xapian.sortable_serialise((download_size)))

        # write out categories
        for cat in self.get_categories():
            doc.add_term("AC" + cat.lower())
        categories_string = ";".join(self.get_categories())
        doc.add_value(XapianValues.CATEGORIES, categories_string)

        # mimetypes
        for mime in self.get_mimetypes():
            doc.add_term("AM" + mime.lower())

        # get type (to distinguish between apps and packages)
        app_type = self.get_value(AppInfoFields.TYPE)
        if app_type:
            doc.add_term("AT" + app_type.lower())

        # (deb)tags (in addition to the pkgname debtags)
        tags_string = self.get_value(AppInfoFields.TAGS)
        if tags_string:
            # convert to list and register
            tags = [tag.strip().lower() for tag in tags_string.split(",")]
            for tag in tags:
                doc.add_term("XT" + tag)
            # ENFORCE region blacklist/whitelist by not registering
            #          the app at all
            region = get_region_cached()
            if region:
                countrycode = region["countrycode"].lower()
                blacklist = [t.replace(REGION_BLACKLIST_TAG, "")
                             for t in tags if
                             t.startswith(REGION_BLACKLIST_TAG)]
                whitelist = [t.replace(REGION_WHITELIST_TAG, "")
                             for t in tags if
                             t.startswith(REGION_WHITELIST_TAG)]

                if countrycode in blacklist:
                    if countrycode in whitelist:
                        LOG.debug("%r.make_doc: %r black AND whitelisted for "
                                  "region %r. Treating as blacklisted.",
                                  self.__class__.__name__, name, countrycode)

                    LOG.debug("%r.make_doc: skipping region restricted app %r "
                             "(blacklisted)", self.__class__.__name__, name)
                    return

                if len(whitelist) > 0 and countrycode not in whitelist:
                    LOG.debug("%r.make_doc: skipping region restricted "
                              "app %r (region not whitelisted)",
                              self.__class__.__name__, name)
                    return

        # popcon
        # FIXME: popularity not only based on popcon but also
        #        on archive section, third party app etc
        popcon = self._set_doc_from_key(doc, AppInfoFields.POPCON)
        if popcon is not None:
            global popcon_max
            popcon_max = max(popcon_max, popcon)

        # comment goes into the summary data if there is one,
        # otherwise we try GenericName and if nothing else,
        # the summary of the candidate package
        summary = self._set_doc_from_key(doc, AppInfoFields.SUMMARY, name=name)
        if summary is None and pkgname in cache and cache[pkgname].candidate:
            summary = cache[pkgname].candidate.summary
            doc.add_value(XapianValues.SUMMARY, summary)

        return doc

    def index_app_info(self, db, cache):
        term_generator = xapian.TermGenerator()
        term_generator.set_database(db)
        try:
            # this tests if we have spelling suggestions (there must be
            # a better way?!?) - this is needed as inmemory does not have
            # spelling corrections, but it allows setting the flag and will
            # raise a exception much later
            db.add_spelling("test")
            db.remove_spelling("test")
            # this enables the flag for it (we only reach this line if
            # the db supports spelling suggestions)
            term_generator.set_flags(xapian.TermGenerator.FLAG_SPELLING)
        except xapian.UnimplementedError:
            pass
        doc = self.make_doc(cache)
        if not doc:
            LOG.debug("%r.index_app_info: returned invalid doc %r, ignoring.",
                      self.__class__.__name__, doc)
            return
        name = doc.get_data()

        if name in seen:
            LOG.debug("%r.index_app_info: duplicated name %r (%r)",
                      self.__class__.__name__, name, self.desktopf)
        LOG.debug("%r.index_app_info: indexing %r",
                  self.__class__.__name__, name)
        seen.add(name)

        term_generator.set_document(doc)
        term_generator.index_text_without_positions(name, WEIGHT_DESKTOP_NAME)

        pkgname = doc.get_value(XapianValues.PKGNAME)
        # add packagename as meta-data too
        term_generator.index_text_without_positions(pkgname,
            WEIGHT_APT_PKGNAME)

        # now add search data from the desktop file
        for weight, key in [('GENERICNAME', AppInfoFields.GENERIC_NAME),
                            ('COMMENT', AppInfoFields.SUMMARY),
                            ('DESCRIPTION', AppInfoFields.DESCRIPTION)]:
            s = self.get_value(key)
            if not s:
                continue
            k = "WEIGHT_DESKTOP_" + weight
            w = globals().get(k)
            if w is None:
                LOG.debug("%r.index_app_info: WEIGHT %r not found",
                          self.__class__.__name__, k)
                w = 1
            term_generator.index_text_without_positions(s, w)

        # add data from the apt cache
        if pkgname in cache and cache[pkgname].candidate:
            term_generator.index_text_without_positions(
                cache[pkgname].candidate.summary, WEIGHT_APT_SUMMARY)
            term_generator.index_text_without_positions(
                cache[pkgname].candidate.description, WEIGHT_APT_DESCRIPTION)
            for origin in cache[pkgname].candidate.origins:
                for (term, attr) in self.ORIGINS_TO_TERMS.items():
                    doc.add_term(term + getattr(origin, attr))

        # add our keywords (with high priority)
        keywords = self.get_value(AppInfoFields.KEYWORDS)
        if keywords:
            for keyword in filter(lambda s: s, keywords.split(";")):
                term_generator.index_text_without_positions(
                    keyword, WEIGHT_DESKTOP_KEYWORD)

        # now add it
        db.add_document(doc)


class SCAApplicationParser(AppInfoParserBase):
    """Map the data we get from the software-center-agent."""

    # map from requested key to sca_application attribute
    MAPPING = {
        AppInfoFields.KEYWORDS: 'keywords',
        AppInfoFields.TAGS: 'tags',
        AppInfoFields.NAME: 'name',
        AppInfoFields.NAME_UNTRANSLATED: 'name',
        AppInfoFields.CHANNEL: 'channel',
        AppInfoFields.PPA: 'archive_id',
        AppInfoFields.SIGNING_KEY_ID: 'signing_key_id',
        AppInfoFields.CATEGORIES: 'categories',
        AppInfoFields.DATE_PUBLISHED: 'date_published',
        AppInfoFields.ICON_URL: 'icon_url',
        AppInfoFields.LICENSE: 'license',
        AppInfoFields.PACKAGE: 'package_name',
        AppInfoFields.PRICE: 'price',
        AppInfoFields.DESCRIPTION: 'description',
        AppInfoFields.DOWNLOAD_SIZE: 'binary_filesize',
        AppInfoFields.SUPPORTED_DISTROS: 'series',
        AppInfoFields.SCREENSHOT_URLS: 'screenshot_url',
        AppInfoFields.SUMMARY: 'comment',
        AppInfoFields.SUPPORT_URL: 'support_url',
        AppInfoFields.THUMBNAIL_URL: 'thumbnail_url',
        AppInfoFields.VERSION: 'version',
        AppInfoFields.VIDEO_URL: 'video_embedded_html_url',
        AppInfoFields.WEBSITE: 'website',
        # tags are special, see _apply_exception
    }

    # map from requested key to a static data element
    STATIC_DATA = {
        AppInfoFields.TYPE: 'Application',
    }

    def __init__(self, sca_application):
        super(SCAApplicationParser, self).__init__()
        # the piston object we got from software-center-agent
        self.sca_application = sca_application
        self.origin = "software-center-agent"
        self._apply_exceptions()

    def _apply_exceptions(self):
        # for items from the agent, we use the full-size screenshot for
        # the thumbnail and scale it for display, this is done because
        # we no longer keep thumbnail versions of screenshots on the server
        if (hasattr(self.sca_application, "screenshot_url") and
                not hasattr(self.sca_application, "thumbnail_url")):
            self.sca_application.thumbnail_url = \
                self.sca_application.screenshot_url
        if hasattr(self.sca_application, "description"):
            comment, desc = self.sca_application.description.split("\n", 1)
            self.sca_application.comment = comment.strip()
            self.sca_application.description = desc.strip()

        # debtags is send as a list, but we need it as a comma separated string
        debtags = getattr(self.sca_application, "debtags", [])
        self.sca_application.tags = ",".join(debtags)

        # we only support a single video currently :/
        urls = getattr(self.sca_application, "video_embedded_html_urls", None)
        if urls:
            self.sca_application.video_embedded_html_url = urls[0]
        else:
            self.sca_application.video_embedded_html_url = None

        # XXX 2012-01-16 bug=917109
        # We can remove these work-arounds once the above bug is fixed on
        # the server. Until then, we fake a channel here and empty category
        # to make the parser happy. Note: available_apps api call includes
        # these already, it's just the apps with subscriptions_for_me which
        # don't currently.
        self.sca_application.channel = \
            AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME
        if not hasattr(self.sca_application, 'categories'):
            self.sca_application.categories = ""

        # detect if its for the partner channel and set the channel
        # attribute appropriately so that the channel-adding magic works
        if hasattr(self.sca_application, "archive_root"):
            u = urlparse(self.sca_application.archive_root)
            if u.scheme == "http" and u.netloc == "archive.canonical.com":
                distroseries = get_distro().get_codename()
                self.sca_application.channel = "%s-partner" % distroseries
            if u.scheme == "http" and u.netloc == "extras.ubuntu.com":
                self.sca_application.channel = "ubuntu-extras"

        # support multiple screenshots
        if hasattr(self.sca_application, "screenshot_urls"):
            # ensure to html-quote "," as this is also our separator
            s = ",".join([url.replace(",", "%2C")
                          for url in self.sca_application.screenshot_urls])
            self.sca_application.screenshot_url = s

        keywords = getattr(self.sca_application, 'keywords', self.NOT_DEFINED)
        if keywords is self.NOT_DEFINED:
            self.sca_application.keywords = ''

    def get_value(self, key, translated=True):
        if key in self.STATIC_DATA:
            return self.STATIC_DATA[key]
        return getattr(self.sca_application, self._apply_mapping(key), None)

    def get_categories(self):
        try:
            dept = ['DEPARTMENT:' + self.sca_application.department[-1]]
            return (dept + self._get_value_list(AppInfoFields.CATEGORIES))
        except:
            return self._get_value_list(AppInfoFields.CATEGORIES)

    @property
    def desktopf(self):
        return self.origin


class SCAPurchasedApplicationParser(SCAApplicationParser):
    """A purchased application has some additional subscription attributes."""

    SUBSCRIPTION_MAPPING = {
        # this key can be used to get the original deb_line that the
        # server returns, it will be at the distroseries that was current
        # at purchase time
        AppInfoFields.DEB_LINE_ORIG: 'deb_line',
        # this is what s-c will always use, the deb_line updated to the
        # current distroseries, note that you should ensure that the app
        # is not in state: PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES
        AppInfoFields.DEB_LINE: 'deb_line',
        AppInfoFields.PURCHASED_DATE: 'purchase_date',
        AppInfoFields.LICENSE_KEY: 'license_key',
        AppInfoFields.LICENSE_KEY_PATH: 'license_key_path',
    }

    def __init__(self, sca_subscription):
        # The sca_subscription is a PistonResponseObject, whereas any child
        # objects are normal Python dicts.
        self.sca_subscription = sca_subscription
        self.MAPPING.update(self.SUBSCRIPTION_MAPPING)
        super(SCAPurchasedApplicationParser, self).__init__(
            PistonResponseObject.from_dict(sca_subscription.application))

    @classmethod
    def update_debline(cls, debline):
        # Be careful to handle deblines with pockets.
        source_entry = SourceEntry(debline)
        distro_pocket = source_entry.dist.split('-')
        distro_pocket[0] = get_distro().get_codename()
        source_entry.dist = "-".join(distro_pocket)

        return unicode(source_entry)

    def get_value(self, key, translated=True):
        result = getattr(self.sca_subscription, self._apply_mapping(key),
                         self.NOT_DEFINED)
        if result is not self.NOT_DEFINED and key == AppInfoFields.DEB_LINE:
            result = self.update_debline(result)
        elif result is self.NOT_DEFINED:
            result = super(
                SCAPurchasedApplicationParser, self).get_value(key)

        return result

    def _apply_exceptions(self):
        super(SCAPurchasedApplicationParser, self)._apply_exceptions()
        # WARNING: item.name needs to be different than
        #          the item.name in the DB otherwise the DB
        #          gets confused about (appname, pkgname) duplication
        self.sca_application.name = utf8(_("%s (already purchased)")) % utf8(
            self.sca_application.name)
        for attr_name in ('license_key', 'license_key_path'):
            attr = getattr(self.sca_subscription, attr_name, self.NOT_DEFINED)
            if attr is self.NOT_DEFINED:
                setattr(self.sca_subscription, attr_name, None)


class JsonTagSectionParser(AppInfoParserBase):

    MAPPING = {
        AppInfoFields.CATEGORIES: 'categories',
        AppInfoFields.NAME: 'application_name',
        AppInfoFields.PACKAGE: 'package_name',
        AppInfoFields.PRICE: 'price',
        AppInfoFields.SUMMARY: 'description',
    }

    STATIC_DATA = {
        AppInfoFields.TYPE: 'Application',
    }

    def __init__(self, tag_section, url):
        super(JsonTagSectionParser, self).__init__()
        self.tag_section = tag_section
        self.url = url

    def get_value(self, key, translated=True):
        if key in self.STATIC_DATA:
            return self.STATIC_DATA[key]
        return self.tag_section.get(self._apply_mapping(key))

    @property
    def desktopf(self):
        return self.url


class AppStreamXMLParser(AppInfoParserBase):

    MAPPING = {
        AppInfoFields.CATEGORIES: 'appcategories',
        AppInfoFields.ICON: 'icon',
        AppInfoFields.KEYWORDS: 'keywords',
        AppInfoFields.MIMETYPE: 'mimetypes',
        AppInfoFields.NAME: 'name',
        AppInfoFields.PACKAGE: 'pkgname',
        AppInfoFields.SUMMARY: 'summary',
    }

    LISTS = {
        "appcategories": "appcategory",
        "keywords": "keyword",
        "mimetypes": "mimetype",
    }

    # map from requested key to a static data element
    STATIC_DATA = {
        AppInfoFields.TYPE: 'Application',
    }

    SPLIT_STR_CHAR = ','

    def __init__(self, appinfo_xml, xmlfile):
        super(AppStreamXMLParser, self).__init__()
        self.appinfo_xml = appinfo_xml
        self.xmlfile = xmlfile

    def get_value(self, key, translated=True):
        if key in self.STATIC_DATA:
            return self.STATIC_DATA[key]
        key = self._apply_mapping(key)
        if key in self.LISTS:
            return self._parse_with_lists(key)
        else:
            return self._parse_value(key, translated)

    def _parse_value(self, key, translated):
        locale = get_default_locale()
        for child in self.appinfo_xml.iter(key):
            if translated:
                if child.get("lang") == locale:
                    return child.text
                if child.get("lang") == locale.split('_')[0]:
                    return child.text
                continue
            elif not child.get("lang"):
                return child.text
        if translated:
            return self._parse_value(key, False)

    def _parse_with_lists(self, key):
        l = []
        for listroot in self.appinfo_xml.iter(key):
            for child in listroot.iter(self.LISTS[key]):
                l.append(child.text)
        return ",".join(l)

    @property
    def desktopf(self):
        subelm = self.appinfo_xml.find("id")
        return subelm.text


class DesktopTagSectionParser(AppInfoParserBase):

    MAPPING = {
        AppInfoFields.ARCH: 'X-AppInstall-Architectures',
        AppInfoFields.CHANNEL: 'X-AppInstall-Channel',
        AppInfoFields.DATE_PUBLISHED: 'X-AppInstall-Date-Published',
        AppInfoFields.DEB_LINE: 'X-AppInstall-Deb-Line',
        AppInfoFields.DESCRIPTION: 'X-AppInstall-Description',
        AppInfoFields.DOWNLOAD_SIZE: 'X-AppInstall-DownloadSize',
        AppInfoFields.GENERIC_NAME: 'GenericName',
        AppInfoFields.GETTEXT_DOMAIN: 'X-Ubuntu-Gettext-Domain',
        AppInfoFields.ICON: 'Icon',
        AppInfoFields.ICON_URL: 'X-AppInstall-Icon-Url',
        AppInfoFields.IGNORE: 'X-AppInstall-Ignore',
        AppInfoFields.KEYWORDS: 'X-AppInstall-Keywords',
        AppInfoFields.LICENSE: 'X-AppInstall-License',
        AppInfoFields.LICENSE_KEY: 'X-AppInstall-License-Key',
        AppInfoFields.LICENSE_KEY_PATH: 'X-AppInstall-License-Key-Path',
        AppInfoFields.NAME:
            ('X-Ubuntu-Software-Center-Name', 'X-GNOME-FullName', 'Name'),
        AppInfoFields.NAME_UNTRANSLATED:
            ('X-Ubuntu-Software-Center-Name', 'X-GNOME-FullName', 'Name'),
        AppInfoFields.PACKAGE: 'X-AppInstall-Package',
        AppInfoFields.POPCON: 'X-AppInstall-Popcon',
        AppInfoFields.PPA: 'X-AppInstall-PPA',
        AppInfoFields.PRICE: 'X-AppInstall-Price',
        AppInfoFields.PURCHASED_DATE: 'X-AppInstall-Purchased-Date',
        AppInfoFields.SCREENSHOT_URLS: 'X-AppInstall-Screenshot-Url',
        AppInfoFields.SECTION: 'X-AppInstall-Section',
        AppInfoFields.SIGNING_KEY_ID: 'X-AppInstall-Signing-Key-Id',
        AppInfoFields.SUMMARY: ('Comment', 'GenericName'),
        AppInfoFields.SUPPORTED_DISTROS: 'Supported-Distros',
        AppInfoFields.SUPPORT_URL: 'X-AppInstall-Support-Url',
        AppInfoFields.TAGS: 'X-AppInstall-Tags',
        AppInfoFields.THUMBNAIL_URL: 'X-AppInstall-Thumbnail-Url',
        AppInfoFields.TYPE: 'Type',
        AppInfoFields.VERSION: 'X-AppInstall-Version',
        AppInfoFields.VIDEO_URL: 'X-AppInstall-Video-Url',
        AppInfoFields.WEBSITE: 'Homepage',
    }

    LOCALE_EXPR = '%s-%s'

    def __init__(self, tag_section, tagfile):
        super(DesktopTagSectionParser, self).__init__()
        self.tag_section = tag_section
        self.tagfile = tagfile

    def get_value(self, key, translated=True):
        keys = self.MAPPING.get(key, key)
        if isinstance(keys, basestring):
            keys = (keys,)

        for key in keys:
            result = self._get_desktop(key, translated)
            if result:
                return result

    def _get_desktop(self, key, translated=True):
        untranslated_value = self._get_option_desktop(key)
        # shortcut
        if not translated:
            return untranslated_value

        # first try dgettext
        domain = self._get_option_desktop('X-Ubuntu-Gettext-Domain')
        if domain and untranslated_value:
            translated_value = gettext.dgettext(domain, untranslated_value)
            if untranslated_value != translated_value:
                return translated_value

        # then try app-install-data
        if untranslated_value:
            translated_value = gettext.dgettext('app-install-data',
                                                untranslated_value)
            if untranslated_value != translated_value:
                return translated_value

        # then try the i18n version of the key (in [de_DE] or
        # [de]) but ignore errors and return the untranslated one then
        try:
            locale = get_default_locale()
            if locale:
                new_key = self.LOCALE_EXPR % (key, locale)
                result = self._get_option_desktop(new_key)
                if not result and "_" in locale:
                    locale_short = locale.split("_")[0]
                    new_key = self.LOCALE_EXPR % (key, locale_short)
                    result = self._get_option_desktop(new_key)
                if result:
                    return result
        except ValueError:
            pass

        # and then the untranslated field
        return untranslated_value

    def _get_option_desktop(self, key):
        if key in self.tag_section:
            return self.tag_section.get(key)

    @property
    def desktopf(self):
        return self.tagfile


class DesktopConfigParser(RawConfigParser, DesktopTagSectionParser):
    """Thin wrapper that is tailored for xdg Desktop files."""

    DE = "Desktop Entry"
    LOCALE_EXPR = '%s[%s]'

    def _get_desktop(self, key, translated=True):
        """Get the generic option 'key' under 'Desktop Entry'."""
        # never translate the pkgname
        if key == self.MAPPING[AppInfoFields.PACKAGE]:
            return self._get_option_desktop(key)

        return super(DesktopConfigParser, self)._get_desktop(key, translated)

    def _get_option_desktop(self, key):
        if self.has_option(self.DE, key):
            return self.get(self.DE, key)

    def read(self, filename):
        self._filename = filename
        RawConfigParser.read(self, filename)

    @property
    def desktopf(self):
        return self._filename


class ScopeConfigParser(DesktopConfigParser):
    """Thin wrapper to handle Scope files."""

    SCOPE = "Scope"

    def _get_option_desktop(self, key):
        # Mark scopes as Type=Scope.
        if key.lower() == 'type':
            return 'Scope'
        value = super(ScopeConfigParser, self)._get_option_desktop(key)
        if value is not None:
            return value
        # Fall back to values from the SCOPE section.
        if self.has_option(self.SCOPE, key):
            return self.get(self.SCOPE, key)


def ascii_upper(key):
    """Translate an ASCII string to uppercase
    in a locale-independent manner."""
    ascii_trans_table = string.maketrans(string.ascii_lowercase,
                                         string.ascii_uppercase)
    return key.translate(ascii_trans_table)


def update(db, cache, datadir=None):
    if not datadir:
        datadir = softwarecenter.paths.APP_INSTALL_DESKTOP_PATH
    update_from_app_install_data(db, cache, datadir)
    update_from_var_lib_apt_lists(db, cache)
    # add db global meta-data
    LOG.debug("adding popcon_max_desktop %r", popcon_max)
    db.set_metadata("popcon_max_desktop",
                    xapian.sortable_serialise(float(popcon_max)))


def update_from_json_string(db, cache, json_string, origin):
    """Index from json string, must include origin url (free form string)."""
    for sec in json.loads(json_string):
        parser = JsonTagSectionParser(sec, origin)
        parser.index_app_info(db, cache)
    return True


def update_from_var_lib_apt_lists(db, cache, listsdir=None):
    """ index the files in /var/lib/apt/lists/*AppInfo """
    try:
        import apt_pkg
    except ImportError:
        return False
    if not listsdir:
        listsdir = apt_pkg.config.find_dir("Dir::State::lists")
    context = GLib.main_context_default()
    for appinfo in glob("%s/*AppInfo" % listsdir):
        LOG.debug("processing %r", appinfo)
        # process events
        while context.pending():
            context.iteration()
        tagf = apt_pkg.TagFile(open(appinfo))
        for section in tagf:
            parser = DesktopTagSectionParser(section, appinfo)
            parser.index_app_info(db, cache)
    return True


def update_from_single_appstream_file(db, cache, filename):
    from lxml import etree

    tree = etree.parse(open(filename))
    root = tree.getroot()
    if not root.tag == "applications":
        LOG.error("failed to read %r expected Applications root tag",
                  filename)
        return
    for appinfo in root.iter("application"):
        parser = AppStreamXMLParser(appinfo, filename)
        parser.index_app_info(db, cache)


def update_from_appstream_xml(db, cache, xmldir=None):
    if not xmldir:
        xmldir = softwarecenter.paths.APPSTREAM_XML_PATH
    context = GLib.main_context_default()

    if os.path.isfile(xmldir):
        update_from_single_appstream_file(db, cache, xmldir)
        return True

    for appstream_xml in glob(os.path.join(xmldir, "*.xml")):
        LOG.debug("processing %r", appstream_xml)
        # process events
        while context.pending():
            context.iteration()
        update_from_single_appstream_file(db, cache, appstream_xml)
    return True


def update_from_app_install_data(db, cache, datadir=None):
    """ index the desktop files in $datadir/desktop/*.desktop """
    if not datadir:
        datadir = softwarecenter.paths.APP_INSTALL_DESKTOP_PATH
    context = GLib.main_context_default()
    for desktopf in glob(datadir + "/*.desktop") + glob(datadir + "/*.scope"):
        LOG.debug("processing %r", desktopf)
        # process events
        while context.pending():
            context.iteration()
        try:
            if desktopf.endswith('.scope'):
                parser = ScopeConfigParser()
            else:
                parser = DesktopConfigParser()
            parser.read(desktopf)
            parser.index_app_info(db, cache)
        except Exception as e:
            # Print a warning, no error (Debian Bug #568941)
            LOG.debug("error processing: %r %r", desktopf, e)
            warning_text = _(
                "The file: '%s' could not be read correctly. The application "
                "associated with this file will not be included in the "
                "software catalog. Please consider raising a bug report "
                "for this issue with the maintainer of that application")
            LOG.warning(warning_text, desktopf)
    return True


def update_from_software_center_agent(db, cache, ignore_cache=False,
                                      include_sca_qa=False):
    """Update the index based on the software-center-agent data."""

    def _available_cb(sca, available):
        LOG.debug("update_from_software_center_agent: available: %r",
                  available)
        sca.available = available
        sca.good_data = True
        loop.quit()

    def _available_for_me_cb(sca, available_for_me):
        LOG.debug("update_from_software_center_agent: available_for_me: %r",
                  available_for_me)
        sca.available_for_me = available_for_me
        loop.quit()

    def _error_cb(sca, error):
        LOG.warn("update_from_software_center_agent: error: %r", error)
        sca.good_data = False
        loop.quit()

    context = GLib.main_context_default()
    loop = GLib.MainLoop(context)

    sca = SoftwareCenterAgent(ignore_cache)
    sca.connect("available", _available_cb)
    sca.connect("available-for-me", _available_for_me_cb)
    sca.connect("error", _error_cb)
    sca.available = []
    sca.available_for_me = []

    # query what is available for me first
    available_for_me_pkgnames = set()
    # this will ensure we do not trigger a login dialog
    helper = UbuntuSSO()
    token = helper.find_oauth_token_sync()
    if token:
        sca.query_available_for_me(no_relogin=True)
        loop.run()
        for item in sca.available_for_me:
            try:
                parser = SCAPurchasedApplicationParser(item)
                parser.index_app_info(db, cache)
                available_for_me_pkgnames.add(item.application["package_name"])
            except:
                LOG.exception("error processing: %r", item)

    # ... now query all that is available
    if include_sca_qa:
        sca.query_available_qa()
    else:
        sca.query_available()

    # create event loop and run it until data is available
    # (the _available_cb and _error_cb will quit it)
    loop.run()

    # process data
    for entry in sca.available:

        # do not add stuff here that's already purchased to avoid duplication
        if entry.package_name in available_for_me_pkgnames:
            continue

        # process events
        while context.pending():
            context.iteration()
        try:
            # now the normal parser
            parser = SCAApplicationParser(entry)
            parser.index_app_info(db, cache)
        except:
            LOG.exception("update_from_software_center_agent: "
                          "error processing %r:", entry.name)

    # return true if we have updated entries (this can also be an empty list)
    # but only if we did not got a error from the agent
    return sca.good_data


def rebuild_database(pathname, debian_sources=True, appstream_sources=False,
                     appinfo_dir=None):
    #cache = apt.Cache(memonly=True)
    cache = get_pkg_info()
    cache.open()
    old_path = pathname + "_old"
    rebuild_path = pathname + "_rb"

    if not os.path.exists(rebuild_path):
        try:
            os.makedirs(rebuild_path)
        except:
            LOG.warn("Problem creating rebuild path %r.", rebuild_path)
            LOG.warn("Please check you have the relevant permissions.")
            return False

    # check permission
    if not os.access(pathname, os.W_OK):
        LOG.warn("Cannot write to %r.", pathname)
        LOG.warn("Please check you have the relevant permissions.")
        return False

    #check if old unrequired version of db still exists on filesystem
    if os.path.exists(old_path):
        LOG.warn("Existing xapian old db was not previously cleaned: %r.",
                 old_path)
        if os.access(old_path, os.W_OK):
            #remove old unrequired db before beginning
            shutil.rmtree(old_path)
        else:
            LOG.warn("Cannot write to %r.", old_path)
            LOG.warn("Please check you have the relevant permissions.")
            return False

    # write it
    db = xapian.WritableDatabase(rebuild_path, xapian.DB_CREATE_OR_OVERWRITE)

    if debian_sources:
        update(db, cache, appinfo_dir)
    if appstream_sources:
        if os.path.exists('./data/app-stream/appdata.xml'):
            update_from_appstream_xml(db, cache,
                './data/app-stream/appdata.xml')
        else:
            update_from_appstream_xml(db, cache)

    # write the database version into the file
    db.set_metadata("db-schema-version", DB_SCHEMA_VERSION)
    # update the mo file stamp for the langpack checks
    mofile = gettext.find("app-install-data")
    if mofile:
        mo_time = os.path.getctime(mofile)
        db.set_metadata("app-install-mo-time", str(mo_time))
    db.flush()

    # use shutil.move() instead of os.rename() as this will automatically
    # figure out if it can use os.rename or needs to do the move "manually"
    try:
        shutil.move(pathname, old_path)
        shutil.move(rebuild_path, pathname)
        shutil.rmtree(old_path)
        return True
    except:
        LOG.warn("Cannot copy refreshed database to correct location: %r.",
                 pathname)
        return False
