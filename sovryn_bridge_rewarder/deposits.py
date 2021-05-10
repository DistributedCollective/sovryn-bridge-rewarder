"""
Logic for fetching token deposits from the bridge contract
"""
from dataclasses import dataclass
from decimal import Decimal
import functools
import logging
from typing import List, Any

from web3 import Web3
from eth_utils import to_int
from web3.contract import Contract

from .utils import get_erc20_contract, get_events, address


logger = logging.getLogger(__name__)


@dataclass
class Deposit:
    """
    Token transfer from another chain to RSK
    """
    user_address: str
    side_token_address: str  # token address in RSK
    side_token_symbol: str  # token symbol in RSK
    main_token_address: str  # the token in the other chain
    amount_minus_fees_wei: int
    amount_decimal: Decimal  # Amount without fees in "real" units, decimal adjusted
    block_hash: str
    transaction_hash: str
    log_index: int
    event: Any = None  # For debugging


def get_deposits(
    *,
    bridge_contract: Contract,
    web3: Web3,
    from_block: int,
    to_block: int,
):
    """
    Load all Deposits (token transfers from another chain to RSK) from the RSK bridge contract
    """
    events = get_events(
        event=bridge_contract.events.AcceptedCrossTransfer,
        from_block=from_block,
        to_block=to_block,
    )
    return parse_deposits_from_events(
        web3=web3,
        bridge_contract=bridge_contract,
        events=events,
    )


@dataclass()
class SideToken:
    address: str
    symbol: str
    decimals: int
    contract: Contract


# NOTE: we lose logging and require restarts between adding tokens if we cache this
@functools.lru_cache()
def get_side_token(
    *,
    web3: Web3,
    bridge_contract: Contract,
    main_token_address,
):
    is_main_token = bridge_contract.functions.knownTokens(
        address(main_token_address)
    ).call()
    if is_main_token:
        logger.info('Token %s is main token', main_token_address)
        return None

    side_token_address = bridge_contract.functions.mappedTokens(
        address(main_token_address)
    ).call()
    if to_int(hexstr=side_token_address) == 0:
        logger.error('side token not found for %s', main_token_address)
        return None

    side_token_contract = get_erc20_contract(
        web3=web3,
        token_address=side_token_address,
    )
    side_token_symbol = side_token_contract.functions.symbol().call()
    side_token_decimals = side_token_contract.functions.decimals().call()
    return SideToken(
        address=side_token_address.lower(),
        symbol=side_token_symbol,
        decimals=side_token_decimals,
        contract=side_token_contract,
    )


def parse_deposits_from_events(
    *,
    web3: Web3,
    bridge_contract: Contract,
    events: List[Any],
    fee_percentage: Decimal = Decimal('0.002'),  # This is hard to parse from the contract, so just hardcode
) -> List[Deposit]:
    # An event looks like this:
    # AttributeDict({
    #     'address': '0x8E7199D5F496eA862492F4F983A1627D723328fd',
    #     'args': {'_amount': 2495000000000000000,
    #              '_calculatedDecimals': 18,
    #              '_calculatedGranularity': 1,
    #              '_decimals': 18,
    #              '_formattedAmount': 2495000000000000000,
    #              '_granularity': 1,
    #              '_to': '0xCa478e11953FE327B46Dd71DD9fd31C92DC9A9Ae',
    #              '_tokenAddress': '0x83241490517384cB28382Bdd4D1534eE54d9350F',
    #              '_userData': b''},
    #     'blockHash': HexBytes('0x11dcc6cd8198159ae7fdf252a42101ad20fc50c614981d3291e562367f66791a'),
    #     'blockNumber': 1785018,
    #     'event': 'AcceptedCrossTransfer',
    #     'logIndex': 7,
    #     'transactionHash': HexBytes('0x0462cb7f734cd277d087a80205b4098ed4e447ec3c7847b68652dd2994a44980'),
    #     'transactionIndex': 4
    # })
    ret = []
    for event in events:
        args = event['args']
        main_token_address = args['_tokenAddress'].lower()  # this is in another chain
        side_token = get_side_token(
            web3=web3,
            bridge_contract=bridge_contract,
            main_token_address=main_token_address,
        )
        if not side_token:
            logger.info('token %s is not from another chain', main_token_address)
            continue

        amount_minus_fees_wei = args['_formattedAmount']  # this has 18 decimals always
        user_address = args['_to'].lower()

        amount_minus_fees_decimal = Decimal(amount_minus_fees_wei) / (Decimal(10) ** side_token.decimals)
        amount_decimal = amount_minus_fees_decimal / (Decimal(1) - fee_percentage)
        deposit = Deposit(
            user_address=user_address,
            side_token_address=side_token.address,
            side_token_symbol=side_token.symbol,
            main_token_address=main_token_address,
            amount_minus_fees_wei=amount_minus_fees_wei,
            amount_decimal=amount_decimal,
            block_hash=event.blockHash.hex().lower(),
            transaction_hash=event.transactionHash.hex().lower(),
            log_index=event.logIndex,
            #event=event,
        )
        ret.append(deposit)
    return ret
