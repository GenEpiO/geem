#!/usr/bin/python

"""Tests scripts/geem_package_handler."""

import argparse
import filecmp
import io
import os
import subprocess
import time
import unittest
from unittest.mock import patch

import scripts.geem_package_handler as gph


class TestPackageHandling(unittest.TestCase):
    """Test backup, delete and insert functionality."""

    @classmethod
    def setUpClass(cls):
        # Mimic geem_package_handler working directory
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        os.chdir(os.path.abspath("../../scripts"))

        # Mimic creation of parser in geem_package_handler
        cls.parser = gph.create_parser()

        # Relative path to docker-compose.test.yml
        cls.test_yml = "../docker-compose.test.yml"

        # Stop and remove default docker services
        subprocess.call("docker-compose down", shell=True)
        # Provide enough time to stop and remove default services
        time.sleep(10)

        # Command that raises an error if service %s is not running.
        check_container = "docker-compose exec -T %s echo 'test'"

        # Make sure geem_db_1 is no longer running
        try:
            subprocess.check_call(check_container % "db", shell=True)
            # Should not reach here, unless db is still running
            raise RuntimeError("Unable to stop and remove db service.")
        except subprocess.CalledProcessError:
            pass

        # Make sure geem_web_1 is no longer running
        try:
            subprocess.check_call(check_container % "web", shell=True)
            # Should not reach here, unless web is still running
            raise RuntimeError("Unable to stop and remove web service.")
        except subprocess.CalledProcessError:
            pass

        # Setup test "db" service
        run_command = "run web python /code/manage.py"
        subprocess.call("docker-compose -f %s %s makemigrations --noinput"
                        % (cls.test_yml, run_command), shell=True)
        subprocess.call("docker-compose -f %s %s migrate --noinput"
                        % (cls.test_yml, run_command), shell=True)
        subprocess.call("docker-compose -f %s %s loaddata sys_admin"
                        % (cls.test_yml, run_command), shell=True)

    @classmethod
    def tearDownClass(cls):
        # Stop and remove test "db" service
        subprocess.call("docker-compose -f %s down  --volumes --remove-orphans"
                        % cls.test_yml, shell=True)
        # Remove geem_package backups generated from testing
        actual_output_path = "../geem_package_backups/actual_output.tsv"
        os.remove(os.path.abspath(actual_output_path))
        # Change working directory back
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

    def setUp(self):
        # Add test packages
        run_command = "run web python /code/manage.py"
        subprocess.call("docker-compose -f %s %s loaddata test_packages"
                        % (self.test_yml, run_command), shell=True)
        # Next geem_package id in sequence is 4
        gph.sync_geem_package_id_seq()

    def tearDown(self):
        # Empty geem_package
        tear_down_command = gph.docker_command("truncate table geem_package")
        subprocess.call(tear_down_command, shell=True)
        # Next geem_package id in sequence is 1
        gph.sync_geem_package_id_seq()

    @staticmethod
    def compare_backups(actual_backup, expected_backup):
        """Compare actual and expected geem_package backups.

        More specifically, compares "actual" file from
        geem_package_backups with "expected" file from
        tests.test_geem_package_backups. Extension must not be
        specified in actual_backup and expected_backup.

        :param str actual_backup: File name of "actual" file
        :param str expected_backup: File name of "expected" file
        :raises AssertionError: If actual_backup and expected_backup
                                contents are different
        """
        are_same = filecmp.cmp("../geem_package_backups/%s.tsv"
                               % actual_backup,
                               "../tests/test_geem_package_backups/%s.tsv"
                               % expected_backup)
        if are_same is not True:
            raise AssertionError("%s and %s are different"
                                 % (actual_backup, expected_backup))

    def test_backup_all_packages(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "all_test_packages")

    def test_backup_one_package(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output",
                                                    "-p", "3"]))
        self.compare_backups("actual_output", "two_deleted_packages")

    def test_backup_two_packages(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output",
                                                    "-p", "2", "3"]))
        self.compare_backups("actual_output", "one_deleted_package")

    def test_delete_all_packages(self):
        gph.delete_packages(self.parser.parse_args(["delete"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "no_packages")

    def test_delete_one_package(self):
        gph.delete_packages(self.parser.parse_args(["delete", "-p", "1"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "one_deleted_package")

    def test_delete_two_packages(self):
        gph.delete_packages(self.parser.parse_args(["delete", "-p", "1", "2"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "two_deleted_packages")

    def test_insert_all_packages(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "three_inserted_packages")

    def test_insert_one_package(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-p", "1"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "one_inserted_package")

    def test_insert_two_packages(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-p", "1", "2"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "two_inserted_packages")

    def test_insert_all_packages_keep_ids(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.delete_packages(self.parser.parse_args(["delete"]))
        # geem_package id sequence not synchronized, so the next
        # insertions would have id's of 4, 5 and 6 without the "-k"
        # flag.
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-k"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "all_test_packages")

    def test_insert_all_packages_new_null_owner_id(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-n"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output",
                             "three_inserted_packages_null_owner_ids")

    def test_insert_all_packages_new_owner_id(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-n"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output",
                                                    "-p", "4", "5", "6"]))
        gph.delete_packages(self.parser.parse_args(["delete",
                                                    "-p", "4", "5", "6"]))
        gph.sync_geem_package_id_seq()
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-n", "1"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "three_inserted_packages")

    def test_insert_two_packages_keep_ids(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.delete_packages(self.parser.parse_args(["delete", "-p", "2", "3"]))
        # geem_package id sequence not synchronized, so the next
        # insertions would have id's of 4 and 5 without the "-k" flag.
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-k",
                                                    "-p", "2", "3"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output", "all_test_packages")

    def test_insert_two_packages_new_owner_id(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-n",
                                                    "-p", "1", "2"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output",
                             "two_inserted_packages_null_owner_ids")

    def test_insert_two_packages_keep_ids_new_owner_id(self):
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-p", "1", "2"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        gph.delete_packages(self.parser.parse_args(["delete", "-p", "4", "5"]))
        # geem_package id sequence not synchronized, so the next
        # insertions would have id's of 6 and 7 without the "-k" flag.
        gph.insert_packages(self.parser.parse_args(["insert",
                                                    "actual_output",
                                                    "-k",
                                                    "-n",
                                                    "-p", "4", "5"]))
        gph.backup_packages(self.parser.parse_args(["backup",
                                                    "actual_output"]))
        self.compare_backups("actual_output",
                             "two_inserted_packages_null_owner_ids")


class TestHelpers(unittest.TestCase):
    """Test helper methods."""

    def test_docker_command(self):
        self.assertEqual(gph.docker_command(""), 'docker-compose exec -T db '
                                                 'psql --username postgres '
                                                 '--dbname postgres '
                                                 '--command ""')
        self.assertEqual(gph.docker_command(" "), 'docker-compose exec -T db '
                                                  'psql --username postgres '
                                                  '--dbname postgres '
                                                  '--command " "')
        self.assertEqual(gph.docker_command("a"), 'docker-compose exec -T db '
                                                  'psql --username postgres '
                                                  '--dbname postgres '
                                                  '--command "a"')
        self.assertEqual(gph.docker_command("ab"), 'docker-compose exec -T db '
                                                   'psql --username postgres '
                                                   '--dbname postgres '
                                                   '--command "ab"')

    def test_psqlize_int_list(self):
        self.assertEqual(gph.psqlize_int_list([]), "()")
        self.assertEqual(gph.psqlize_int_list([1]), "(1)")
        self.assertEqual(gph.psqlize_int_list([1, 2, 3]), "(1,2,3)")

    def test_valid_owner_id(self):
        self.assertEqual(gph.valid_owner_id("null"), "null")
        self.assertEqual(gph.valid_owner_id("NULL"), "null")
        self.assertEqual(gph.valid_owner_id("nUlL"), "null")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_owner_id("null ")

        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_owner_id("")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_owner_id(" ")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_owner_id("a")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_owner_id("@")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_owner_id("a4")

        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_owner_id("0")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_owner_id("-1")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_owner_id("-2")
        self.assertEqual("1", "1")
        self.assertEqual("2", "2")

    def test_valid_tsv_file_name(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name("")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name(".tsv")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name(r"\ ")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name(r"\ .tsv")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name("@#")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name("@#.tsv")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name("a@")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name("a@.tsv")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name(".tsv.tsv")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name("a.csv")
        with self.assertRaises(argparse.ArgumentTypeError):
            gph.valid_tsv_file_name("a.tsv.tsv")

        self.assertEqual(gph.valid_tsv_file_name("a"), "a.tsv")
        self.assertEqual(gph.valid_tsv_file_name("a.tsv"), "a.tsv")
        self.assertEqual(gph.valid_tsv_file_name("a_"), "a_.tsv")
        self.assertEqual(gph.valid_tsv_file_name("a_.tsv"), "a_.tsv")
        self.assertEqual(gph.valid_tsv_file_name("tsv.tsv"), "tsv.tsv")
        self.assertEqual(gph.valid_tsv_file_name("tsv.tsv"), "tsv.tsv")


class TestArgParser(unittest.TestCase):
    """Test parsing of user-inputted command-line arguments."""

    @classmethod
    def setUpClass(cls):
        # Mimic creation of parser in geem_package_handler
        cls.parser = gph.create_parser()

    @patch("sys.stderr", new_callable=io.StringIO)
    def test_no_supplied_subparser(self, mock_stderr):
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"the following arguments are required: "
                                 r"{backup,delete,insert}")

    @patch("sys.stderr", new_callable=io.StringIO)
    def test_backup(self, mock_stderr):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["backup"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"the following arguments are required: "
                                 r"file_name")
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["backup", "###"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"###.tsv is not a valid file name")
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["backup", "a", "-p"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"argument -p/--packages: expected at least "
                                 r"one argument")
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["backup", "a", "-p", "a"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"argument -p/--packages: invalid int value")

        try:
            self.parser.parse_args(["backup", "a"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["backup", "a", "-p", "1"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["backup", "a", "-p", "1", "2"])
        except:
            self.fail("Unexpected SystemExit")

        actual_args = self.parser.parse_args(["backup", "a"])
        actual_args = vars(actual_args)
        expected_args = {
            "file_name": "a.tsv",
            "packages": None,
            "func": gph.backup_packages,
            "{backup,delete,insert}": "backup"
        }
        self.assertDictEqual(actual_args, expected_args)

        actual_args = self.parser.parse_args(["backup", "a", "-p", "1", "2"])
        actual_args = vars(actual_args)
        expected_args = {
            "file_name": "a.tsv",
            "packages": [1, 2],
            "func": gph.backup_packages,
            "{backup,delete,insert}": "backup"
        }
        self.assertDictEqual(actual_args, expected_args)

    @patch("sys.stderr", new_callable=io.StringIO)
    def test_delete(self, mock_stderr):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["delete", "-p"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"argument -p/--packages: expected at least "
                                 r"one argument")
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["delete", "-p", "a"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"argument -p/--packages: invalid int value")

        try:
            self.parser.parse_args(["delete"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["delete", "-p", "1"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["delete", "-p", "1", "2"])
        except:
            self.fail("Unexpected SystemExit")

        actual_args = self.parser.parse_args(["delete"])
        actual_args = vars(actual_args)
        expected_args = {
            "packages": None,
            "func": gph.delete_packages,
            "{backup,delete,insert}": "delete"
        }
        self.assertDictEqual(actual_args, expected_args)

        actual_args = self.parser.parse_args(["delete", "-p", "1", "2"])
        actual_args = vars(actual_args)
        expected_args = {
            "packages": [1, 2],
            "func": gph.delete_packages,
            "{backup,delete,insert}": "delete"
        }
        self.assertDictEqual(actual_args, expected_args)

    @patch("sys.stderr", new_callable=io.StringIO)
    def test_insert(self, mock_stderr):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["insert"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"the following arguments are required: "
                                 r"file_name")
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["insert", "a", "-k", "b"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"unrecognized arguments: b")
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["insert", "a", "-n", "c"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"argument -n/--new_owner_ids: must be a "
                                 r"natural number")
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["insert", "a", "-n", "0"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"argument -n/--new_owner_ids: must be a "
                                 r"natural number")
        # with self.assertRaises(SystemExit):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["insert", "a", "-n", "-1"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"argument -n/--new_owner_ids: must be a "
                                 r"natural number")
        # with self.assertRaises(SystemExit):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["insert", "a", "-n", "-10"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"argument -n/--new_owner_ids: must be a "
                                 r"natural number")
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["insert", "a", "-p", "a"])
        self.assertRegexpMatches(mock_stderr.getvalue(),
                                 r"argument -p/--packages: invalid int value")

        try:
            self.parser.parse_args(["insert", "a"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["insert", "a", "-k"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["insert", "a", "-n"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["insert", "a", "-n", "1"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["insert", "a", "-n", "10"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["insert", "a", "-k", "-n", "1"])
        except:
            self.fail("Unexpected SystemExit")
        try:
            self.parser.parse_args(["insert", "a", "-k", "-n", "10"])
        except:
            self.fail("Unexpected SystemExit")

        actual_args = self.parser.parse_args(["insert", "a"])
        actual_args = vars(actual_args)
        expected_args = {
            "file_name": "a.tsv",
            "keep_ids": False,
            "new_owner_ids": None,
            "packages": None,
            "func": gph.insert_packages,
            "{backup,delete,insert}": "insert"
        }
        self.assertDictEqual(actual_args, expected_args)

        actual_args = self.parser.parse_args(["insert", "a", "-k"])
        actual_args = vars(actual_args)
        expected_args = {
            "file_name": "a.tsv",
            "keep_ids": True,
            "new_owner_ids": None,
            "packages": None,
            "func": gph.insert_packages,
            "{backup,delete,insert}": "insert"
        }
        self.assertDictEqual(actual_args, expected_args)

        actual_args = self.parser.parse_args(["insert", "a", "-n"])
        actual_args = vars(actual_args)
        expected_args = {
            "file_name": "a.tsv",
            "keep_ids": False,
            "new_owner_ids": "null",
            "packages": None,
            "func": gph.insert_packages,
            "{backup,delete,insert}": "insert"
        }
        self.assertDictEqual(actual_args, expected_args)

        actual_args = self.parser.parse_args(["insert", "a", "-n", "10"])
        actual_args = vars(actual_args)
        expected_args = {
            "file_name": "a.tsv",
            "keep_ids": False,
            "new_owner_ids": "10",
            "packages": None,
            "func": gph.insert_packages,
            "{backup,delete,insert}": "insert"
        }
        self.assertDictEqual(actual_args, expected_args)

        actual_args = self.parser.parse_args(["insert", "a", "-k", "-n"])
        actual_args = vars(actual_args)
        expected_args = {
            "file_name": "a.tsv",
            "keep_ids": True,
            "new_owner_ids": "null",
            "packages": None,
            "func": gph.insert_packages,
            "{backup,delete,insert}": "insert"
        }
        self.assertDictEqual(actual_args, expected_args)

        actual_args = self.parser.parse_args(["insert", "a", "-k", "-n", "10"])
        actual_args = vars(actual_args)
        expected_args = {
            "file_name": "a.tsv",
            "keep_ids": True,
            "new_owner_ids": "10",
            "packages": None,
            "func": gph.insert_packages,
            "{backup,delete,insert}": "insert"
        }
        self.assertDictEqual(actual_args, expected_args)


if __name__ == '__main__':
    # Change current working directory to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    unittest.main()
