import logging
from typing import Union

from eth_typing import Address, AnyAddress
from web3 import Web3
from web3.contract import Contract

from .deposits import get_deposits
from .utils import address, load_abi

logger = logging.getLogger(__name__)
BRIDGE_ABI = load_abi('Bridge.json')


def run_rewarder(
    *,
    bridge_address: Address,
    rpc_url: str,
    start_block: int,
    required_block_confirmations: int
):
    logger.info('Starting rewarder')
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    logger.info('Connected to chain %s, rpc url: %s', web3.eth.chain_id, rpc_url)

    bridge_contract = get_bridge_contract(
        bridge_address=bridge_address,
        web3=web3
    )

    current_block = web3.eth.get_block_number()
    to_block = current_block - required_block_confirmations

    if to_block < start_block:
        logger.info('to_block %s is smaller than start_block %s, not doing anything', to_block, start_block)
        return

    deposits = get_deposits(
        bridge_contract=bridge_contract,
        web3=web3,
        from_block=start_block,
        to_block=to_block,
    )
    print('deposits')
    print(deposits)


def get_bridge_contract(*, bridge_address: Union[str, AnyAddress], web3: Web3) -> Contract:
    return web3.eth.contract(
        address=address(bridge_address),
        abi=BRIDGE_ABI
    )
