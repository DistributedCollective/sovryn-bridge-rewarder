import functools
import json
import logging
from typing import Dict, Any, Union
import os

from eth_typing import AnyAddress
from eth_utils import to_checksum_address
from web3 import Web3
from web3.contract import Contract, ContractEvent

THIS_DIR = os.path.dirname(__file__)
logger = logging.getLogger(__name__)


def load_abi(name: str) -> Dict[str, Any]:
    with open(os.path.join(THIS_DIR, 'abi', name)) as f:
        return json.load(f)


def address(a: Union[bytes, str]) -> AnyAddress:
    return to_checksum_address(a)


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
    while batch_from_block < to_block:
        batch_to_block = min(batch_from_block + batch_size, to_block)
        logger.info('fetching batch from %s to %s (up to %s)', batch_from_block, batch_to_block, to_block)
        event_filter = event.createFilter(
            fromBlock=batch_from_block,
            toBlock=batch_to_block,
        )
        events = event_filter.get_all_entries()
        logger.info(f'found %s events', len(events))
        ret.extend(events)
        batch_from_block = batch_to_block + 1
    return ret
