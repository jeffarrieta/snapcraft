# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2018 Canonical Ltd
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

import subprocess
from collections import OrderedDict
from unittest import mock

from testtools.matchers import Equals

from snapcraft.internal.build_providers import errors
from snapcraft.internal.build_providers._multipass import MultipassCommand
from tests import unit


class MultipassCommandBaseTest(unit.TestCase):
    def setUp(self):
        super().setUp()

        patcher = mock.patch("signal.signal")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch("shutil.which", return_value=["multipass"])
        self.which_mock = patcher.start()
        self.addCleanup(patcher.stop)


class MultipassCommandGeneralTest(MultipassCommandBaseTest):
    def test_provider_name(self):
        self.assertThat(MultipassCommand.provider_name, Equals("multipass"))

    def test_multipass_command_missing_raises(self):
        self.which_mock.return_value = []

        self.assertRaises(errors.ProviderNotFound, MultipassCommand, platform="linux")

    def test_ensure_multipass_on_command_found(self):
        self.which_mock.return_value = ["multipass"]

        MultipassCommand.ensure_multipass(platform="linux")


class MultipassCommandEnsureMultipassErrorsTest(MultipassCommandBaseTest):
    scenarios = (
        ("linux", dict(platform="linux", prompt_installable=True, snap_which=True)),
        ("linux not snap", dict(platform="linux", prompt_installable=False)),
        ("darwin", dict(platform="darwin", prompt_installable=True)),
        ("unknown", dict(platform="unknown", prompt_installable=False)),
    )

    def setUp(self):
        super().setUp()

        def which_effect(command: str):
            if command != "snap":
                return

            try:
                if self.snap_which:
                    return ["snap"]
            except AttributeError:
                return []

        self.which_mock.side_effect = which_effect

    def test_ensure_multipass_raises(self):
        raised = self.assertRaises(
            errors.ProviderNotFound,
            MultipassCommand.ensure_multipass,
            platform=self.platform,
        )
        self.assertThat(raised.prompt_installable, Equals(self.prompt_installable))


class MultipassCommandSetupMultipassTest(MultipassCommandBaseTest):
    def setUp(self):
        super().setUp()

        patcher = mock.patch("time.sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

        def check_output_effect(*args, **kwargs):
            if args[0] == ["multipass", "version"]:
                return b"multipassd"

        patcher = mock.patch("subprocess.check_call")
        self.check_call_mock = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch("subprocess.check_output")
        self.check_output_mock = patcher.start()
        self.check_output_mock.side_effect = check_output_effect
        self.addCleanup(patcher.stop)

        self.echoer_mock = mock.Mock()

    def test_linux(self):
        self.fake_snapd.snaps_result = [
            dict(name="multipass", channel="beta", revision="10")
        ]
        self.fake_snapd.find_result = [
            dict(multipass=dict(channels={"latest/beta": dict(confinement="classic")}))
        ]
        MultipassCommand.setup_multipass(platform="linux", echoer=self.echoer_mock)

        self.echoer_mock.wrapped.assert_called_once_with("Waiting for multipass...")

    def test_darwin(self):
        MultipassCommand.setup_multipass(platform="darwin", echoer=self.echoer_mock)

        self.check_call_mock.assert_called_once_with(
            ["brew", "cask", "install", "multipass"]
        )
        self.echoer_mock.wrapped.assert_called_once_with("Waiting for multipass...")

    def test_unkown_platform_raises(self):
        self.assertRaises(
            EnvironmentError,
            MultipassCommand.setup_multipass,
            platform="unknown",
            echoer=self.echoer_mock,
        )

        self.echoer_mock.wrapped.assert_not_called()


class MultipassCommandPassthroughBaseTest(MultipassCommandBaseTest):
    def setUp(self):
        super().setUp()

        patcher = mock.patch("subprocess.check_call")
        self.check_call_mock = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch("subprocess.check_output")
        self.check_output_mock = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch("subprocess.Popen")
        self.popen_mock = patcher.start()
        self.popen_mock().communicate.return_value = (b"", b"error")
        self.popen_mock().returncode = 0
        self.addCleanup(patcher.stop)

        self.multipass_command = MultipassCommand(platform="linux")
        self.instance_name = "stub-instance"


class MultipassCommandLaunchTest(MultipassCommandPassthroughBaseTest):
    def test_launch(self):
        self.multipass_command.launch(instance_name=self.instance_name, image="16.04")

        self.check_call_mock.assert_called_once_with(
            ["multipass", "launch", "16.04", "--name", self.instance_name],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_launch_with_cpus(self):
        self.multipass_command.launch(
            instance_name=self.instance_name, cpus="10", image="16.04"
        )

        self.check_call_mock.assert_called_once_with(
            [
                "multipass",
                "launch",
                "16.04",
                "--name",
                self.instance_name,
                "--cpus",
                "10",
            ],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_launch_with_mem(self):
        self.multipass_command.launch(
            instance_name=self.instance_name, mem="2G", image="16.04"
        )

        self.check_call_mock.assert_called_once_with(
            [
                "multipass",
                "launch",
                "16.04",
                "--name",
                self.instance_name,
                "--mem",
                "2G",
            ],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_launch_with_disk(self):
        self.multipass_command.launch(
            instance_name=self.instance_name, disk="8G", image="16.04"
        )

        self.check_call_mock.assert_called_once_with(
            [
                "multipass",
                "launch",
                "16.04",
                "--name",
                self.instance_name,
                "--disk",
                "8G",
            ],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_launch_with_remote(self):
        self.multipass_command.launch(
            instance_name=self.instance_name, image="18.04", remote="daily"
        )

        self.check_call_mock.assert_called_once_with(
            ["multipass", "launch", "daily:18.04", "--name", self.instance_name],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_launch_fails(self):
        # multipass can fail due to several reasons and will display the error
        # right above this exception message, it looks something like:
        #
        #   Creating a build environment named 'nonfilterable-mayola'
        #   failed to launch: failed to obtain exit status for remote process
        #   An error occurred when trying to launch the instance with 'multipass'.  # noqa: E501
        cmd = ["multipass", "launch", "18.04", "--name", self.instance_name]
        self.check_call_mock.side_effect = subprocess.CalledProcessError(1, cmd)

        self.assertRaises(
            errors.ProviderLaunchError,
            self.multipass_command.launch,
            instance_name=self.instance_name,
            image="18.04",
        )
        self.check_call_mock.assert_called_once_with(cmd, stdin=subprocess.DEVNULL)
        self.check_output_mock.assert_not_called()


class MultipassCommandShellTest(MultipassCommandPassthroughBaseTest):
    def test_shell(self):
        self.multipass_command.shell(instance_name=self.instance_name)

        self.check_call_mock.assert_called_once_with(
            ["multipass", "shell", self.instance_name], stdin=None
        )
        self.check_output_mock.assert_not_called()

    def test_shell_fails(self):
        # multipass can fail due to several reasons and will display the error
        # right above this exception message.
        cmd = ["multipass", "shell", self.instance_name]
        self.check_call_mock.side_effect = subprocess.CalledProcessError(1, cmd)

        self.assertRaises(
            errors.ProviderShellError,
            self.multipass_command.shell,
            instance_name=self.instance_name,
        )
        self.check_call_mock.assert_called_once_with(cmd, stdin=None)
        self.check_output_mock.assert_not_called()


class MultipassCommandStopTest(MultipassCommandPassthroughBaseTest):
    def test_stop(self):
        self.multipass_command.stop(instance_name=self.instance_name)

        self.check_call_mock.assert_called_once_with(
            ["multipass", "stop", self.instance_name], stdin=subprocess.DEVNULL
        )
        self.check_output_mock.assert_not_called()

    def test_stop_time(self):
        self.multipass_command.stop(instance_name=self.instance_name, time=10)

        self.check_call_mock.assert_called_once_with(
            ["multipass", "stop", "--time", "10", self.instance_name],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_stop_fails(self):
        # multipass can fail due to several reasons and will display the error
        # right above this exception message.
        cmd = ["multipass", "stop", self.instance_name]
        self.check_call_mock.side_effect = subprocess.CalledProcessError(1, cmd)

        self.assertRaises(
            errors.ProviderStopError,
            self.multipass_command.stop,
            instance_name=self.instance_name,
        )
        self.check_call_mock.assert_called_once_with(cmd, stdin=subprocess.DEVNULL)
        self.check_output_mock.assert_not_called()


class MultipassCommandDeleteTest(MultipassCommandPassthroughBaseTest):
    def test_delete_implicit_purge(self):
        self.multipass_command.delete(instance_name=self.instance_name)

        self.check_call_mock.assert_called_once_with(
            ["multipass", "delete", self.instance_name, "--purge"],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_delete_no_purge(self):
        self.multipass_command.delete(instance_name=self.instance_name, purge=False)

        self.check_call_mock.assert_called_once_with(
            ["multipass", "delete", self.instance_name], stdin=subprocess.DEVNULL
        )
        self.check_output_mock.assert_not_called()

    def test_delete_fails(self):
        # multipass can fail due to several reasons and will display the error
        # right above this exception message.
        cmd = ["multipass", "delete", self.instance_name, "--purge"]
        self.check_call_mock.side_effect = subprocess.CalledProcessError(1, cmd)

        self.assertRaises(
            errors.ProviderDeleteError,
            self.multipass_command.delete,
            instance_name=self.instance_name,
        )
        self.check_call_mock.assert_called_once_with(cmd, stdin=subprocess.DEVNULL)
        self.check_output_mock.assert_not_called()


class MultipassCommandMountTest(MultipassCommandPassthroughBaseTest):
    def test_mount(self):
        source = "mountpath"
        target = "{}/mountpoint".format(self.instance_name)
        self.multipass_command.mount(source=source, target=target)

        self.check_call_mock.assert_called_once_with(
            ["multipass", "mount", source, target], stdin=subprocess.DEVNULL
        )
        self.check_output_mock.assert_not_called()

    def test_mount_uid(self):
        source = "mountpath"
        target = "{}/mountpoint".format(self.instance_name)
        self.multipass_command.mount(
            source=source,
            target=target,
            uid_map=OrderedDict([("1000", "0"), ("900", "0")]),
        )

        self.check_call_mock.assert_called_once_with(
            [
                "multipass",
                "mount",
                source,
                target,
                "--uid-map",
                "1000:0",
                "--uid-map",
                "900:0",
            ],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_mount_gid(self):
        source = "mountpath"
        target = "{}/mountpoint".format(self.instance_name)
        self.multipass_command.mount(
            source=source,
            target=target,
            gid_map=OrderedDict([("1000", "0"), ("900", "0")]),
        )

        self.check_call_mock.assert_called_once_with(
            [
                "multipass",
                "mount",
                source,
                target,
                "--gid-map",
                "1000:0",
                "--gid-map",
                "900:0",
            ],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_mount_uid_and_gid(self):
        source = "mountpath"
        target = "{}/mountpoint".format(self.instance_name)
        self.multipass_command.mount(
            source=source,
            target=target,
            uid_map=OrderedDict([("1000", "0"), ("900", "1")]),
            gid_map=OrderedDict([("1000", "0"), ("900", "2")]),
        )

        self.check_call_mock.assert_called_once_with(
            [
                "multipass",
                "mount",
                source,
                target,
                "--uid-map",
                "1000:0",
                "--uid-map",
                "900:1",
                "--gid-map",
                "1000:0",
                "--gid-map",
                "900:2",
            ],
            stdin=subprocess.DEVNULL,
        )
        self.check_output_mock.assert_not_called()

    def test_mount_fails(self):
        source = "mountpath"
        target = "{}/mountpoint".format(self.instance_name)
        cmd = ["multipass", "mount", source, target]
        self.check_call_mock.side_effect = subprocess.CalledProcessError(1, cmd)

        self.assertRaises(
            errors.ProviderMountError,
            self.multipass_command.mount,
            source=source,
            target=target,
        )
        self.check_call_mock.assert_called_once_with(cmd, stdin=subprocess.DEVNULL)
        self.check_output_mock.assert_not_called()


class MultipassCommandCopyFilesTest(MultipassCommandPassthroughBaseTest):
    def test_copy_files(self):
        source = "source-file"
        destination = "{}/destination-file".format(self.instance_name)
        self.multipass_command.copy_files(source=source, destination=destination)

        self.check_call_mock.assert_called_once_with(
            ["multipass", "copy-files", source, destination], stdin=subprocess.DEVNULL
        )
        self.check_output_mock.assert_not_called()

    def test_copy_files_fails(self):
        # multipass can fail due to several reasons and will display the error
        # right above this exception message.
        source = "source-file"
        destination = "destination-file"
        cmd = ["multipass", "copy-files", source, destination]
        self.check_call_mock.side_effect = subprocess.CalledProcessError(1, cmd)

        self.assertRaises(
            errors.ProviderFileCopyError,
            self.multipass_command.copy_files,
            source=source,
            destination=destination,
        )
        self.check_call_mock.assert_called_once_with(cmd, stdin=subprocess.DEVNULL)
        self.check_output_mock.assert_not_called()


class MultipassCommandInfoTest(MultipassCommandPassthroughBaseTest):
    def test_info(self):
        self.multipass_command.info(instance_name=self.instance_name)

        self.popen_mock.assert_has_calls(
            [
                mock.call(
                    ["multipass", "info", self.instance_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            ]
        )
        self.check_output_mock.assert_not_called()
        self.check_call_mock.assert_not_called()

    def test_info_with_format(self):
        self.multipass_command.info(
            instance_name=self.instance_name, output_format="json"
        )

        self.popen_mock.assert_has_calls(
            [
                mock.call(
                    ["multipass", "info", self.instance_name, "--format", "json"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            ]
        )
        self.check_output_mock.assert_not_called()
        self.check_call_mock.assert_not_called()

    def test_info_fails(self):
        self.popen_mock().returncode = 1

        self.assertRaises(
            errors.ProviderInfoError,
            self.multipass_command.info,
            instance_name=self.instance_name,
        )
        self.popen_mock.assert_has_calls(
            [
                mock.call(
                    ["multipass", "info", self.instance_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            ]
        )
        self.check_output_mock.assert_not_called()
        self.check_call_mock.assert_not_called()
