#!/usr/bin/env python3
"""
Tests for opening the SMS app with termux-am, and falling back to plain am.

subprocess.run is mocked, so nothing is actually opened.

Run with:
    ./venv/bin/python -m unittest discover tests -v
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils import sms_handler  # noqa: E402


def finished(returncode=0, stdout='', stderr=''):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class TestOpeningTheSmsApp(unittest.TestCase):

    def run_with(self, *outcomes):
        """Open a message with subprocess.run giving these results in turn"""
        with mock.patch.object(sms_handler.subprocess, 'run',
                               side_effect=list(outcomes)) as run:
            ok = sms_handler._open_with_termux_am('555-0001', 'Hi')
        commands = [Path(c.args[0][0]).name for c in run.call_args_list]
        return ok, commands

    def test_termux_am_alone_when_it_works(self):
        self.assertEqual(self.run_with(finished()), (True, ['termux-am']))

    def test_no_socket_falls_back_to_am(self):
        ok, commands = self.run_with(
            finished(1, stderr='Could not connect to socket: No such file or directory'),
            finished())
        self.assertEqual((ok, commands), (True, ['termux-am', 'am']))

    def test_a_disabled_server_falls_back_to_am(self):
        ok, commands = self.run_with(
            finished(1, stderr='TermuxAm server is not enabled.'), finished())
        self.assertEqual((ok, commands), (True, ['termux-am', 'am']))

    def test_a_missing_termux_am_falls_back_to_am(self):
        ok, commands = self.run_with(FileNotFoundError('termux-am'), finished())
        self.assertEqual((ok, commands), (True, ['termux-am', 'am']))

    def test_a_timeout_is_not_retried(self):
        # The intent may already have fired - a retry could open it twice
        ok, commands = self.run_with(subprocess.TimeoutExpired('termux-am', 15))
        self.assertEqual((ok, commands), (False, ['termux-am']))

    def test_an_error_from_am_itself_is_not_retried(self):
        ok, commands = self.run_with(
            finished(0, stdout='Error: Activity not started, unable to resolve Intent'))
        self.assertEqual((ok, commands), (False, ['termux-am']))

    def test_both_failing_is_a_failure(self):
        ok, commands = self.run_with(
            finished(1, stderr='Could not connect to socket'),
            finished(1, stderr='Error: something'))
        self.assertEqual((ok, commands), (False, ['termux-am', 'am']))


if __name__ == '__main__':
    unittest.main()
