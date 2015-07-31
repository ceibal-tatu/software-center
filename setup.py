#!/usr/bin/python
#
# Copyright 2009-2013 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Setup.py: build, distribute, clean."""

import platform
import glob
import sys

from DistUtilsExtra.auto import setup

# The VERSION of software-center
VERSION = '13.10'

# Get the distribution information for various functions.
(distro, release, codename) = platform.dist()


def merge_extras_ubuntu_com_channel_file():
    # TODO: Only do this during setup.py install.
    # update ubuntu-extras.list.in (this will not be part of debian as
    # its killed of in debian/rules on a non-ubuntu build)
    channelfile = "data/channels/Ubuntu/ubuntu-extras.list"
    s = open(channelfile + ".in").read()
    open(channelfile, "w").write(s.replace("#DISTROSERIES#", codename))


# update version.py
def update_version():
    # TODO: Move this to a build command.
    # this comes from the build host
    open("softwarecenter/version.py", "w").write("""
VERSION = '%s'
CODENAME = '%s'
DISTRO = '%s'
RELEASE = '%s'
""" % (VERSION, codename, distro, release))

# update po4a
if sys.argv[1] == "build":
    update_version()
    merge_extras_ubuntu_com_channel_file()


# real setup
setup(
    name="software-center",
    version=VERSION,
    scripts=[
        "bin/software-center",
        "bin/software-center-dbus",
        # gtk3
        "utils/submit_review_gtk3.py",
        "utils/report_review_gtk3.py",
        "utils/submit_usefulness_gtk3.py",
        "utils/delete_review_gtk3.py",
        "utils/modify_review_gtk3.py",
        # db helpers
        "utils/update-software-center",
        "utils/update-software-center-channels",
        "utils/update-software-center-agent",
        # generic helpers
        "utils/expunge-cache.py",
    ] + glob.glob("utils/piston-helpers/*.py"),
    packages=[
        'softwarecenter',
        'softwarecenter.backend',
        'softwarecenter.backend.installbackend_impl',
        'softwarecenter.backend.channel_impl',
        'softwarecenter.backend.oneconfhandler',
        'softwarecenter.backend.login_impl',
        'softwarecenter.backend.piston',
        'softwarecenter.backend.reviews',
        'softwarecenter.db',
        'softwarecenter.db.pkginfo_impl',
        'softwarecenter.db.history_impl',
        'softwarecenter.distro',
        'softwarecenter.plugins',
        'softwarecenter.ui',
        'softwarecenter.ui.gtk3',
        'softwarecenter.ui.gtk3.dialogs',
        'softwarecenter.ui.gtk3.models',
        'softwarecenter.ui.gtk3.panes',
        'softwarecenter.ui.gtk3.session',
        'softwarecenter.ui.gtk3.views',
        'softwarecenter.ui.gtk3.widgets',
        'softwarecenter.ui.qml',
    ],
    data_files=[
        # gtk3
        ('share/software-center/ui/gtk3/', glob.glob("data/ui/gtk3/*.ui")),
        ('share/software-center/ui/gtk3/css/',
         glob.glob("data/ui/gtk3/css/*.css")),
        ('share/software-center/ui/gtk3/art/',
         glob.glob("data/ui/gtk3/art/*.png")),
        ('share/software-center/ui/gtk3/art/icons',
         glob.glob("data/ui/gtk3/art/icons/*.png")),
        ('share/software-center/default_banner',
         glob.glob("data/default_banner/*")),
        # dbus
        ('../etc/dbus-1/system.d/',
         ["data/dbus/com.ubuntu.SoftwareCenter.conf"]),
        ('share/dbus-1/services',
         ["data/dbus/com.ubuntu.SoftwareCenterDataProvider.service"]),
        # images
        ('share/software-center/images/',
         glob.glob("data/images/*.png") + glob.glob("data/images/*.gif")),
        ('share/software-center/icons/', glob.glob("data/emblems/*.png")),
        # xapian
        ('share/apt-xapian-index/plugins',
         glob.glob("apt_xapian_index_plugin/*.py")),
        # apport
        # TODO: Move this over from the packaging
        # ('share/apport/package-hooks/', ['debian/source_software-center.py']),
        # extra software channels (can be distro specific)
        ('share/app-install/channels/',
         glob.glob("data/channels/%s/*.{eula,list}" % distro)),
    ],
)
