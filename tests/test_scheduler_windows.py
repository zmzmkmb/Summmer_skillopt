import os
import sys
import unittest
from unittest import mock

class TestSchedulerWindows(unittest.TestCase):
    @mock.patch("sys.platform", "win32")
    @mock.patch("shutil.which", return_value="C:\\Windows\\System32\\schtasks.exe")
    def test_schedule_windows(self, mock_which):
        from skillopt_sleep.scheduler import schedule
        
        calls = []
        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            class Proc:
                returncode = 0
                stdout = "SUCCESS: The scheduled task ... has successfully been created."
                stderr = ""
            return Proc()
            
        with mock.patch("subprocess.run", side_effect=fake_run):
            ok, msg = schedule("/p/my project", backend="mock", hour=3, minute=17)
            self.assertTrue(ok)
            self.assertIn("via Windows Task Scheduler", msg)
            self.assertEqual(len(calls), 1)
            cmd = calls[0]
            self.assertEqual(cmd[0], "schtasks")
            self.assertEqual(cmd[1], "/create")
            self.assertEqual(cmd[2], "/tn")
            self.assertTrue(cmd[3].startswith("SkillOpt-Sleep-"))
            self.assertIn("my_project", cmd[3])
            self.assertEqual(cmd[4], "/tr")
            self.assertIn("cmd.exe", cmd[5])
            self.assertEqual(cmd[6], "/sc")
            self.assertEqual(cmd[7], "daily")
            self.assertEqual(cmd[8], "/st")
            self.assertEqual(cmd[9], "03:17")
            self.assertEqual(cmd[10], "/f")

    @mock.patch("sys.platform", "win32")
    @mock.patch("shutil.which", return_value="C:\\Windows\\System32\\schtasks.exe")
    def test_unschedule_windows(self, mock_which):
        from skillopt_sleep.scheduler import unschedule
        
        calls = []
        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            class Proc:
                returncode = 0
                stdout = "SUCCESS: The scheduled task ... was successfully deleted."
                stderr = ""
            return Proc()
            
        with mock.patch("subprocess.run", side_effect=fake_run):
            ok, msg = unschedule("/p/my project")
            self.assertTrue(ok)
            self.assertEqual(len(calls), 1)
            cmd = calls[0]
            self.assertEqual(cmd[0], "schtasks")
            self.assertEqual(cmd[1], "/delete")
            self.assertEqual(cmd[2], "/tn")
            self.assertTrue(cmd[3].startswith("SkillOpt-Sleep-"))
            self.assertEqual(cmd[4], "/f")
