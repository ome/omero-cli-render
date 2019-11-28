#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2015-2018 University of Dundee & Open Microscopy Environment.
# All rights reserved.
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


from omero.cli import CLI, NonZeroReturnCode
from omero_cli_render import RenderControl

import pytest
import uuid
import yaml


def write_yaml(d, tmpdir):
    f = tmpdir.join(str(uuid.uuid4()) + ".yml")
    f.write(yaml.dump(d, explicit_start=True, width=80, indent=4,
                      default_flow_style=False))
    return str(f)


class TestLoadRenderingSettings:
    def setup_method(self):
        self.cli = CLI()
        self.cli.register("render", RenderControl, "TEST")
        self.render = self.cli.controls['render']

    def test_none(self):
        with pytest.raises(NonZeroReturnCode):
            self.render._load_rendering_settings(None)

    def test_non_existing_file(self):
        with pytest.raises(NonZeroReturnCode) as e:
            self.render._load_rendering_settings(str(uuid.uuid4()) + '.yml')
        assert e.value.rv == 103

    def test_no_channels(self, tmpdir):
        d = {'version': 1}
        f = write_yaml(d, tmpdir)
        with pytest.raises(NonZeroReturnCode) as e:
            self.render._load_rendering_settings(f)
        assert e.value.rv == 104

    def test_bad_version(self, tmpdir):
        d = {'channels': {1: {'label': 'foo'}}}
        f = write_yaml(d, tmpdir)
        with pytest.raises(NonZeroReturnCode) as e:
            self.render._load_rendering_settings(f)
        assert e.value.rv == 124
