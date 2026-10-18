#!/usr/bin/env python3
"""
Tests for opening the SMS app with Termux's am.

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

    def run_with(self, outcome):
        """Open a message with subprocess.run giving this result"""
        with mock.patch.object(sms_handler.subprocess, 'run',
                               side_effect=[outcome]) as run:
            ok = sms_handler._open_with_am('555-0001', 'Hi there')
        return ok, run.call_args.args[0]

    def test_it_fires_sendto_with_the_number_and_message(self):
        ok, cmd = self.run_with(finished())
        self.assertTrue(ok)
        self.assertEqual(cmd, [sms_handler.TERMUX_AM, 'start',
                               '-a', 'android.intent.action.SENDTO',
                               '-d', 'smsto:555-0001',
                               '--es', 'sms_body', 'Hi there'])

    def test_a_failed_exit_is_a_failure(self):
        self.assertFalse(self.run_with(finished(1, stderr='boom'))[0])

    def test_an_error_with_a_zero_exit_is_a_failure(self):
        ok, _ = self.run_with(
            finished(0, stdout='Error: Activity not started, unable to resolve Intent'))
        self.assertFalse(ok)

    def test_a_missing_am_is_a_failure(self):
        self.assertFalse(self.run_with(FileNotFoundError('am'))[0])

    def test_a_timeout_is_a_failure(self):
        self.assertFalse(self.run_with(subprocess.TimeoutExpired('am', 15))[0])


if __name__ == '__main__':
    unittest.main()
