import json
import logging
import os

import click

from .main import run_rewarder
from .config import load_from_json


@click.command('sovryn_bridge_rewarder')
@click.argument('config_file')
@click.pass_context
def main(context, config_file: str):
    """
    Start a bot that rewards RBTC to users of the token bridge
    """
    if not os.path.exists(config_file):
        context.fail(f'config file not found at path {config_file!r}')
    with open(config_file) as f:
        config_json = json.load(f)
        config = load_from_json(config_json)

    logging.basicConfig(level=logging.INFO)
    click.echo('Starting rewarder bot')
    run_rewarder(config)
