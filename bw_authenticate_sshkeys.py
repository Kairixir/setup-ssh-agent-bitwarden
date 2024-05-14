#!/usr/bin/env python3

"""
Extracts passphrases for SSH private keys from Bitwarden vault
Then adds them to ssh-agent
"""

from typing import Dict
import csv
import pathlib
import config
import argparse
import json
import logging
import os
import subprocess

from importlib.metadata import version

# Use this constant to call `bw` in shell
# Necessary to fix `bw` deprecation warning for punycode 
# https://github.com/bitwarden/clients/issues/6689
BW_SHELL_CALL = "NODE_OPTIONS=\"--no-deprecation\" bw"


def memoize(func):
    """
    Decorator function to cache the results of another function call
    """
    cache = dict()

    def memoized_func(*args):
        if args in cache:
            return cache[args]
        result = func(*args)
        cache[args] = result
        return result

    return memoized_func


@memoize
def bwcli_version():
    """
    Function to return the version of the Bitwarden CLI
    """
    proc_version = subprocess.run(
        [f"{BW_SHELL_CALL} --version"],
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=True,
        shell=True
    )
    return proc_version.stdout


@memoize
def cli_supports(feature):
    """
    Function to return whether the current Bitwarden CLI supports a particular
    feature
    """
    version = version(bwcli_version())

    if feature == "nointeraction" and version >= version("1.9.0"):
        return True
    return False


def get_session():
    """
    Function to return a valid Bitwarden session
    """
    # Check for an existing, user-supplied Bitwarden session
    session = os.environ.get("BW_SESSION")
    if session is not None:
        logging.debug("Existing Bitwarden session found")
        return session

    # Check if we're already logged in
    proc_logged = subprocess.run(f"{BW_SHELL_CALL} login --check --quiet {config.EMAIL}", shell=True)

    if proc_logged.returncode:
        logging.debug("Not logged into Bitwarden")
        operation = "login"
    else:
        logging.debug("Bitwarden vault is locked")
        operation = "unlock"
    
    proc_session = subprocess.run(
        f"{BW_SHELL_CALL} --raw {operation}",
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=True,
        shell=True
    )
    return proc_session.stdout


def folder_items(session, folder_id):
    """
    Function to return items from a folder
    """
    logging.debug("Folder ID: %s" % folder_id)

    proc_items = subprocess.run(
        f"{BW_SHELL_CALL} list items --folderid {folder_id} --session {session}",
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=True,
        shell=True
    )
    return json.loads(proc_items.stdout)


def add_ssh_keys(session, items, itemid_path_pair: Dict[str, pathlib.Path]):
    """
    Add all possible keys with corresponding passphrases to ssh-add
    """
    for item in items:
        passphrase = item["login"]["password"]
        try:
            path = itemid_path_pair[item["id"]]
        except KeyError:
            print("Path for item %s not found" % item["name"])
            continue
        if passphrase is None:
            print("Passphrase not found for %s" % item["name"])
            continue
        if not path.exists():
            print("Private key at %s does not exist" % path)
            continue
        try:
            # sleep .3; echo testing; } | script -q /dev/null ssh-add testing_key
            subprocess.run(
                ["{ sleep .8; echo %s; } | script -q /dev/null ssh-add %s" % (passphrase, path)],
                universal_newlines=True,
                shell=True,
                check=True,
            )
        except subprocess.SubprocessError:
            logging.warning("Could not add key to the SSH agent")


def lock_bitwarden(session):
    """
    Lock Bitwarden after all is done
    """
    subprocess.run(
        f"{BW_SHELL_CALL} lock --session {session}",
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=True,
        shell=True
    )
    return None


if __name__ == "__main__":

    def parse_args():
        """
        Function to parse command line arguments
        """
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="show debug output",
        )

        return parser.parse_args()

    def main():
        """
        Main program logic
        """

        args = parse_args()

        if args.debug:
            loglevel = logging.DEBUG
        else:
            loglevel = logging.INFO

        logging.basicConfig(level=loglevel)

        itemid_path_pair = {}
        try:
            with open(config.ITEM_ID_KEY_MAPPING_CSV) as csv_file:
                reader = csv.reader(csv_file)
                for row in reader:
                    itemid_path_pair[row[0]] = pathlib.Path(row[1]).expanduser()
        except Exception:
            print("CSV file was not loaded correctly")
            exit()

        session = None

        try:
            logging.info("Getting Bitwarden session")
            session = get_session()
            logging.debug("Session = %s" % session)

            # Sync bw vault before retrieving keys
            subprocess.run(
                f"{BW_SHELL_CALL} sync --session {session}", stdout=subprocess.PIPE, universal_newlines=True, check=True, shell=True
            )

            logging.info("Getting folder items")
            items = folder_items(session, config.FOLDER_ID)

            logging.info("Attempting to add keys to ssh-agent")
            add_ssh_keys(session, items, itemid_path_pair)

        except subprocess.CalledProcessError as e:
            if e.stderr:
                logging.error("`%s` error: %s" % (e.cmd[0], e.stderr))
            logging.debug("Error running %s" % e.cmd)
        finally:
            if session:
                lock_bitwarden(session)

    main()
