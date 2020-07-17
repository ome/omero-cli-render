CHANGES
=======

0.6.0
-----

*   Also set rendering setting (colors, windows) for disabled channels [#43](https://github.com/ome/omero-cli-render/pull/43)


0.5.1
-----

*   Fix channel re-activation when render set is passed without `--disable` [#40](https://github.com/ome/omero-cli-render/pull/40)
*   Fix REAMDE and usage [#41](https://github.com/ome/omero-cli-render/pull/41)

0.5.0
-----

*   Upgrade to Python 3 and consume new omero-py project [#31](https://github.com/ome/omero-cli-render/pull/31) [#32](https://github.com/ome/omero-cli-render/pull/32) [#37](https://github.com/ome/omero-cli-render/pull/37) [#38](https://github.com/ome/omero-cli-render/pull/38)
*   Refactor rendering settings parsing [#34](https://github.com/ome/omero-cli-render/pull/34)

0.4.3
-----

*   Actively close rendering services when applying `render set` to a
    collection of images [#29](https://github.com/ome/omero-cli-render/pull/29)

0.4.2
-----

*   Declare `PyYAML` as a package dependency
    [#28](https://github.com/ome/omero-cli-render/pull/28)

0.4.1
-----

*   Make output of `render info --style yaml` subcommand yamllint compliant
    [#26](https://github.com/ome/omero-cli-render/pull/26)
    [#27](https://github.com/ome/omero-cli-render/pull/27)

0.4.0
-----

*   Drop Python 2.6 support
    [#17](https://github.com/ome/omero-cli-render/pull/17)
*   CLI render version 2: use start/end for setting channel rendering window
    instead of min/max [#15](https://github.com/ome/omero-cli-render/pull/15)
    [#22](https://github.com/ome/omero-cli-render/pull/22)
*   CLI render version 2: add support for settings default z/t planes
    [#23](https://github.com/ome/omero-cli-render/pull/23)
    [#24](https://github.com/ome/omero-cli-render/pull/24)
*   Add logic for render version detection logic
    [#20](https://github.com/ome/omero-cli-render/pull/20)
*   Review integration tests
    [#21](https://github.com/ome/omero-cli-render/pull/21)


0.3.1
-----

* Add `--disable` option to `render set` [#9](https://github.com/ome/omero-cli-render/pull/9)
* Close services [#13](https://github.com/ome/omero-cli-render/pull/13)

0.3.0
-----

* Remove `--copy` flag of `render set` [#8](https://github.com/ome/omero-cli-render/pull/8)
* Fix auto-disabling of channels if not specified in the YML/JSON [#8](https://github.com/ome/omero-cli-render/pull/8)
* Improve command-line documentation [#8](https://github.com/ome/omero-cli-render/pull/8)

0.2.0
-----

* Rename `render edit` subcommand as `render set` and deprecate it [#7](https://github.com/ome/omero-cli-render/pull/7)
* Fix `render info` subcommand [#7](https://github.com/ome/omero-cli-render/pull/7)
* Allow rendering settings to be set at the Project/Dataset level [#7](https://github.com/ome/omero-cli-render/pull/7)

0.1.1
-----

* Use cross-group querying and improve documentation of `render test` [#6](https://github.com/ome/omero-cli-render/pull/6)

0.1.0
-----

* Extraction of the CLI render plugin from the openmicroscopy/openmicroscopy
* Initial PyPI release
