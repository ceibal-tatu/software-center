from __future__ import print_function

import logging
import os
import sys
import urllib

import xapian

from gi.repository import Gdk, Gtk, GLib
from mock import Mock, patch

import softwarecenter.distro
import softwarecenter.log
import softwarecenter.paths

from softwarecenter.backend import channel
from softwarecenter.db import (
    appfilter,
    application,
    database,
    enquire,
    pkginfo,
)
from softwarecenter.enums import (
    BUY_SOMETHING_HOST,
    NonAppVisibility,
)
from softwarecenter.ui.gtk3 import em
from softwarecenter.ui.gtk3.dialogs import dependency_dialogs
from softwarecenter.ui.gtk3.models import appstore2
from softwarecenter.ui.gtk3.panes import (
    availablepane,
    globalpane,
    historypane,
    installedpane,
    pendingpane,
    viewswitcher,
)
from softwarecenter.ui.gtk3.session import (
    appmanager,
    displaystate,
    )
from softwarecenter.ui.gtk3.utils import (
    get_sc_icon_theme,
)
from softwarecenter.ui.gtk3.views import (
    appview,
    appdetailsview,
    catview,
    lobbyview,
    pkgnamesview,
    purchaseview,
)
from softwarecenter.ui.gtk3.widgets import (
    backforward,
    buttons,
    containers,
    description,
    exhibits,
    labels,
    oneconfviews,
    recommendations,
    reviews,
    searchentry,
    spinner,
    stars,
    symbolic_icons,
    thumbnail,
    videoplayer,
)
from softwarecenter.utils import ExecutionTime
from tests.utils import (
    do_events,
    get_test_categories,
    get_test_db,
    get_test_gtk3_icon_cache,
    get_test_gtk3_viewmanager,
    get_test_install_backend,
    get_test_pkg_info,
    patch_datadir,
)


if os.environ.get('SOFTWARE_CENTER_PERFORMANCE_DEBUG', False):
    softwarecenter.log.root.setLevel(level=logging.DEBUG)
    softwarecenter.log.add_filters_from_string("performance")
    fmt = logging.Formatter("%(name)s - %(message)s", None)
    softwarecenter.log.handler.setFormatter(fmt)


if os.environ.get('SOFTWARE_CENTER_DEBUG', False):
    softwarecenter.log.root.setLevel(level=logging.DEBUG)
    fmt = logging.Formatter("%(name)s - %(message)s", None)
    softwarecenter.log.handler.setFormatter(fmt)


# compat window with functions for {get,set}_data() as this
# got removed from python gobject API in 12.10
class TestWindow(Gtk.Window):
    def __init__(self):
        super(TestWindow, self).__init__()
        self.set_position(Gtk.WindowPosition.CENTER)
        self._data = {}
    def get_data(self, key):
        return self._data.get(key)
    def set_data(self, key, value):
        self._data[key] = value

def get_test_window(child, width=600, height=800, border_width=0, title=None):
    win = TestWindow()
    win.set_size_request(width, height)
    win.set_border_width(border_width)
    win.add(child)
    if title is None:
        title = child.__class__.__name__
    win.set_title(title)
    win.show_all()
    return win


def get_test_window_dependency_dialog():
    icons = get_test_gtk3_icon_cache()
    db = get_test_db()

    depends = ["apt", "synaptic"]
    app = application.Application("", "software-center")
    primary = "primary text"
    button_text = "button_text"
    dia = dependency_dialogs._get_confirm_internal_dialog(
        parent=None, app=app,
        db=db, icons=icons, primary=primary, button_text=button_text,
        depends=depends, cache=db._aptcache)
    return dia


def get_test_window_confirm_remove():
    # test real remove dialog
    icons = get_test_gtk3_icon_cache()
    db = get_test_db()
    app = application.Application("", "p7zip-full")
    return dependency_dialogs.confirm_remove(None,
        app, db, icons)


def get_query_from_search_entry(search_term):
    if not search_term:
        return xapian.Query("")
    parser = xapian.QueryParser()
    user_query = parser.parse_query(search_term)
    return user_query


def on_entry_changed(widget, data):

    def _work():
        new_text = widget.get_text()
        (view, enquirer) = data

        with ExecutionTime("total time"):
            with ExecutionTime("enquire.set_query()"):
                enquirer.set_query(get_query_from_search_entry(new_text),
                    limit=100 * 1000,
                    nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE)

            store = view.tree_view.get_model()
            if store is None:
                return

            with ExecutionTime("store.clear()"):
                store.clear()

            with ExecutionTime("store.set_from_matches()"):
                store.set_from_matches(enquirer.matches)

            with ExecutionTime("model settle (size=%s)" % len(store)):
                do_events()

    if widget.stamp:
        GLib.source_remove(widget.stamp)
    widget.stamp = GLib.timeout_add(250, _work)


def get_test_window_appview():
    db = get_test_db()
    cache = get_test_pkg_info()
    icons = get_test_gtk3_icon_cache()

    # create a filter
    app_filter = appfilter.AppFilter(db, cache)
    app_filter.set_supported_only(False)
    app_filter.set_installed_only(True)

    # appview
    enquirer = enquire.AppEnquire(cache, db)
    store = appstore2.AppListStore(db, cache, icons)

    view = appview.AppView(db, cache, icons, show_ratings=True)
    view.set_model(store)

    entry = Gtk.Entry()
    entry.stamp = 0
    entry.connect("changed", on_entry_changed, (view, enquirer))
    entry.set_text("gtk3")

    box = Gtk.VBox()
    box.pack_start(entry, False, True, 0)
    box.pack_start(view, True, True, 0)

    win = get_test_window(child=box)
    win.set_data("appview", view)
    win.set_data("entry", entry)

    return win


def get_test_window_apptreeview():
    cache = get_test_pkg_info()
    db = get_test_db()
    icons = get_test_gtk3_icon_cache()

    # create a filter
    app_filter = appfilter.AppFilter(db, cache)
    app_filter.set_supported_only(False)
    app_filter.set_installed_only(True)

    # get the TREEstore
    store = appstore2.AppTreeStore(db, cache, icons)

    # populate from data
    cats = get_test_categories(db)
    for cat in cats[:3]:
        with ExecutionTime("query cat '%s'" % cat.name):
            docs = db.get_docs_from_query(cat.query)
            store.set_category_documents(cat, docs)

    # ok, this is confusing - the AppView contains the AppTreeView that
    #                         is a tree or list depending on the model
    app_view = appview.AppView(db, cache, icons, show_ratings=True)
    app_view.set_model(store)

    box = Gtk.VBox()
    box.pack_start(app_view, True, True, 0)

    win = get_test_window(child=box)
    return win


def get_test_window_availablepane():
    # needed because available pane will try to get it
    vm = get_test_gtk3_viewmanager()
    assert vm is not None
    db = get_test_db()
    cache = get_test_pkg_info()
    icons = get_test_gtk3_icon_cache()
    backend = get_test_install_backend()
    distro = softwarecenter.distro.get_distro()

    manager = appmanager.get_appmanager()
    if manager is None:
        # create global AppManager instance
        manager = appmanager.ApplicationManager(db, backend, icons)

    navhistory_back_action = Gtk.Action("navhistory_back_action", "Back",
        "Back", None)
    navhistory_forward_action = Gtk.Action("navhistory_forward_action",
        "Forward", "Forward", None)

    zl = "softwarecenter.backend.zeitgeist_logger.ZeitgeistLogger";
    patch(zl + ".log_install_event").start().return_value = False
    patch(zl + ".log_uninstall_event").start().return_value = False
    patch("softwarecenter.utils.is_unity_running").start().return_value = False

    w = availablepane.AvailablePane(cache, db, distro, icons,
        navhistory_back_action, navhistory_forward_action)
    w.init_view()
    w.show()

    win = get_test_window(child=w, width=800, height=600)
    # this is used later in tests
    win.set_data("pane", w)
    win.set_data("vm", vm)
    return win


def get_test_window_globalpane():
    vm = get_test_gtk3_viewmanager()
    db = get_test_db()
    cache = get_test_pkg_info()
    icons = get_test_gtk3_icon_cache()

    p = globalpane.GlobalPane(vm, db, cache, icons)

    win = get_test_window(child=p)
    win.set_data("pane", p)
    return win


def get_test_window_pendingpane():
    icons = get_test_gtk3_icon_cache()

    view = pendingpane.PendingPane(icons)

    # gui
    scroll = Gtk.ScrolledWindow()
    scroll.add_with_viewport(view)

    win = get_test_window(child=scroll)
    view.grab_focus()
    return win


@patch_datadir('./data')
def get_test_window_viewswitcher():
    cache = get_test_pkg_info()
    db = get_test_db()
    icons = get_test_gtk3_icon_cache()
    manager = get_test_gtk3_viewmanager()

    view = viewswitcher.ViewSwitcher(manager, db, cache, icons)

    scroll = Gtk.ScrolledWindow()
    box = Gtk.VBox()
    box.pack_start(scroll, True, True, 0)

    win = get_test_window(child=box)
    scroll.add_with_viewport(view)
    return win


def get_test_window_installedpane():
    # needed because available pane will try to get it
    vm = get_test_gtk3_viewmanager()
    vm  # make pyflakes happy
    db = get_test_db()
    cache = get_test_pkg_info()
    icons = get_test_gtk3_icon_cache()

    w = installedpane.InstalledPane(cache, db, 'Ubuntu', icons)
    w.show()

    # init the view
    w.init_view()

    w.state.channel = channel.AllInstalledChannel()
    view_state = displaystate.DisplayState()
    view_state.channel = channel.AllInstalledChannel()
    w.display_overview_page(view_state)

    win = get_test_window(child=w)
    win.set_data("pane", w)
    return win


def get_test_window_historypane():
    # needed because available pane will try to get it
    vm = get_test_gtk3_viewmanager()
    vm  # make pyflakes happy
    db = get_test_db()
    cache = get_test_pkg_info()
    icons = get_test_gtk3_icon_cache()

    widget = historypane.HistoryPane(cache, db, None, icons)
    widget.show()

    win = get_test_window(child=widget)
    widget.init_view()
    return win


def get_test_window_recommendations(panel_type="lobby"):
    cache = get_test_pkg_info()
    db = get_test_db()
    icons = get_test_gtk3_icon_cache()
    from softwarecenter.ui.gtk3.models.appstore2 import AppPropertiesHelper
    properties_helper = AppPropertiesHelper(db, cache, icons)
            
    if panel_type is "lobby":
        view = recommendations.RecommendationsPanelLobby(
                db, properties_helper)
    elif panel_type is "category":
        cats = get_test_categories(db)
        view = recommendations.RecommendationsPanelCategory(
                db, properties_helper, cats[0])
    else:  # panel_type is "details":
        view = recommendations.RecommendationsPanelDetails(
                db, properties_helper)

    win = get_test_window(child=view, width=600, height=300)
    win.set_data("rec_panel", view)
    return win


def get_test_window_catview(db=None, selected_category="Internet"):
    ''' 
        Note that selected_category must specify a category that includes
        subcategories, else a ValueError will be raised.
    '''
    def on_category_selected(view, cat):
        print("on_category_selected view: ", view)
        print("on_category_selected cat: ", cat)

    if db is None:
        cache = pkginfo.get_pkg_info()
        cache.open()

        xapian_base_path = "/var/cache/software-center"
        pathname = os.path.join(xapian_base_path, "xapian")
        db = database.StoreDatabase(pathname, cache)
        db.open()
    else:
        cache = db._aptcache

    icons = get_sc_icon_theme()
    distro = softwarecenter.distro.get_distro()
    apps_filter = appfilter.AppFilter(db, cache)

    # gui
    notebook = Gtk.Notebook()

    lobby_view = lobbyview.LobbyView(cache, db, icons, distro, apps_filter)

    scroll = Gtk.ScrolledWindow()
    scroll.add(lobby_view)
    notebook.append_page(scroll, Gtk.Label(label="Lobby"))

    subcat_cat = None
    for cat in lobby_view.categories:
        if cat.name == selected_category:
            if not cat.subcategories:
                raise ValueError('The value specified for selected_category '
                                 '*must* specify a '
                                 'category that contains subcategories!!')
            subcat_cat = cat
            break

    subcat_view = catview.SubCategoryView(cache, db, icons, apps_filter)
    subcat_view.connect("category-selected", on_category_selected)
    subcat_view.set_subcategory(subcat_cat)

    scroll = Gtk.ScrolledWindow()
    scroll.add(subcat_view)
    notebook.append_page(scroll, Gtk.Label(label="Subcats"))

    win = get_test_window(child=notebook, width=800, height=800)
    win.set_data("subcat", subcat_view)
    win.set_data("lobby", lobby_view)
    return win


def get_test_catview():

    def on_category_selected(view, cat):
        print("on_category_selected %s %s" % (view, cat))

    cache = pkginfo.get_pkg_info()
    cache.open()

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = database.StoreDatabase(pathname, cache)
    db.open()

    icons = get_sc_icon_theme()
    distro = softwarecenter.distro.get_distro()
    apps_filter = appfilter.AppFilter(db, cache)

    cat_view = lobbyview.LobbyView(cache, db, icons, distro, apps_filter)

    return cat_view


def get_test_window_appdetails(pkgname=None):
    cache = pkginfo.get_pkg_info()
    cache.open()

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = database.StoreDatabase(pathname, cache)
    db.open()

    icons = get_sc_icon_theme()
    distro = softwarecenter.distro.get_distro()

    # gui
    scroll = Gtk.ScrolledWindow()
    view = appdetailsview.AppDetailsView(db, distro, icons, cache)

    if pkgname is None:
        pkgname = "totem"

    view.show_app(application.Application("", pkgname))
    #view.show_app(application.Application("Pay App Example", "pay-app"))
    #view.show_app(application.Application("3D Chess", "3dchess"))
    #view.show_app(application.Application("Movie Player", "totem"))
    #view.show_app(application.Application("ACE", "unace"))
    #~ view.show_app(application.Application("", "apt"))

    #view.show_app("AMOR")
    #view.show_app("Configuration Editor")
    #view.show_app("Artha")
    #view.show_app("cournol")
    #view.show_app("Qlix")

    scroll.add(view)
    scroll.show()

    win = get_test_window(child=scroll, width=800, height=800)
    win.set_data("view", view)
    return win


def get_test_window_pkgnamesview():
    cache = pkginfo.get_pkg_info()
    cache.open()

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = database.StoreDatabase(pathname, cache)
    db.open()

    icons = get_sc_icon_theme()
    pkgs = ["apt", "software-center"]
    view = pkgnamesview.PackageNamesView("header", cache, pkgs, icons, 32, db)
    view.show()

    win = get_test_window(child=view)
    return win


@patch_datadir('./tests/data')
def get_test_window_purchaseview(url=None):
    if url is None:
        #url = "http://www.animiertegifs.de/java-scripts/alertbox.php"
        url = "http://www.ubuntu.cohtml=DUMMY_m"
        #d = PurchaseDialog(app=None, url="http://spiegel.de")
        url_args = urllib.urlencode({'archive_id': "mvo/private-test",
                                     'arch': "i386"})
        url = (BUY_SOMETHING_HOST +
               "/subscriptions/en/ubuntu/precise/+new/?%s" % url_args)

    # useful for debugging
    #d.connect("key-press-event", _on_key_press)
    #GLib.timeout_add_seconds(1, _generate_events, d)

    widget = purchaseview.PurchaseView()
    widget.config = Mock()

    win = get_test_window(child=widget)
    win.set_data("view", widget)

    widget.initiate_purchase(app=None, iconname=None, url=url)
    #widget.initiate_purchase(app=None, iconname=None, html=DUMMY_HTML)

    return win


def get_test_backforward_window(*args, **kwargs):
    backforward_button = backforward.BackForwardButton()
    win = get_test_window(child=backforward_button, *args, **kwargs)
    return win


def get_test_container_window():
    f = containers.FlowableGrid()

    for i in range(10):
        t = buttons.CategoryTile("test", "folder")
        f.add_child(t)

    scroll = Gtk.ScrolledWindow()
    scroll.add_with_viewport(f)

    win = get_test_window(child=scroll)
    return win


def _build_channels_list(popup):
    for i in range(3):
        item = Gtk.MenuItem.new()
        label = Gtk.Label.new("channel_name %s" % i)
        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, em.StockEms.MEDIUM)
        box.pack_start(label, False, False, 0)
        item.add(box)
        item.show_all()
        popup.attach(item, 0, 1, i, i + 1)


def get_test_buttons_window():
    vb = Gtk.VBox(spacing=12)
    link = buttons.Link("<small>test link</small>", uri="www.google.co.nz")
    vb.pack_start(link, False, False, 0)

    button = Gtk.Button()
    button.set_label("channels")
    channels_button = buttons.ChannelSelector(button)
    channels_button.parent_style_type = Gtk.Window
    channels_button.set_build_func(_build_channels_list)
    hb = Gtk.HBox()
    hb.pack_start(button, False, False, 0)
    hb.pack_start(channels_button, False, False, 0)
    vb.pack_start(hb, False, False, 0)

    win = get_test_window(child=vb)
    return win


def get_test_description_window():
    EXAMPLE0 = """p7zip is the Unix port of 7-Zip, a file archiver that \
archives with very high compression ratios.

p7zip-full provides:

 - /usr/bin/7za a standalone version of the 7-zip tool that handles
   7z archives (implementation of the LZMA compression algorithm) and some \
other formats.

 - /usr/bin/7z not only does it handle 7z but also ZIP, Zip64, CAB, RAR, \
ARJ, GZIP,
   BZIP2, TAR, CPIO, RPM, ISO and DEB archives. 7z compression is 30-50% \
better than ZIP compression.

p7zip provides 7zr, a light version of 7za, and p7zip a gzip like wrapper \
around 7zr."""

    EXAMPLE1 = """Transmageddon supports almost any format as its input and \
can generate a very large host of output files. The goal of the application \
was to help people to create the files they need to be able to play on their \
mobile devices and for people not hugely experienced with multimedia to \
generate a multimedia file without having to resort to command line tools \
with ungainly syntaxes.
The currently supported codecs are:
 * Containers:
  - Ogg
  - Matroska
  - AVI
  - MPEG TS
  - flv
  - QuickTime
  - MPEG4
  - 3GPP
  - MXT
 * Audio encoders:
  - Vorbis
  - FLAC
  - MP3
  - AAC
  - AC3
  - Speex
  - Celt
 * Video encoders:
  - Theora
  - Dirac
  - H264
  - MPEG2
  - MPEG4/DivX5
  - xvid
  - DNxHD
It also provide the support for the GStreamer's plugins auto-search."""

    EXAMPLE2 = """File-roller is an archive manager for the GNOME \
environment. It allows you to:
 * Create and modify archives.
 * View the content of an archive.
 * View a file contained in an archive.
 * Extract files from the archive.
File-roller supports the following formats:
 * Tar (.tar) archives, including those compressed with
   gzip (.tar.gz, .tgz), bzip (.tar.bz, .tbz), bzip2 (.tar.bz2, .tbz2),
   compress (.tar.Z, .taz), lzip (.tar.lz, .tlz), lzop (.tar.lzo, .tzo),
   lzma (.tar.lzma) and xz (.tar.xz)
 * Zip archives (.zip)
 * Jar archives (.jar, .ear, .war)
 * 7z archives (.7z)
 * iso9660 CD images (.iso)
 * Lha archives (.lzh)
 * Single files compressed with gzip (.gz), bzip (.bz), bzip2 (.bz2),
   compress (.Z), lzip (.lz), lzop (.lzo), lzma (.lzma) and xz (.xz)
File-roller doesn't perform archive operations by itself, but relies on \
standard tools for this."""

    EXAMPLE3 = """This package includes the following CTAN packages:
 Asana-Math -- A font to typeset maths in Xe(La)TeX.
 albertus --
 allrunes -- Fonts and LaTeX package for almost all runes.
 antiqua -- the URW Antiqua Condensed Font.
 antp -- Antykwa Poltawskiego: a Type 1 family of Polish traditional type.
 antt -- Antykwa Torunska: a Type 1 family of a Polish traditional type.
 apl -- Fonts for typesetting APL programs.
 ar -- Capital A and capital R ligature for Apsect Ratio.
 archaic -- A collection of archaic fonts.
 arev -- Fonts and LaTeX support files for Arev Sans.
 ascii -- Support for IBM "standard ASCII" font.
 astro -- Astronomical (planetary) symbols.
 atqolive --
 augie -- Calligraphic font for typesetting handwriting.
 auncial-new -- Artificial Uncial font and LaTeX support macros.
 aurical -- Calligraphic fonts for use with LaTeX in T1 encoding.
 barcodes -- Fonts for making barcodes.
 bayer -- Herbert Bayers Universal Font For Metafont.
 bbding -- A symbol (dingbat) font and LaTeX macros for its use.
 bbm -- "Blackboard-style" cm fonts.
 bbm-macros -- LaTeX support for "blackboard-style" cm fonts.
 bbold -- Sans serif blackboard bold.
 belleek -- Free replacement for basic MathTime fonts.
 bera -- Bera fonts.
 blacklettert1 -- T1-encoded versions of Haralambous old German fonts.
 boisik -- A font inspired by Baskerville design.
 bookhands -- A collection of book-hand fonts.
 braille -- Support for braille.
 brushscr -- A handwriting script font.
 calligra -- Calligraphic font.
 carolmin-ps -- Adobe Type 1 format of Carolingian Minuscule fonts.
 cherokee -- A font for the Cherokee script.
 clarendo --
 cm-lgc -- Type 1 CM-based fonts for Latin, Greek and Cyrillic.
 cmbright -- Computer Modern Bright fonts.
 cmll -- Symbols for linear logic.
 cmpica -- A Computer Modern Pica variant.
 coronet --
 courier-scaled -- Provides a scaled Courier font.
 cryst -- Font for graphical symbols used in crystallography.
 cyklop -- The Cyclop typeface.
 dancers -- Font for Conan Doyle's "The Dancing Men".
 dice -- A font for die faces.
 dictsym -- DictSym font and macro package
 dingbat -- Two dingbat symbol fonts.
 doublestroke -- Typeset mathematical double stroke symbols.
 dozenal -- Typeset documents using base twelve numbering (also called
  "dozenal")
 duerer -- Computer Duerer fonts.
 duerer-latex -- LaTeX support for the Duerer fonts.
 ean -- Macros for making EAN barcodes.
 ecc -- Sources for the European Concrete fonts.
 eco -- Oldstyle numerals using EC fonts.
 eiad -- Traditional style Irish fonts.
 eiad-ltx -- LaTeX support for the eiad font.
 elvish -- Fonts for typesetting Tolkien Elvish scripts.
 epigrafica -- A Greek and Latin font.
 epsdice -- A scalable dice "font".
 esvect -- Vector arrows.
 eulervm -- Euler virtual math fonts.
 euxm --
 feyn -- A font for in-text Feynman diagrams.
 fge -- A font for Frege's Grundgesetze der Arithmetik.
 foekfont -- The title font of the Mads Fok magazine.
 fonetika -- Support for the danish "Dania" phonetic system.
 fourier -- Using Utopia fonts in LaTeX documents.
 fouriernc -- Use New Century Schoolbook text with Fourier maths fonts.
 frcursive -- French cursive hand fonts.
 garamond --
 genealogy -- A compilation genealogy font.
 gfsartemisia -- A modern Greek font design.
 gfsbodoni -- A Greek and Latin font based on Bodoni.
 gfscomplutum -- A Greek font with a long history.
 gfsdidot -- A Greek font based on Didot's work.
 gfsneohellenic -- A Greek font in the Neo-Hellenic style.
 gfssolomos -- A Greek-alphabet font.
 gothic -- A collection of old German-style fonts.
 greenpoint -- The Green Point logo.
 groff --
 grotesq -- the URW Grotesk Bold Font.
 hands -- Pointing hand font.
 hfbright -- The hfbright fonts.
 hfoldsty -- Old style numerals with EC fonts.
 ifsym -- A collection of symbols.
 inconsolata -- A monospaced font, with support files for use with TeX.
 initials -- Adobe Type 1 decorative initial fonts.
 iwona -- A two-element sans-serif font.
 junicode -- A TrueType font for mediaevalists.
 kixfont -- A font for KIX codes.
 knuthotherfonts --
 kpfonts -- A complete set of fonts for text and mathematics.
 kurier -- A two-element sans-serif typeface.
 lettrgth --
 lfb -- A Greek font with normal and bold variants.
 libertine -- Use the font Libertine with LaTeX.
 libris -- Libris ADF fonts, with LaTeX support.
 linearA -- Linear A script fonts.
 logic -- A font for electronic logic design.
 lxfonts -- Set of slide fonts based on CM.
 ly1 -- Support for LY1 LaTeX encoding.
 marigold --
 mathabx -- Three series of mathematical symbols.
 mathdesign -- Mathematical fonts to fit with particular text fonts.
 mnsymbol -- Mathematical symbol font for Adobe MinionPro.
 nkarta -- A "new" version of the karta cartographic fonts.
 ocherokee -- LaTeX Support for the Cherokee language.
 ogham -- Fonts for typesetting Ogham script.
 oinuit -- LaTeX Support for the Inuktitut Language.
 optima --
 orkhun -- A font for orkhun script.
 osmanian -- Osmanian font for writing Somali.
 pacioli -- Fonts designed by Fra Luca de Pacioli in 1497.
 pclnfss -- Font support for current PCL printers.
 phaistos -- Disk of Phaistos font.
 phonetic -- MetaFont Phonetic fonts, based on Computer Modern.
 pigpen -- A font for the pigpen (or masonic) cipher.
 psafm --
 punk -- Donald Knuth's punk font.
 recycle -- A font providing the "recyclable" logo.
 sauter -- Wide range of design sizes for CM fonts.
 sauterfonts -- Use sauter fonts in LaTeX.
 semaphor -- Semaphore alphabet font.
 simpsons -- MetaFont source for Simpsons characters.
 skull -- A font to draw a skull.
 staves -- Typeset Icelandic staves and runic letters.
 tapir -- A simple geometrical font.
 tengwarscript -- LaTeX support for using Tengwar fonts.
 trajan -- Fonts from the Trajan column in Rome.
 umtypewriter -- Fonts to typeset with the xgreek package.
 univers --
 universa -- Herbert Bayer's 'universal' font.
 venturisadf -- Venturis ADF fonts collection.
 wsuipa -- International Phonetic Alphabet fonts.
 yfonts -- Support for old German fonts.
 zefonts -- Virtual fonts to provide T1 encoding from existing fonts."""

    EXAMPLE4 = """Arista is a simple multimedia transcoder, it focuses on \
being easy to use by making complex task of encoding for various devices \
simple.
Users should pick an input and a target device, choose a file to save to and \
go. Features:
* Presets for iPod, computer, DVD player, PSP, Playstation 3, and more.
* Live preview to see encoded quality.
* Automatically discover available DVD media and Video 4 Linux (v4l) devices.
* Rip straight from DVD media easily (requires libdvdcss).
* Rip straight from v4l devices.
* Simple terminal client for scripting.
* Automatic preset updating."""

    def on_clicked(widget, desc_widget, descs):
        widget.position += 1
        if widget.position >= len(descs):
            widget.position = 0
        desc_widget.set_description(*descs[widget.position])

    descs = ((EXAMPLE0, ''),
             (EXAMPLE1, ''),
             (EXAMPLE2, ''),
             (EXAMPLE3, 'texlive-fonts-extra'),
             (EXAMPLE4, ''))

    vb = Gtk.VBox()
    b = Gtk.Button('Next test description >>')
    b.position = 0
    vb.pack_start(b, False, False, 0)
    scroll = Gtk.ScrolledWindow()
    vb.add(scroll)
    d = description.AppDescription()
    #~ d.description.DEBUG_PAINT_BBOXES = True
    d.set_description(EXAMPLE0, pkgname='')
    scroll.add_with_viewport(d)

    b.connect("clicked", on_clicked, d, descs)

    win = get_test_window(child=vb)
    win.set_has_resize_grip(True)
    return win


@patch_datadir('./data')
def get_test_exhibits_window():
    exhibit_banner = exhibits.ExhibitBanner()

    exhibits_list = [exhibits.FeaturedExhibit()]
    for (i, (title, url)) in enumerate([
        ("1 some title", "https://wiki.ubuntu.com/Brand?"
            "action=AttachFile&do=get&target=orangeubuntulogo.png"),
        ("2 another title", "https://wiki.ubuntu.com/Brand?"
            "action=AttachFile&do=get&target=blackeubuntulogo.png"),
        ("3 yet another title", "https://wiki.ubuntu.com/Brand?"
            "action=AttachFile&do=get&target=xubuntu.png"),
        ]):
        exhibit = Mock()
        exhibit.id = i
        exhibit.package_names = "apt,2vcard"
        exhibit.published = True
        exhibit.style = "some uri to html"
        exhibit.title_translated = title
        exhibit.banner_url = url
        exhibit.html = None
        exhibits_list.append(exhibit)

    exhibit_banner.set_exhibits(exhibits_list)

    scroll = Gtk.ScrolledWindow()
    scroll.add_with_viewport(exhibit_banner)

    win = get_test_window(child=scroll)
    return win


def get_test_window_labels():
    HW_TEST_RESULT = {
        'hardware::gps': 'yes',
        'hardware::video:opengl': 'no',
    }

    # add it
    hwbox = labels.HardwareRequirementsBox()
    hwbox.set_hardware_requirements(HW_TEST_RESULT)

    win = get_test_window(child=hwbox)
    return win


def get_test_window_oneconfviews():

    w = oneconfviews.OneConfViews(Gtk.IconTheme.get_default())
    win = get_test_window(child=w)
    win.set_data("pane", w)

    # init the view
    w.register_computer("AAAAA", "NameA")
    w.register_computer("ZZZZZ", "NameZ")
    w.register_computer("DDDDD", "NameD")
    w.register_computer("CCCCC", "NameC")
    w.register_computer("", "This computer should be first")
    w.select_first()

    GLib.timeout_add_seconds(5, w.register_computer, "EEEEE", "NameE")

    def print_selected_hostid(widget, hostid, hostname):
        print("%s selected for %s" % (hostid, hostname))

    w.connect("computer-changed", print_selected_hostid)

    w.remove_computer("DDDDD")
    return win


@patch_datadir('./data')
def get_test_reviews_window():
    appdetails_mock = Mock()
    appdetails_mock.version = "2.0"

    parent = Mock()
    parent.app_details = appdetails_mock

    review_data = Mock()
    review_data.app_name = "app"
    review_data.usefulness_favorable = 10
    review_data.usefulness_total = 12
    review_data.usefulness_submit_error = False
    review_data.reviewer_username = "name"
    review_data.reviewer_displayname = "displayname"
    review_data.date_created = "2011-01-01 18:00:00"
    review_data.summary = "summary"
    review_data.review_text = 10 * "loonng text"
    review_data.rating = "3.0"
    review_data.version = "1.0"

    # create reviewslist
    vb = reviews.UIReviewsList(parent)
    vb.add_review(review_data)
    vb.configure_reviews_ui()

    win = get_test_window(child=vb)
    return win


def get_test_searchentry_window():
    icons = Gtk.IconTheme.get_default()
    entry = searchentry.SearchEntry(icons)
    entry.connect("terms-changed", lambda w, terms: print(terms))

    win = get_test_window(child=entry)
    win.entry = entry
    return win


def get_test_spinner_window():
    label = Gtk.Label("foo")
    spinner_notebook = spinner.SpinnerNotebook(label, "random msg")

    win = get_test_window(child=spinner_notebook)
    spinner_notebook.show_spinner("Loading for 1s ...")
    GLib.timeout_add_seconds(1, lambda: spinner_notebook.hide_spinner())
    return win


def get_test_stars_window():
    vb = Gtk.VBox()
    vb.set_spacing(6)

    win = get_test_window(child=vb)

    vb.add(Gtk.Button())
    vb.add(Gtk.Label(label="BLAHHHHHH"))

    star = stars.Star()
    star.set_n_stars(5)
    star.set_rating(2.5)
    star.set_size(stars.StarSize.SMALL)
    vb.pack_start(star, False, False, 0)

    star = stars.Star()
    star.set_n_stars(5)
    star.set_rating(2.5)
    star.set_size(stars.StarSize.NORMAL)
    vb.pack_start(star, False, False, 0)

    star = stars.Star()
    star.set_n_stars(5)
    star.set_rating(2.575)
    star.set_size(stars.StarSize.BIG)
    vb.pack_start(star, False, False, 0)

    star = stars.Star()
    star.set_n_stars(5)
    star.set_rating(3.333)
    star.set_size_as_pixel_value(36)
    vb.pack_start(star, False, False, 0)

    star = stars.ReactiveStar()
    star.set_n_stars(5)
    star.set_rating(3)
    star.set_size_as_pixel_value(em.big_em(3))
    vb.pack_start(star, False, False, 0)

    selector = stars.StarRatingSelector()
    vb.pack_start(selector, False, False, 0)

    return win


@patch_datadir('./data')
def get_test_symbolic_icons_window():
    hb = Gtk.HBox(spacing=12)
    ico = symbolic_icons.SymbolicIcon("available")
    hb.add(ico)
    ico = symbolic_icons.PendingSymbolicIcon("pending")
    ico.start()
    ico.set_transaction_count(33)
    hb.add(ico)
    ico = symbolic_icons.PendingSymbolicIcon("pending")
    ico.start()
    ico.set_transaction_count(1)
    hb.add(ico)
    win = get_test_window(child=hb)
    return win


def get_test_screenshot_thumbnail_window():

    class CycleState(object):
        def __init__(self):
            self.app_n = 0
            self.apps = [application.Application("Movie Player", "totem"),
                         application.Application("Comix", "comix"),
                         application.Application("Gimp", "gimp"),
                         #application.Application("ACE", "uace"),
                         ]

    def testing_cycle_apps(widget, thumb, db, cycle_state):
        d = cycle_state.apps[cycle_state.app_n].get_details(db)

        if cycle_state.app_n + 1 < len(cycle_state.apps):
            cycle_state.app_n += 1
        else:
            cycle_state.app_n = 0

        thumb.fetch_screenshots(d)
        return True

    cycle_state = CycleState()

    vb = Gtk.VBox(spacing=6)
    win = get_test_window(child=vb)

    icons = get_test_gtk3_icon_cache()
    distro = softwarecenter.distro.get_distro()

    t = thumbnail.ScreenshotGallery(distro, icons)
    t.connect('draw', t.draw)
    frame = containers.FramedBox()
    frame.add(t)

    win.set_data("screenshot_thumbnail_widget", t)

    b = Gtk.Button('A button for cycle testing')
    vb.pack_start(b, False, False, 8)
    win.set_data("screenshot_button_widget", b)
    vb.pack_start(frame, True, True, 0)
    win.set_data("screenshot_thumbnail_cycle_test_button", b)

    db = get_test_db()
    win.show_all()

    testing_cycle_apps(None, t, db, cycle_state)
    b.connect("clicked", testing_cycle_apps, t, db, cycle_state)

    return win


def get_test_videoplayer_window(video_url=None):
    Gdk.threads_init()

    # youtube example fragment
    html_youtube = """<iframe width="640" height="390"
src="http://www.youtube.com/embed/h3oBU0NZJuA" frameborder="0"
allowfullscreen></iframe>"""
    # vimeo example video fragment
    html_vimeo = """<iframe
src="http://player.vimeo.com/video/2891554?title=0&amp;byline=0&amp;portrait=0"
width="400" height="308" frameborder="0" webkitAllowFullScreen
allowFullScreen></iframe><p><a href="http://vimeo.com/2891554">
Supertuxkart 0.6</a> from <a href="http://vimeo.com/user1183699">
constantin pelikan</a> on <a href="http://vimeo.com">Vimeo</a>.</p>"""
    # dailymotion example video fragment
    html_dailymotion = """<iframe frameborder="0" width="480" height="270"
src="http://www.dailymotion.com/embed/video/xm4ysu"></iframe>"""
    html_dailymotion2 = """<iframe frameborder="0" width="480" height="379"
src="http://www.dailymotion.com/embed/video/xdiktp"></iframe>"""

    html_youtube  # pyflakes
    html_dailymotion  # pyflakes
    html_dailymotion2  # pyflakes

    player = videoplayer.VideoPlayer()
    win = get_test_window(child=player, width=500, height=400)

    if video_url is None:
        #player.uri = "http://upload.wikimedia.org/wikipedia/commons/9/9b/" \
        #    "Pentagon_News_Sample.ogg"
        #player.uri = "http://people.canonical.com/~mvo/totem.html"
        player.load_html_string(html_vimeo)
    else:
        player.uri = video_url

    return win


if __name__ == '__main__':
    if len(sys.argv) > 1:
        window_name = sys.argv[1]
        result = None
        for i in ('get_test_window_%s',
                  'get_%s_test_window',
                  'get_test_%s_window'):
            name = i % window_name
            print('Trying to execute: ', name)
            f = locals().get(name)
            if f is not None:
                print('Success! Running the main loop and showing the window.')
                # pass the renaming sys.argv to the function
                result = f(*sys.argv[2:])
                break

        if result is not None:
            if isinstance(result, Gtk.Dialog):
                response = result.run()
                result.hide()
                GLib.timeout_add(1, Gtk.main_quit)
            elif isinstance(result, Gtk.Window):
                result.connect("destroy", Gtk.main_quit)
            Gtk.main()
        else:
            print('ERROR: Found no test functions for', name)

    else:
        print("""Please provide the name of the window to test.
Examples are:

PYTHONPATH=. python tests/gtk3/windows.py dependency_dialog
PYTHONPATH=. python tests/gtk3/windows.py videoplayer
PYTHONPATH=. python tests/gtk3/windows.py videoplayer http://google.com
PYTHONPATH=. python tests/gtk3/windows.py appdetails
PYTHONPATH=. python tests/gtk3/windows.py appdetails firefox

""".format(sys.argv[0]))
