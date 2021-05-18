import sys
from multiprocessing import Process
import json
import logging
import os

import click

from .main import run_rewarder
from .config import load_from_json


@click.command('sovryn_bridge_rewarder')
@click.argument('config_file')
@click.option('--rewarder/--no-rewarder', default=True)
@click.option('--ui/--no-ui', default=False)
@click.pass_context
def main(context, config_file: str, rewarder: bool, ui: bool):
    """
    Start a bot that rewards RBTC to users of the token bridge
    """
    if not os.path.exists(config_file):
        context.fail(f'config file not found at path {config_file!r}')
    with open(config_file) as f:
        config_json = json.load(f)
        config = load_from_json(config_json)

    if config.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(
            config.sentry_dsn,
            traces_sample_rate=0.1
        )
        click.echo("Sentry initialized")
    else:
        click.echo("Sentry DSN not provided -- Sentry not initialized")

    _setup_logging()

    ui_process = None
    if ui:
        ui_process = _launch(target=_start_ui, args=(config,), in_process=rewarder)

    try:
        if rewarder:
            click.echo('Starting rewarder bot')
            run_rewarder(config)
    finally:
        if ui_process:
            _close_process(ui_process)


def _setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.NOTSET)
    formatter = logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] %(message)s')

    error_handler = logging.StreamHandler(sys.stderr)
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)

    info_handler = logging.StreamHandler(sys.stdout)
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    root.addHandler(info_handler)



def _start_ui(config):
    os.environ.setdefault('DEBUG', '0')
    from .ui.ui_main import run_ui
    run_ui(config)


def _launch(target, args, in_process: bool):
    """
    Launch target with args, in a separate process if `in_process` = True
    """
    if in_process:
        process = Process(target=target, args=args)
        process.start()
        return process
    else:
        target(*args)


def _close_process(process):
    try:
        process.close()
    except:
        process.terminate()
