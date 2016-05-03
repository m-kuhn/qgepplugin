#-----------------------------------------------------------
#
# QGEP
# Copyright (C) 2016 Matthias Kuhn
#
#-----------------------------------------------------------
#
# licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#---------------------------------------------------------------------

import qgis
import nose2

from qgis.testing import start_app, unittest
from qgis.testing.mocked import get_iface
from ..qgepplugin import QgepPlugin

class TestLoadPlugin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start_app()
        cls.iface = get_iface()

    def test_init_gui(self):
        qgepplugin = QgepPlugin(self.iface)
