# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2015, 2017-2019 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import collections
import json
import os
import tarfile
from textwrap import dedent
from unittest import mock

import fixtures
from testscenarios.scenarios import multiply_scenarios
from testtools.matchers import Equals, HasLength, FileExists

from snapcraft.plugins import nodejs
from snapcraft.internal import errors
from snapcraft.project import Project
from tests import fixture_setup, unit


class NodePluginBaseTest(unit.TestCase):
    def setUp(self):
        super().setUp()

        snapcraft_yaml_path = self.make_snapcraft_yaml(
            dedent(
                """\
            name: go-snap
            base: core18
        """
            )
        )

        self.project = Project(snapcraft_yaml_file_path=snapcraft_yaml_path)

        class Options:
            source = "."
            nodejs_version = nodejs._NODEJS_VERSION
            nodejs_package_manager = "npm"
            nodejs_yarn_version = ""
            source = "."

        self.options = Options()

        # always have a package.json stub under source
        open("package.json", "w").close()

        patcher = mock.patch("snapcraft.internal.common.run")
        self.run_mock = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch("snapcraft.internal.common.run_output")
        self.run_output_mock = patcher.start()
        self.addCleanup(patcher.stop)
        self.run_output_mock.return_value = '{"dependencies": []}'

        patcher = mock.patch("snapcraft.sources.Tar")
        self.tar_mock = patcher.start()
        self.addCleanup(patcher.stop)

        self.nodejs_url = nodejs.get_nodejs_release(
            nodejs._NODEJS_VERSION, self.project.deb_arch
        )

        self.useFixture(fixture_setup.CleanEnvironment())

    def create_assets(
        self,
        plugin,
        package_name="test-nodejs",
        single_bin=False,
        skip_package_json=False,
    ):
        for directory in (plugin.sourcedir, plugin.builddir):
            os.makedirs(directory)
            if not skip_package_json:
                with open(os.path.join(directory, "package.json"), "w") as json_file:
                    json.dump(
                        dict(
                            name=package_name, bin=dict(run="index.js"), version="1.0"
                        ),
                        json_file,
                    )
            package_name = package_name.lstrip("@").replace("/", "-")
            packed_tar_file = os.path.join(directory, "{}-1.0.tgz".format(package_name))
            open(os.path.join(directory, "index.js"), "w").close()
        tarfile.TarFile(packed_tar_file, "w").close()

        def provision(directory, **kwargs):
            if directory == os.path.join(plugin.builddir, "package"):
                package_dir = os.path.join(plugin.builddir, "package")
                open(os.path.join(package_dir, "index.js"), "w").close()

        self.tar_mock().provision.side_effect = provision

        # Create a fake node bin
        os.makedirs(os.path.join(plugin._npm_dir, "bin"))
        open(os.path.join(plugin._npm_dir, "bin", "node"), "w").close()


class NodejsPluginPropertiesTest(unit.TestCase):
    def test_schema(self):
        schema = nodejs.NodePlugin.schema()
        properties = schema["properties"]

        # Check nodejs-version
        self.assertTrue(
            "nodejs-version" in properties,
            'Expected "nodejs-version" to be included in ' "properties",
        )
        node_channel = properties["nodejs-version"]

        self.assertTrue(
            "type" in node_channel, 'Expected "type" to be included in "nodejs-version"'
        )
        self.assertThat(
            node_channel["type"],
            Equals("string"),
            'Expected "nodejs-version" "type" to be '
            '"string", but it was '
            '"{}"'.format(node_channel["type"]),
        )
        self.assertTrue(
            "default" in node_channel,
            'Expected "default" to be included in "nodejs-version"',
        )
        self.assertThat(
            node_channel["default"],
            Equals(nodejs._NODEJS_VERSION),
            'Expected "nodejs-version" "default" to be '
            '"{}", but it was '
            '"{}"'.format(nodejs._NODEJS_VERSION, node_channel["default"]),
        )

        # Check nodejs-yarn-version
        self.assertTrue(
            "nodejs-yarn-version" in properties,
            'Expected "nodejs-yarn-version" to be included in ' "properties",
        )
        node_channel = properties["nodejs-yarn-version"]

        self.assertTrue(
            "type" in node_channel,
            'Expected "type" to be included in "nodejs-yarn-version"',
        )
        self.assertThat(
            node_channel["type"],
            Equals("string"),
            'Expected "nodejs-yarn-version" "type" to be '
            '"string", but it was '
            '"{}"'.format(node_channel["type"]),
        )
        self.assertTrue(
            "default" in node_channel,
            'Expected "default" to be included in "nodejs-yarn-version"',
        )
        self.assertThat(
            node_channel["default"],
            Equals(""),
            'Expected "nodejs-yarn-version" "default" to be '
            '"", but it was '
            '"{}"'.format(node_channel["default"]),
        )

        # Check nodejs-package-manager
        self.assertTrue(
            "nodejs-package-manager" in properties,
            'Expected "nodejs-package-manager" to be included in ' "properties",
        )
        nodejs_package_manager = properties["nodejs-package-manager"]

        self.assertTrue(
            "type" in nodejs_package_manager,
            'Expected "type" to be included in "nodejs-package-manager"',
        )
        self.assertThat(
            nodejs_package_manager["type"],
            Equals("string"),
            'Expected "nodejs-package-manager" "type" to be '
            '"string", but it was '
            '"{}"'.format(nodejs_package_manager["type"]),
        )
        self.assertTrue(
            "default" in nodejs_package_manager,
            'Expected "default" to be included in "nodejs-package-manager"',
        )
        self.assertThat(
            nodejs_package_manager["default"],
            Equals("yarn"),
            'Expected "nodejs-package-manager" "default" to be '
            '"yarn", but it was '
            '"{}"'.format(nodejs_package_manager["default"]),
        )

    def test_get_pull_properties(self):
        expected_pull_properties = [
            "nodejs-version",
            "nodejs-package-manager",
            "nodejs-yarn-version",
        ]
        resulting_pull_properties = nodejs.NodePlugin.get_pull_properties()

        self.assertThat(
            resulting_pull_properties, HasLength(len(expected_pull_properties))
        )

        for property in expected_pull_properties:
            self.assertIn(property, resulting_pull_properties)

    def test_get_build_properties(self):
        expected_build_properties = []
        resulting_build_properties = nodejs.NodePlugin.get_build_properties()

        self.assertThat(
            resulting_build_properties, HasLength(len(expected_build_properties))
        )

        for property in expected_build_properties:
            self.assertIn(property, resulting_build_properties)


class NodePluginTest(NodePluginBaseTest):

    scenarios = multiply_scenarios(
        [
            ("without-proxy", dict(http_proxy=None, https_proxy=None)),
            (
                "with-proxy",
                dict(
                    http_proxy="http://localhost:3132",
                    https_proxy="http://localhost:3133",
                ),
            ),
        ],
        [("npm", dict(package_manager="npm")), ("yarn", dict(package_manager="yarn"))],
    )

    def setUp(self):
        super().setUp()
        for v in ("http_proxy", "https_proxy"):
            self.useFixture(fixtures.EnvironmentVariable(v, getattr(self, v)))

        self.options.nodejs_package_manager = self.package_manager

    def get_npm_cmd(self, plugin):
        return os.path.join(plugin._npm_dir, "bin", "npm")

    def get_yarn_cmd(self, plugin):
        return os.path.join(plugin._npm_dir, "bin", "yarn")

    def test_pull(self):
        plugin = nodejs.NodePlugin("test-part", self.options, self.project)

        self.create_assets(plugin)

        plugin.pull()

        self.run_mock.assert_has_calls([])

        expected_env = dict(PATH=os.path.join(plugin._npm_dir, "bin"))
        if self.http_proxy is not None:
            expected_env["http_proxy"] = self.http_proxy
        if self.https_proxy is not None:
            expected_env["https_proxy"] = self.https_proxy
        if self.package_manager == "npm":
            expected_run_calls = [
                mock.call(
                    [self.get_npm_cmd(plugin), "install"],
                    cwd=plugin.sourcedir,
                    env=expected_env,
                ),
                mock.call(
                    [self.get_npm_cmd(plugin), "pack"],
                    cwd=plugin.sourcedir,
                    env=expected_env,
                ),
                mock.call(
                    [self.get_npm_cmd(plugin), "install"],
                    cwd=os.path.join(plugin.sourcedir, "package"),
                    env=expected_env,
                ),
            ]
            expected_tar_calls = [
                mock.call(self.nodejs_url, plugin._npm_dir),
                mock.call().download(),
                mock.call().provision(
                    plugin._npm_dir, clean_target=False, keep_tarball=True
                ),
            ]
        else:
            cmd = [self.get_yarn_cmd(plugin)]
            if self.http_proxy is not None:
                cmd.extend(["--proxy", self.http_proxy])
            if self.https_proxy is not None:
                cmd.extend(["--https-proxy", self.https_proxy])
            expected_run_calls = [
                mock.call(cmd + ["install"], cwd=plugin.sourcedir, env=expected_env),
                mock.call(
                    cmd + ["pack", "--filename", "test-nodejs-1.0.tgz"],
                    cwd=plugin.sourcedir,
                    env=expected_env,
                ),
                mock.call(
                    cmd + ["install"],
                    cwd=os.path.join(plugin.sourcedir, "package"),
                    env=expected_env,
                ),
            ]
            expected_tar_calls = [
                mock.call(self.nodejs_url, plugin._npm_dir),
                mock.call().download(),
                mock.call("https://yarnpkg.com/latest.tar.gz", plugin._npm_dir),
                mock.call().download(),
                mock.call().provision(
                    plugin._npm_dir, clean_target=False, keep_tarball=True
                ),
                mock.call().provision(
                    plugin._npm_dir, clean_target=False, keep_tarball=True
                ),
            ]

        self.run_mock.assert_has_calls(expected_run_calls)
        self.tar_mock.assert_has_calls(expected_tar_calls)

    def test_build(self):
        plugin = nodejs.NodePlugin("test-part", self.options, self.project)

        self.create_assets(plugin)

        plugin.build()

        self.assertThat(os.path.join(plugin.installdir, "bin", "run"), FileExists())

        expected_env = dict(PATH=os.path.join(plugin._npm_dir, "bin"))
        if self.http_proxy is not None:
            expected_env["http_proxy"] = self.http_proxy
        if self.https_proxy is not None:
            expected_env["https_proxy"] = self.https_proxy
        if self.package_manager == "npm":
            expected_run_calls = [
                mock.call(
                    [self.get_npm_cmd(plugin), "install", "--offline", "--prod"],
                    cwd=plugin.builddir,
                    env=expected_env,
                ),
                mock.call(
                    [self.get_npm_cmd(plugin), "pack"],
                    cwd=plugin.builddir,
                    env=expected_env,
                ),
                mock.call(
                    [self.get_npm_cmd(plugin), "install", "--offline", "--prod"],
                    cwd=os.path.join(plugin.builddir, "package"),
                    env=expected_env,
                ),
            ]
            expected_tar_calls = [
                mock.call(self.nodejs_url, plugin._npm_dir),
                mock.call().provision(
                    plugin._npm_dir, clean_target=False, keep_tarball=True
                ),
                mock.call("test-nodejs-1.0.tgz", plugin.builddir),
                mock.call().provision(os.path.join(plugin.builddir, "package")),
            ]
        else:
            cmd = [self.get_yarn_cmd(plugin)]
            if self.http_proxy is not None:
                cmd.extend(["--proxy", self.http_proxy])
            if self.https_proxy is not None:
                cmd.extend(["--https-proxy", self.https_proxy])
            expected_run_calls = [
                mock.call(
                    cmd + ["install", "--offline", "--prod"],
                    cwd=plugin.builddir,
                    env=expected_env,
                ),
                mock.call(
                    cmd + ["pack", "--filename", "test-nodejs-1.0.tgz"],
                    cwd=plugin.builddir,
                    env=expected_env,
                ),
                mock.call(
                    cmd + ["install", "--offline", "--prod"],
                    cwd=os.path.join(plugin.builddir, "package"),
                    env=expected_env,
                ),
            ]
            expected_tar_calls = [
                mock.call(self.nodejs_url, plugin._npm_dir),
                mock.call().provision(
                    plugin._npm_dir, clean_target=False, keep_tarball=True
                ),
                mock.call("https://yarnpkg.com/latest.tar.gz", plugin._npm_dir),
                mock.call().provision(
                    plugin._npm_dir, clean_target=False, keep_tarball=True
                ),
                mock.call("test-nodejs-1.0.tgz", plugin.builddir),
                mock.call().provision(os.path.join(plugin.builddir, "package")),
            ]

        self.run_mock.assert_has_calls(expected_run_calls)
        self.tar_mock.assert_has_calls(expected_tar_calls)

        expected_tar_calls = [
            mock.call("test-nodejs-1.0.tgz", plugin.builddir),
            mock.call().provision(os.path.join(plugin.builddir, "package")),
        ]
        self.tar_mock.assert_has_calls(expected_tar_calls)

    def test_build_scoped_name(self):
        plugin = nodejs.NodePlugin("test-part", self.options, self.project)

        self.create_assets(plugin, package_name="@org/name")

        plugin.build()

        if self.package_manager == "npm":
            expected_run_calls = [
                mock.call(
                    [self.get_npm_cmd(plugin), "install", "--offline", "--prod"],
                    cwd=os.path.join(plugin.builddir),
                    env=mock.ANY,
                ),
                mock.call(
                    [self.get_npm_cmd(plugin), "pack"],
                    cwd=plugin.builddir,
                    env=mock.ANY,
                ),
                mock.call(
                    [self.get_npm_cmd(plugin), "install", "--offline", "--prod"],
                    cwd=os.path.join(plugin.builddir, "package"),
                    env=mock.ANY,
                ),
            ]
        else:
            cmd = [self.get_yarn_cmd(plugin)]
            if self.http_proxy is not None:
                cmd.extend(["--proxy", self.http_proxy])
            if self.https_proxy is not None:
                cmd.extend(["--https-proxy", self.https_proxy])
            expected_run_calls = [
                mock.call(
                    cmd + ["install", "--offline", "--prod"],
                    cwd=plugin.builddir,
                    env=mock.ANY,
                ),
                mock.call(
                    cmd + ["pack", "--filename", "org-name-1.0.tgz"],
                    cwd=plugin.builddir,
                    env=mock.ANY,
                ),
                mock.call(
                    cmd + ["install", "--offline", "--prod"],
                    cwd=os.path.join(plugin.builddir, "package"),
                    env=mock.ANY,
                ),
            ]

        self.run_mock.assert_has_calls(expected_run_calls)

        expected_tar_calls = [
            mock.call("org-name-1.0.tgz", plugin.builddir),
            mock.call().provision(os.path.join(plugin.builddir, "package")),
        ]
        self.tar_mock.assert_has_calls(expected_tar_calls)


class NodePluginManifestTest(NodePluginBaseTest):
    scenarios = multiply_scenarios(
        [
            (
                "simple",
                dict(
                    ls_output=(
                        '{"dependencies": {'
                        '   "testpackage1": {"version": "1.0"},'
                        '   "testpackage2": {"version": "1.2"}}}'
                    ),
                    expected_dependencies=["testpackage1=1.0", "testpackage2=1.2"],
                ),
            ),
            (
                "nested",
                dict(
                    ls_output=(
                        '{"dependencies": {'
                        '   "testpackage1": {'
                        '      "version": "1.0",'
                        '      "dependencies": {'
                        '        "testpackage2": {"version": "1.2"}}}}}'
                    ),
                    expected_dependencies=["testpackage1=1.0", "testpackage2=1.2"],
                ),
            ),
            (
                "missing",
                dict(
                    ls_output=(
                        '{"dependencies": {'
                        '   "testpackage1": {"version": "1.0"},'
                        '   "testpackage2": {"version": "1.2"},'
                        '   "missing": {"noversion": "dummy"}}}'
                    ),
                    expected_dependencies=["testpackage1=1.0", "testpackage2=1.2"],
                ),
            ),
            ("none", dict(ls_output="{}", expected_dependencies=[])),
        ],
        [("npm", dict(package_manager="npm")), ("yarn", dict(package_manager="yarn"))],
    )

    def test_get_manifest_with_node_packages(self):
        self.run_output_mock.return_value = self.ls_output
        self.options.node_package_manager = self.package_manager

        plugin = nodejs.NodePlugin("test-part", self.options, self.project)

        self.create_assets(plugin)

        plugin.build()

        self.assertThat(
            plugin.get_manifest(),
            Equals(
                collections.OrderedDict({"node-packages": self.expected_dependencies})
            ),
        )


class NodePluginYarnLockManifestTest(NodePluginBaseTest):
    def test_get_manifest_with_yarn_lock_file(self):
        self.options.nodejs_package_manager = "yarn"
        plugin = nodejs.NodePlugin("test-part", self.options, self.project)

        self.create_assets(plugin)

        with open(os.path.join(plugin.builddir, "yarn.lock"), "w") as yarn_lock_file:
            yarn_lock_file.write("test yarn lock contents")

        plugin.build()

        expected_manifest = collections.OrderedDict()
        expected_manifest["yarn-lock-contents"] = "test yarn lock contents"
        expected_manifest["node-packages"] = []

        self.assertThat(plugin.get_manifest(), Equals(expected_manifest))


class NodeBinTest(unit.TestCase):
    scenarios = [
        (
            "dict",
            dict(
                package_json=dict(
                    name="package-foo",
                    bin=dict(run1="bin0/run1bin", run2="bin1/run2bin"),
                ),
                expected_bins=["run1", "run2"],
            ),
        ),
        (
            "single",
            dict(
                package_json=dict(name="package-foo", bin="bin0/run1bin"),
                expected_bins=["package-foo"],
            ),
        ),
        (
            "single, scoped package",
            dict(
                package_json=dict(name="@org/package-foo", bin="bin1/run1bin"),
                expected_bins=["package-foo"],
            ),
        ),
    ]

    def setUp(self):
        super().setUp()

        if type(self.package_json["bin"]) == dict:
            binaries = self.package_json["bin"].values()
        else:
            binaries = [self.package_json["bin"]]

        for binary in binaries:
            os.makedirs(os.path.dirname(binary), exist_ok=True)
            open(binary, "w").close()

    def test_bins(self):
        nodejs._create_bins(self.package_json, ".")
        binary_paths = (os.path.join("bin", b) for b in self.expected_bins)

        for binary in binary_paths:
            self.assertThat(binary, FileExists())


class NodeReleaseTest(unit.TestCase):
    scenarios = [
        (
            "amd64",
            dict(
                deb_arch="amd64",
                engine="4.4.4",
                expected_url=(
                    "https://nodejs.org/dist/v4.4.4/node-v4.4.4-linux-x64.tar.gz"
                ),
            ),
        ),
        (
            "i386",
            dict(
                deb_arch="i386",
                engine="4.4.4",
                expected_url=(
                    "https://nodejs.org/dist/v4.4.4/node-v4.4.4-linux-x86.tar.gz"
                ),
            ),
        ),
        (
            "armhf",
            dict(
                deb_arch="armhf",
                engine="4.4.4",
                expected_url=(
                    "https://nodejs.org/dist/v4.4.4/node-v4.4.4-linux-armv7l.tar.gz"
                ),
            ),
        ),
        (
            "aarch64",
            dict(
                deb_arch="arm64",
                engine="4.4.4",
                expected_url=(
                    "https://nodejs.org/dist/v4.4.4/node-v4.4.4-linux-arm64.tar.gz"
                ),
            ),
        ),
        (
            "s390x",
            dict(
                deb_arch="s390x",
                engine="4.4.4",
                expected_url=(
                    "https://nodejs.org/dist/v4.4.4/node-v4.4.4-linux-s390x.tar.gz"
                ),
            ),
        ),
    ]

    def test_get_nodejs_release(self):
        node_url = nodejs.get_nodejs_release(self.engine, self.deb_arch)
        self.assertThat(node_url, Equals(self.expected_url))


class NodePluginUnsupportedArchTest(NodePluginBaseTest):
    @mock.patch("snapcraft.project.Project.deb_arch", "ppcel64")
    def test_unsupported_arch_raises_exception(self):
        raised = self.assertRaises(
            errors.SnapcraftEnvironmentError,
            nodejs.NodePlugin,
            "test-part",
            self.options,
            self.project,
        )

        self.assertThat(
            raised.__str__(), Equals("architecture not supported (ppcel64)")
        )


class NodePluginMissingFilesTest(NodePluginBaseTest):

    scenarios = [
        ("npm", dict(package_manager="npm")),
        ("yarn", dict(package_manager="yarn")),
    ]

    def test_missing_package_json(self):
        plugin = nodejs.NodePlugin("test-part", self.options, self.project)

        self.create_assets(plugin, skip_package_json=True)

        self.assertRaises(nodejs.NodejsPluginMissingPackageJsonError, plugin.pull)
