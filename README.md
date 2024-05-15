# bwsshauth 
Keep passphrases for your locally present private keys in Bitwarden and add them to `ssh-agent` with one command

## Motivation
Securing ssh keys with password manager ([Bitwarden](https://bitwarden.com/))

## Use case
Maintaining multiple ssh keys <br />
Frequent need for adding keys to ssh-agent

## Dependencies
- Pure python (tested on 3.10)
- [bitwarden/cli](https://github.com/bitwarden/cli)

## Setup
1. Create new folder in [Bitwarden](https://bitwarden.com/)
2. Create item with passphrase in bw's folder
3. Copy `config.py.example` as `config.py`
4. Obtain `folderId` of your folder through bitwardenw/cli [`bw list` command](https://bitwarden.com/help/cli/#list)
5. Input `folderId` into `config.py`
6. Create .csv file for bitwarden item to ssh key mapping
7. Input path to csv into `config.py`
8. Obtain `itemID` of your item through bitwarden/cli
9. Fill .csv with mapping in format: `itemId,path_to_key`
10. Make the script executable using [`chmod +x <name_of_script>`](https://www.howtogeek.com/437958/how-to-use-the-chmod-command-on-linux/)

Bonus: Create symlink in /usr/bin for easier use (I use `bwsshauth`)

## Usage
1. Type `bwsshauth`
2. Follow instructions
