from datetime import datetime, timezone
import functools
import json
import logging
import os
from time import sleep
from typing import Dict, Any, Union

from eth_abi import decode_single
from eth_abi.exceptions import DecodingError
from eth_typing import AnyAddress
from eth_utils import to_checksum_address, to_hex
from web3 import Web3
from web3.contract import Contract, ContractEvent

THIS_DIR = os.path.dirname(__file__)
logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_abi(name: str) -> Dict[str, Any]:
    with open(os.path.join(THIS_DIR, 'abi', name)) as f:
        return json.load(f)


def address(a: Union[bytes, str]) -> AnyAddress:
    # Web3.py expects checksummed addresses, but has no support for EIP-1191,
    # so RSK-checksummed addresses are broken
    # Should instead fix web3, but meanwhile this wrapper will help us
    return to_checksum_address(a)


# Alias, better name...
to_address = address


@functools.lru_cache()
def get_erc20_contract(*, token_address: Union[str, AnyAddress], web3: Web3) -> Contract:
    return web3.eth.contract(
        address=address(token_address),
        abi=ERC20_ABI,
    )


ERC20_ABI = load_abi('IERC20.json')


def get_events(
    *,
    event: ContractEvent,
    from_block: int,
    to_block: int,
    batch_size: int = 100
):
    """Load events in batches"""
    if to_block < from_block:
        raise ValueError(f'to_block {to_block} is smaller than from_block {from_block}')

    logger.info('fetching events from %s to %s with batch size %s', from_block, to_block, batch_size)
    ret = []
    batch_from_block = from_block
    while batch_from_block <= to_block:
        batch_to_block = min(batch_from_block + batch_size, to_block)
        logger.info('fetching batch from %s to %s (up to %s)', batch_from_block, batch_to_block, to_block)
        event_filter = event.createFilter(
            fromBlock=batch_from_block,
            toBlock=batch_to_block,
        )
        events = get_event_batch_with_retries(
            event=event,
            from_block=batch_from_block,
            to_block=batch_to_block,
        )
        if len(events) > 0:
            logger.info(f'found %s events in batch', len(events))
        ret.extend(events)
        batch_from_block = batch_to_block + 1
    return ret


def get_event_batch_with_retries(event, from_block, to_block, *, retries=3):
    while True:
        try:
            return event.getLogs(
                fromBlock=from_block,
                toBlock=to_block,
            )
        except ValueError as e:
            if retries <= 0:
                raise e
            logger.warning('error in get_all_entries: %s, retrying (%s)', e, retries)
            retries -= 1


def exponential_sleep(attempt, max_sleep_time=256.0):
    sleep_time = min(2 ** attempt, max_sleep_time)
    sleep(sleep_time)


def retryable(*, max_attempts: int = 10):
    def decorator(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt >= max_attempts:
                        logger.warning('max attempts (%s) exchusted for error: %s', max_attempts, e)
                        raise
                    logger.warning(
                        'Retryable error (attempt: %s/%s): %s',
                        attempt + 1,
                        max_attempts,
                        e,
                    )
                    exponential_sleep(attempt)
                    attempt += 1
        return wrapped
    return decorator


class UserDataNotAddress(Exception):
    def __init__(self, userdata: bytes):
        super().__init__(f'userdata {userdata!r} cannot be decoded to an address')


def decode_address_from_userdata(userdata: bytes) -> str:
    try:
        return decode_single('address', userdata)
    except DecodingError as e:
        raise UserDataNotAddress(userdata) from e


@functools.lru_cache()
def is_contract(*, web3: Web3, address: str) -> bool:
    code = web3.eth.get_code(to_address(address))
    return code != b'\x00'
