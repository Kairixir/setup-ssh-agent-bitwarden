#!/usr/bin/env python3
"""
Extracts SSH keys from Bitwarden vault
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

from pkg_resources import parse_version


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
        ['bw', '--version'],
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    )
    return proc_version.stdout


@memoize
def cli_supports(feature):
    """
    Function to return whether the current Bitwarden CLI supports a particular
    feature
    """
    version = parse_version(bwcli_version())

    if feature == 'nointeraction' and version >= parse_version('1.9.0'):
        return True
    return False


def get_session():
    """
    Function to return a valid Bitwarden session
    """
    # Check for an existing, user-supplied Bitwarden session
    session = os.environ.get('BW_SESSION')
    if session is not None:
        logging.debug('Existing Bitwarden session found')
        return session

    # Check if we're already logged in
    proc_logged = subprocess.run(['bw', 'login', '--check', '--quiet'])

    if proc_logged.returncode:
        logging.debug('Not logged into Bitwarden')
        operation = 'login'
    else:
        logging.debug('Bitwarden vault is locked')
        operation = 'unlock'

    proc_session = subprocess.run(
        ['bw', '--raw', operation],
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    )
    return proc_session.stdout


def folder_items(session, folder_id):
    """
    Function to return items from a folder
    """
    logging.debug('Folder ID: %s', folder_id)

    proc_items = subprocess.run(
        ['bw', 'list', 'items', '--folderid', folder_id, '--session', session],
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    )
    return json.loads(proc_items.stdout)


def add_ssh_keys(session, items, itemid_path_pair: Dict[str, pathlib.Path]):
    """
    Function to attempt to get keys from a vault item
    """
    for item in items:
        print(item)
        passphrase = item["login"]["password"]
        try:
            path = itemid_path_pair[item["id"]]
        except KeyError:
            print("Path for item %s not found", item["name"])
            continue
        if passphrase is None:
            print("Passphrase not found for %s", item["name"])
            continue
        if not path.exists():
            print("Private key at %s does not exist", path)
            continue
        try:
            # sleep .3; echo testing; } | script -q /dev/null ssh-add testing_key
            subprocess.run(
                ['{ sleep .3; echo %s; } | script -q /dev/null ssh-add %s' % (passphrase, path)],
                universal_newlines=True,
                shell=True,
                check=True,
            )
        except subprocess.SubprocessError:
            logging.warning('Could not add key to the SSH agent')


if __name__ == '__main__':
    def parse_args():
        """
        Function to parse command line arguments
        """
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '-d', '--debug',
            action='store_true',
            help='show debug output',
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
        try:
            itemid_path_pair = {}
            with open(config.ITEM_ID_KEY_MAPPING_CSV) as csv_file:
                reader = csv.reader(csv_file)
                for row in reader:
                    itemid_path_pair[row[0]] = pathlib.Path(row[1]).expanduser()
            print(itemid_path_pair)
            logging.info('Getting Bitwarden session')
            session = get_session()
            logging.debug('Session = %s', session)

            logging.info('Getting folder items')
            items = folder_items(session, config.FOLDER_ID)

            logging.info('Attempting to add keys to ssh-agent')
            add_ssh_keys(session, items, itemid_path_pair)

        except subprocess.CalledProcessError as e:
            if e.stderr:
                logging.error('`%s` error: %s', e.cmd[0], e.stderr)
            logging.debug('Error running %s', e.cmd)
#        finally:
#            log_bitwarden_off()

    main()
