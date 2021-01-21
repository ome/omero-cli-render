#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import print_function
from past.builtins import long
from builtins import str
from builtins import range
from builtins import object
import sys
import time
import json
import yaml

from functools import wraps

from omero.cli import BaseControl
from omero.cli import CLI
from omero.cli import ProxyStringType
from omero.gateway import BlitzGateway
from omero.model import Image
from omero.model import Plate
from omero.model import Screen
from omero.model import Dataset
from omero.model import Project
from omero.model import StatsInfoI
from omero.rtypes import rint, rdouble
from omero.util import pydict_text_io

from omero import UnloadedEntityException

HELP = "Tools for working with rendering settings"

INFO_HELP = """Show details of a rendering setting

    The syntax for specifying objects is: <object>:<id>
    <object> can be Image, Project, Dataset, Plate or Screen.
    Image is assumed if <object>: is omitted

    Examples:
    omero render info Image:123
"""

COPY_HELP = """Copy rendering setting to multiple objects

    The syntax for specifying objects is: <object>:<id>
    <object> can be Image, Project, Dataset, Plate or Screen.
    Image is assumed if <object>: is omitted

    The first argument is the source of the rendering settings,
    the following arguments are the targets.

    Examples:
    omero render copy Image:456 Image:222 Image:333
    omero render copy Image:456 Plate:1
    omero render copy Image:456 Dataset:1
"""

EDIT_HELP = "Deprecated, please use 'set' instead"

SET_HELP = """Set rendering settings

    The syntax for specifying objects is: <object>:<id>
    <object> can be Image, Project, Dataset, Plate or Screen.
    Image is assumed if <object>: is omitted

    Examples:
    omero render set Image:1 settings.json
    omero render set Dataset:1 settings.yml

    # where the input file (YAML or JSON) contains:
    # - a top-level channels key (required)
    # - a version (recommended, current version: 2)
    # - an optional top-level greyscale key (True: greyscale,
    # False: color).
    # Channel elements are index:dictionaries of the form:

    channels:               Required
      <int>:                Channel index, 1-based
        active: <bool>      Active channel
        color: <string>     Channel color as HTML RGB triplet
        label: <string>     Channel name
        start: <float>      Start of rendering window, optional (needs end)
        end: <float>        End of rendering window, optional (needs start)
        min: <float>        Minimum pixel intensity, optional (needs max)
        max: <float>        Maximum pixel intensity, optional (needs min)
      <int>:
        ...
    greyscale: <bool>               Greyscale rendering, optional
    z: <int>                        Default Z plane index, 1-based, optional
    t: <int>                        Default T plane index, 1-based, optional
    version: 2                      Version of the renderdef specification

    For example:

    channels:
      1:
        color: "FF0000"
        label: "Red"
        start: 10.0
        end: 248.0
        active: True
      2:
        color: "00FF00"
      ...
    z: 5
    t: 1
    version: 2

    # Omitted fields will keep their current values.
    # Omitted channels will not be disabled unless --disable is used.
    # If the file specifies to turn off a channel (active: False) then the
    # other settings like start, end, and color which might be specified for
    # that channel in the same file will be ignored, however the channel
    # name (label) is still taken into account.
    # If min and max have not been set on the channel (no StatsInfo on the
    # channel) then you must set both. If max and min already set, each can
    # be updated individually.
"""

TEST_HELP = """Test that underlying pixel data is available

    The syntax for specifying objects is: <object>:<id>
    <object> can be Image, Project, Dataset, Plate or Screen.
    Image is assumed if <object>: is omitted

    Output:
    <Status>: <Pixels ID> <Time (in sec) to load the thumbnail> \
<Error details, if any>

    Where status is either ok, miss, fill, cancel, or fail.

    Examples:
    omero render test Image:1
"""

# Current version for specifying rendering settings
# in the yaml / json files
SPEC_VERSION = 2


def _set_if_not_none(dictionary, k, v):
    if v is not None:
        dictionary[k] = v


def _getversion(dictionary):
    """
    Returns the version of the rendering settings format.
    Note: Previously min/max was used to set the channel window start/end
    From version 2 on start/end will be used.

    Parameters:
    dictionary (dictionary): The rendering settings as dictionary

    Returns:
    int: The version or 0 if it cannot be determined
    """

    if 'version' not in dictionary:
        for chindex, chdict in dictionary['channels'].items():
            if ('start' in chdict or 'end' in chdict) and\
               ('min' in chdict or 'max' in chdict):
                return 0
            if 'start' in chdict or 'end' in chdict:
                return 2
            if 'min' in chdict or 'max' in chdict:
                return 1
    else:
        v = dictionary['version']
        if not isinstance(v, int) or v < 1 or v > SPEC_VERSION:
            return 0
        return v
    return SPEC_VERSION


class ChannelObject(object):
    """
    Represents the rendering settings of a channel

    Parameters:
    channel (IObject): The rendering settings as dictionary
    version (int):     The version of the renderings settings format
                       (optional; default: latest)
    """

    def __init__(self, channel, version=SPEC_VERSION):
        self.version = version
        try:
            self.init_from_channel(channel)
        except AttributeError:
            self.init_from_dict(channel)

    def init_from_channel(self, channel):
        self.emWave = channel.getEmissionWave()
        self.label = channel.getLabel()
        self.color = channel.getColor()
        try:
            self.min = channel.getWindowMin()
            self.max = channel.getWindowMax()
            self.start = channel.getWindowStart()
            self.end = channel.getWindowEnd()
        except UnloadedEntityException:
            self.min = None
            self.max = None
            self.start = None
            self.end = None
        self.active = channel.isActive()

    def init_from_dict(self, d):
        self.emWave = None
        self.label = d.get('label', None)
        self.color = d.get('color', None)
        self.min = float(d['min']) if 'min' in d else None
        self.max = float(d['max']) if 'max' in d else None
        if self.version > 1:
            self.start = float(d['start']) if 'start' in d else None
            self.end = float(d['end']) if 'end' in d else None
        else:
            self.start = self.min
            self.end = self.max
        self.active = bool(d.get('active', True))

    def __str__(self):
        try:
            color = self.color.getHtml()
        except AttributeError:
            color = self.color
        sb = ""
        sb += ",".join([
            "active=%s" % self.active,
            "color=%s" % color,
            "label=%s" % self.label,
            "min=%s" % self.min,
            "start=%s" % self.start,
            "end=%s" % self.end,
            "max=%s" % self.max,
        ])
        return sb

    def to_dict(self):
        """
        Return a dict of fields that are recognised by `render set`
        """
        try:
            color = self.color.getHtml()
        except AttributeError:
            color = self.color

        label = None
        if self.label is not None:
            label = str(self.label)
        d = {}
        _set_if_not_none(d, 'label', label)
        _set_if_not_none(d, 'color', color)
        _set_if_not_none(d, 'min', self.min)
        _set_if_not_none(d, 'max', self.max)
        _set_if_not_none(d, 'start', self.start)
        _set_if_not_none(d, 'end', self.end)
        _set_if_not_none(d, 'active', self.active)
        return d


class RenderObject(object):

    def __init__(self, image):
        """
        Based on omeroweb.webgateway.marshal

        Note: this loads a RenderingEngine and will need to
        have the instance closed.
        """
        assert image
        image.loadRenderOptions()
        self.image = image
        self.name = image.name or ''
        self.type = image.getPixelsType()
        re_ok = image._prepareRenderingEngine()
        if not re_ok:
            raise Exception(
                "Failed to prepare Rendering Engine for %s" % image)

        self.tiles = image._re.requiresPixelsPyramid()
        self.width = None
        self.height = None
        self.levels = None
        self.zoomLevelScaling = None
        if self.tiles:
            self.width, self.height = image._re.getTileSize()
            self.levels = image._re.getResolutionLevels()
            self.zoomLevelScaling = image.getZoomLevelScaling()

        self.range = image.getPixelRange()
        self.channels = [
            ChannelObject(x) for x in image.getChannels(noRE=False)]
        self.model = image.isGreyscaleRenderingModel() and \
            'greyscale' or 'color'
        self.projection = image.getProjection()
        self.defaultZ = image._re.getDefaultZ()
        self.defaultT = image._re.getDefaultT()

    def __str__(self):
        """Return a string representation of the render object"""
        sb = "rdefv%s: model=%s, z=%s, t=%s\n" % (
            SPEC_VERSION, self.model, self.defaultZ, self.defaultT)
        sb += "tiles: %s\n" % (self.tiles,)
        for idx, ch in enumerate(self.channels):
            sb += "ch%s: %s\n" % (idx, ch)
        return sb

    def to_dict(self):
        """
        Return a dict of fields that are recognised by `render set`
        """
        d = {}
        chs = {}
        for idx, ch in enumerate(self.channels, 1):
            chs[idx] = ch.to_dict()
        d['version'] = SPEC_VERSION
        d['z'] = int(self.defaultZ+1)
        d['t'] = int(self.defaultT+1)
        d['channels'] = chs
        d['greyscale'] = True if self.model == 'greyscale' else False
        return d


def gateway_required(func):
    """
    Decorator which initializes a client (self.client),
    a BlitzGateway (self.gateway), and makes sure that
    all services of the Blitzgateway are closed again.
    """
    @wraps(func)
    def _wrapper(self, *args, **kwargs):
        self.client = self.ctx.conn(*args)
        self.gateway = BlitzGateway(client_obj=self.client)

        try:
            return func(self, *args, **kwargs)
        finally:
            if self.gateway is not None:
                self.gateway.close(hard=False)
                self.gateway = None
                self.client = None
    return _wrapper


class RenderControl(BaseControl):

    gateway = None
    client = None

    def _configure(self, parser):
        parser.add_login_arguments()
        sub = parser.sub()
        info = parser.add(sub, self.info, INFO_HELP)
        copy = parser.add(sub, self.copy, COPY_HELP)
        set_cmd = parser.add(sub, self.set, SET_HELP)
        edit = parser.add(sub, self.edit, EDIT_HELP)
        test = parser.add(sub, self.test, TEST_HELP)

        render_type = ProxyStringType("Image")
        src_help = ("Rendering settings source")

        for x in (info, copy, test):
            x.add_argument("object", type=render_type, help=src_help)

        tgt_help = ("Objects to apply the rendering settings to")
        for x in (set_cmd, edit):
            x.add_argument("object", type=render_type, help=tgt_help,
                           nargs="+")

        for x in (copy, set_cmd, edit):
            x.add_argument(
                "--skipthumbs", help="Do not regenerate thumbnails "
                                     "immediately", action="store_true")

        output_formats = ['plain'] + list(
            pydict_text_io.get_supported_formats())
        info.add_argument(
            "--style", choices=output_formats, default='plain',
            help="Output format")

        copy.add_argument("target", type=render_type, help=tgt_help,
                          nargs="+")

        for x in (set_cmd, edit):
            x.add_argument(
                "--disable", help="Disable non specified channels ",
                action="store_true")
            x.add_argument(
                "--ignore-errors", help="Do not error on mismatching"
                " rendering settings", action="store_true")
            x.add_argument(
                "channels",
                help="Local file or OriginalFile:ID which specifies the "
                     "rendering settings")

        test.add_argument(
            "--force", action="store_true",
            help="Force creation of pixel data file in binary "
                 "repository if missing"
        )
        test.add_argument(
            "--thumb", action="store_true",
            help="If underlying pixel data available test thumbnail retrieval"
        )

    def _lookup(self, gateway, type, oid):
        # TODO: move _lookup to a _configure type
        gateway.SERVICE_OPTS.setOmeroGroup('-1')
        obj = gateway.getObject(type, oid)
        if not obj:
            self.ctx.die(110, "No such %s: %s" % (type, oid))
        return obj

    def render_images(self, gateway, object, batch=100):
        """
        Get the images.

        Parameters:
            gateway (BlitzGateway): The gateway
            object (IObject): The parent object (Project, Dataset, S, P, W)
            batch (int): The batch size

        Returns:
            Generator: List of images (IObjects)
        """

        if isinstance(object, list):
            for x in object:
                for rv in self.render_images(gateway, x, batch):
                    yield rv
        elif isinstance(object, Screen):
            scr = self._lookup(gateway, "Screen", object.id)
            for plate in scr.listChildren():
                for rv in self.render_images(gateway, plate._obj, batch):
                    yield rv
        elif isinstance(object, Plate):
            plt = self._lookup(gateway, "Plate", object.id)
            rv = []
            for well in plt.listChildren():
                for idx in range(0, well.countWellSample()):
                    img = well.getImage(idx)
                    if batch == 1:
                        yield img
                    else:
                        rv.append(img)
                        if len(rv) == batch:
                            yield rv
                            rv = []
            if rv:
                yield rv

        elif isinstance(object, Project):
            prj = self._lookup(gateway, "Project", object.id)
            for ds in prj.listChildren():
                for rv in self.render_images(gateway, ds._obj, batch):
                    yield rv

        elif isinstance(object, Dataset):
            ds = self._lookup(gateway, "Dataset", object.id)
            rv = []
            for img in ds.listChildren():
                if batch == 1:
                    yield img
                else:
                    rv.append(img)
                    if len(rv) == batch:
                        yield rv
                        rv = []
            if rv:
                yield rv

        elif isinstance(object, Image):
            img = self._lookup(gateway, "Image", object.id)
            if batch == 1:
                yield img
            else:
                yield [img]
        else:
            self.ctx.die(111, "TBD: %s" % object.__class__.__name__)

    @gateway_required
    def info(self, args):
        """ Implements the 'info' command """
        first = True
        for img in self.render_images(self.gateway, args.object, batch=1):
            try:
                ro = RenderObject(img)
                if args.style == 'plain':
                    self.ctx.out(str(ro))
                elif args.style == 'yaml':
                    self.ctx.out(yaml.dump(ro.to_dict(), explicit_start=True,
                                           width=80, indent=4,
                                           default_flow_style=False).rstrip())
                else:
                    if not first:
                        self.ctx.die(
                            103,
                            "Output styles not supported for multiple images")
                    self.ctx.out(json.dumps(
                        ro.to_dict(), sort_keys=True, indent=4))
                    first = False
            except Exception as e:
                self.ctx.err('ERROR: %s' % e)
            finally:
                img._closeRE()

    @gateway_required
    def copy(self, args):
        """ Implements the 'copy' command """
        for src_img in self.render_images(self.gateway, args.object, batch=1):
            for targets in self.render_images(self.gateway, args.target):
                batch = dict()
                for target in targets:
                    if target.id == src_img.id:
                        self.ctx.err(
                            "Skipping: Image:%s itself" % target.id)
                    else:
                        batch[target.id] = target

                if not batch:
                    continue

                rv = self.gateway.applySettingsToSet(src_img.id, "Image",
                                                     list(batch.keys()))
                for missing in rv[False]:
                    self.ctx.err("Error: Image:%s" % missing)
                    del batch[missing]

                self.ctx.out("Rendering settings successfully copied \
                              to %d images." % len(rv[True]))

                if not args.skipthumbs:
                    self._generate_thumbs(list(batch.values()))

    def update_channel_names(self, gateway, obj, namedict):
        for targets in self.render_images(gateway, obj):
            iids = [img.id for img in targets]
            self._update_channel_names(self, iids, namedict)

    def _update_channel_names(self, gateway, iids, namedict):
        counts = gateway.setChannelNames("Image", iids, namedict)
        if counts:
            self.ctx.dbg("Updated channel names for %d/%d images" % (
                counts['updateCount'], counts['imageCount']))

    def _generate_thumbs(self, images):
        for img in images:
            start = time.time()
            img.getThumbnail(size=(96,), direct=False)
            stop = time.time()
            self.ctx.dbg("Image:%s got thumbnail in %2.2fs" % (
                img.id, stop - start))

    def _read_default_planes(self, img, data, ignore_errors=False):
        """Read and validate the default planes"""

        # Read values from dictionary
        def_z = data['z'] if 'z' in data else None
        def_t = data['t'] if 't' in data else None

        # Minimal validation: default planes should be 1-indexed integers
        if (def_z is not None) and (def_z < 1 or int(def_z) != def_z):
            self.ctx.die(
                105, "Invalid default Z plane: %s" % def_z)
        if (def_t is not None) and (def_t < 1 or int(def_t) != def_t):
            self.ctx.die(
                105, "Invalid default T plane: %s" % def_t)

        # Validate default plane index against image dimensions
        if def_z and def_z > img.getSizeZ():
            msg = ("Inconsistent default Z plane. Expected to set %s but the"
                   " image dimension is %s" % (def_z, img.getSizeZ()))
            if not ignore_errors:
                self.ctx.die(106, msg)
            else:
                self.ctx.dbg(msg + ". Ignoring.")
                def_z = None
        if def_t and def_t > img.getSizeT():
            msg = ("Inconsistent default T plane. Expected to set %s but the"
                   " image dimension is %s" % (def_t, img.getSizeT()))
            if not ignore_errors:
                self.ctx.die(106, msg)
            else:
                self.ctx.dbg(msg + ". Ignoring.")
                def_t = None
        return (def_z, def_t)

    def _load_rendering_settings(self, source, session=None):
        """Load a rendering dictionary from a source (file or object)"""
        try:
            data = pydict_text_io.load(source, session=session)
        except Exception as e:
            self.ctx.dbg(e)
            self.ctx.die(103, "Could not read %s" % source)

        if 'channels' not in data:
            self.ctx.die(104, "ERROR: No channels found in %s" % source)

        version = _getversion(data)
        if version == 0:
            self.ctx.die(124, "ERROR: Cannot determine version. Specify"
                              " version or use either start/end or min/max"
                              " (not both).")
        return data

    def _read_channels(self, data):
        """Read new channels from settings dictionary"""
        newchannels = {}
        version = _getversion(data)
        # Read channel setttings from rendering dictionary
        for chindex, chdict in data['channels'].items():
            try:
                cindex = int(chindex)
            except Exception as e:
                self.ctx.err('ERROR: %s' % e)
                self.ctx.die(
                    105, "Invalid channel index: %s" % chindex)

            try:
                cobj = ChannelObject(chdict, version)
                newchannels[cindex] = cobj
                self.ctx.dbg('%d:%s' % (cindex, cobj))
            except Exception as e:
                self.ctx.err('ERROR: %s' % e)
                self.ctx.die(
                    105, "Invalid channel description: %s" % chdict)

        namedict = {}
        cindices = []
        rangelist = []
        colourlist = []
        minmaxlist = []
        for (i, c) in newchannels.items():
            if c.label:
                namedict[i] = c.label
            if c.active is False:
                cindices.append(-i)
            else:
                cindices.append(i)
            rangelist.append([c.start, c.end])
            colourlist.append(c.color)
            minmaxlist.append([c.min, c.max])
        rv = (namedict, cindices, rangelist, colourlist, minmaxlist)
        return rv

    @gateway_required
    def set(self, args):
        """ Implements the 'set' command """
        data = self._load_rendering_settings(
            args.channels, session=self.client.getSession())
        (namedict, cindices, rangelist, colourlist, minmaxlist) = \
            self._read_channels(data)
        greyscale = data.get('greyscale', None)
        if greyscale is not None:
            self.ctx.dbg('greyscale=%s' % greyscale)

        iids = []
        for img in self.render_images(self.gateway, args.object, batch=1):
            iids.append(img.id)

            (def_z, def_t) = self._read_default_planes(
                img, data, ignore_errors=args.ignore_errors)

            active_channels = []
            if not args.disable:
                # Calling set_active_channels will disable channels which
                # are not specified.
                # Need to reset ALL active channels after set_active_channels()
                imgchannels = img.getChannels()
                for ci, ch in enumerate(imgchannels, 1):
                    if (-ci not in cindices and ch.isActive()) \
                            or ci in cindices:
                        active_channels.append(ci)

            img.set_active_channels(
                cindices, windows=rangelist, colors=colourlist,
                set_inactive=True)

            if greyscale is not None:
                if greyscale:
                    img.setGreyscaleRenderingModel()
                else:
                    img.setColorRenderingModel()

            # Re-activate any un-listed channels
            if len(active_channels) > 0:
                img.set_active_channels(active_channels)

            # Set statsInfo min & max
            for minmax, ch in zip(minmaxlist, img.getChannels(noRE=True)):
                if minmax[0] is None and minmax[1] is None:
                    continue
                si = ch.getStatsInfo()
                if si is None:
                    si = StatsInfoI()
                else:
                    si = si._obj
                if minmax[0] is not None:
                    si.globalMin = rdouble(minmax[0])
                if minmax[1] is not None:
                    si.globalMax = rdouble(minmax[1])
                ch._obj.statsInfo = si
                ch.save()

            if def_z:
                img.setDefaultZ(def_z - 1)
            if def_t:
                img.setDefaultT(def_t - 1)

            try:
                img.saveDefaults()
                self.ctx.dbg(
                    "Updated rendering settings for Image:%s" % img.id)
                if not args.skipthumbs:
                    self._generate_thumbs([img])
            except Exception as e:
                self.ctx.err('ERROR: %s' % e)
            finally:
                img._closeRE()

        if not iids:
            self.ctx.die(113, "ERROR: No images found for %s %d" %
                         (args.object.__class__.__name__, args.object.id._val))

        if namedict:
            self._update_channel_names(self.gateway, iids, namedict)

    def edit(self, args):
        self.ctx.die(112, "ERROR: 'edit' command has been renamed to 'set'")

    @gateway_required
    def test(self, args):
        """ Implements the 'test' command """
        self.gateway.SERVICE_OPTS.setOmeroGroup('-1')
        for img in self.render_images(self.gateway, args.object, batch=1):
            self.test_per_pixel(
                self.client, img.getPrimaryPixels().id, args.force, args.thumb)

    def test_per_pixel(self, client, pixid, force, thumb):
        ctx = {'omero.group': '-1'}
        fail = {"omero.pixeldata.fail_if_missing": "true"}
        fail.update(ctx)
        make = {"omero.pixeldata.fail_if_missing": "false"}
        make.update(ctx)

        start = time.time()
        error = ""
        rps = client.sf.createRawPixelsStore()

        try:
            rps.setPixelsId(long(pixid), False, fail)
            msg = "ok:"
        except Exception as e:
            error = e
            msg = "miss:"

        if msg == "ok:" or not force:
            rps.close()
        else:
            try:
                rps.setPixelsId(long(pixid), False, make)
                msg = "fill:"
            except KeyboardInterrupt:
                msg = "cancel:"
                pass
            except Exception as e:
                msg = "fail:"
                error = e
            finally:
                rps.close()

        if error:
            error = str(error).split("\n")[0]
        elif thumb:
            tb = client.sf.createThumbnailStore()
            try:
                tb.setPixelsId(int(pixid), ctx)
                tb.getThumbnailByLongestSide(rint(96), ctx)
            finally:
                tb.close()

        stop = time.time()
        self.ctx.out("%s %s %s %s" % (msg, pixid, stop-start, error))
        return msg


try:
    register("render", RenderControl, HELP)
except NameError:
    if __name__ == "__main__":
        cli = CLI()
        cli.register("render", RenderControl, HELP)
        cli.invoke(sys.argv[1:])
