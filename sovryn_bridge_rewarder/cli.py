import json
import logging
import os

import click

from .main import run_rewarder


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
        config = json.load(f)

    logging.basicConfig(level=logging.INFO)
    click.echo('Starting rewarder bot')
    run_rewarder(
        bridge_address=config['bridge'],
        rpc_url=config['host'],
        default_start_block=config['fromBlock'],
        required_block_confirmations=config['requiredBlockConfirmations'],
    )
