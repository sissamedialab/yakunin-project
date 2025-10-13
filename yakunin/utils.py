import argparse
import json
import logging
import logging.config
from importlib.resources import files


def merge_with_config_file(args):
    """
    Merge config file.

    If we have a config file, load it and merge it with the
    command-line.  Command line args will override config-file
    directives (this is also why I don't use defaults in command line
    args).

    """
    # This function is called after the command line has been parsed
    # (this function is also called by the setup_config fixture of pytest)

    # remove all empty (None) values from the command-line args
    # the remaining args will be used dict to update (override)
    # the parameters read from the config-file
    keys = list(vars(args).keys())
    for key in keys:
        if getattr(args, key) is None:
            delattr(args, key)

    with open(args.config_file, encoding="utf-8") as config_file_content:
        config = json.load(config_file_content)
        # read LOGGING config
        logging_config = config.get("LOGGING", None)
        logging.config.dictConfig(logging_config)

        # read GENERAL config
        general_config = config.get("GENERAL", None)
        if general_config is not None:
            # override confi-file with command line
            general_config.update(vars(args))

            # add (or reset) arguments to arparse's Namespace
            map_obj = [setattr(args, x[0], x[1]) for x in general_config.items()]
            # (map is lazy: just retruns a map object,
            #  no action has yet been done;
            #  call "list" to "execute")
            list(map_obj)

    # set defaults
    # TODO: manage defaults to appear on command line
    defaults = {
        "log": logging.DEBUG,
        "pdfa_url": "https://medialab.sissa.it/ud/medusa/topdfa",
        "pitstop_url": "https://medialab.sissa.it/ud/medusa/pitstop_fix",
    }
    for key, value in defaults.items():
        if not hasattr(args, key):
            setattr(args, key, value)


def setup_yakunin():
    """
    Read and apply yakunin configuration.

    Raises:
      RuntimeError: if the config file yakunin.json cannot be found.

    """
    # Get the data file
    config_file = files("yakunin") / "yakunin.json"

    args = argparse.Namespace()

    # Check if the file exists
    if not config_file.exists():
        raise RuntimeError(f"No config file {config_file} found")

    args.config_file = config_file
    merge_with_config_file(args)
