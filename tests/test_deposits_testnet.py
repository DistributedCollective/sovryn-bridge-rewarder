# This actually tests stuff against a contract deployed on testnet, so it will require a web connection
# Seems reasonable however, and because data is in the blockchain forever, it can be made idempodent
from decimal import Decimal

import pytest
from hexbytes import HexBytes

from web3 import Web3
from web3.contract import Contract
from web3.datastructures import AttributeDict
from sovryn_bridge_rewarder.main import (
    get_bridge_contract,
)
from sovryn_bridge_rewarder.deposits import (
    Deposit,
    parse_deposits_from_events,
)
from sovryn_bridge_rewarder.utils import (
    get_events,
)


CONFIG = {
    "bridge_address": "0x8e7199d5f496ea862492f4f983a1627d723328fd",
    "rpc_url": "https://testnet.sovryn.app/rpc",
    "start_block": 1784453,
}


@pytest.fixture()
def web3() -> Web3:
    return Web3(Web3.HTTPProvider(CONFIG['rpc_url']))


@pytest.fixture()
def bridge_contract(web3) -> Contract:
    return get_bridge_contract(
        bridge_address=CONFIG['bridge_address'],
        web3=web3,
    )


def test_get_cross_transfer_events(bridge_contract: Contract):
    events = get_events(
        event=bridge_contract.events.AcceptedCrossTransfer,
        from_block=1784453,
        to_block=1785766,
    )
    assert events == EXAMPLE_CROSS_TRANSFER_EVENTS


def test_parse_deposits_from_events(web3, bridge_contract):
    deposits = parse_deposits_from_events(
        web3=web3,
        bridge_contract=bridge_contract,
        events=EXAMPLE_CROSS_TRANSFER_EVENTS
    )
    #pprint_improved(deposits)
    assert deposits == [
        Deposit(**{
            'amount_decimal': Decimal('2.5'),
             'amount_minus_fees_wei': 2495000000000000000,
             'event': None,
             'main_token_address': '0x83241490517384cb28382bdd4d1534ee54d9350f',
             'side_token_address': '0x081d4aa03ac5cdaf2b758306a259e1bd0896c0ca',
             'side_token_symbol': 'DAIbs',
             'user_address': '0xca478e11953fe327b46dd71dd9fd31c92dc9a9ae'
        }),
        Deposit(**{
            'amount_decimal': Decimal('3'),
            'amount_minus_fees_wei': 2994000000000000000,
            'event': None,
            'main_token_address': '0x83241490517384cb28382bdd4d1534ee54d9350f',
            'side_token_address': '0x081d4aa03ac5cdaf2b758306a259e1bd0896c0ca',
            'side_token_symbol': 'DAIbs',
            'user_address': '0xca478e11953fe327b46dd71dd9fd31c92dc9a9ae'
        }),
        Deposit(**{
            'amount_decimal': Decimal('3'),
            'amount_minus_fees_wei': 2994000000000000000,
            'event': None,
            'main_token_address': '0x83241490517384cb28382bdd4d1534ee54d9350f',
            'side_token_address': '0x081d4aa03ac5cdaf2b758306a259e1bd0896c0ca',
            'side_token_symbol': 'DAIbs',
            'user_address': '0xca478e11953fe327b46dd71dd9fd31c92dc9a9ae'
        })
    ]


EXAMPLE_CROSS_TRANSFER_EVENTS = [
    AttributeDict({
        'address': '0x8E7199D5F496eA862492F4F983A1627D723328fd',
        'args': {'_amount': 2495000000000000000,
                 '_calculatedDecimals': 18,
                 '_calculatedGranularity': 1,
                 '_decimals': 18,
                 '_formattedAmount': 2495000000000000000,
                 '_granularity': 1,
                 '_to': '0xCa478e11953FE327B46Dd71DD9fd31C92DC9A9Ae',
                 '_tokenAddress': '0x83241490517384cB28382Bdd4D1534eE54d9350F',
                 '_userData': b''},
        'blockHash': HexBytes('0x11dcc6cd8198159ae7fdf252a42101ad20fc50c614981d3291e562367f66791a'),
        'blockNumber': 1785018,
        'event': 'AcceptedCrossTransfer',
        'logIndex': 7,
        'transactionHash': HexBytes('0x0462cb7f734cd277d087a80205b4098ed4e447ec3c7847b68652dd2994a44980'),
        'transactionIndex': 4
    }),
    AttributeDict({
        'address': '0x8E7199D5F496eA862492F4F983A1627D723328fd',
        'args': {'_amount': 2994000000000000000,
                 '_calculatedDecimals': 18,
                 '_calculatedGranularity': 1,
                 '_decimals': 18,
                 '_formattedAmount': 2994000000000000000,
                 '_granularity': 1,
                 '_to': '0xCa478e11953FE327B46Dd71DD9fd31C92DC9A9Ae',
                 '_tokenAddress': '0x83241490517384cB28382Bdd4D1534eE54d9350F',
                 '_userData': b''},
        'blockHash': HexBytes('0x284b7a205246897df0f416ed17dab9aa90c9dbedc8448dd7a13626e405906010'),
        'blockNumber': 1785236,
        'event': 'AcceptedCrossTransfer',
        'logIndex': 3,
        'transactionHash': HexBytes('0x79e1e0211c0832e55e29dc6b31e0be8e2aded15ee2783a8c7d5f1032ad7eddbd'),
        'transactionIndex': 0
    }),
    AttributeDict({
        'address': '0x8E7199D5F496eA862492F4F983A1627D723328fd',
        'args': {'_amount': 2994000000000000000,
                 '_calculatedDecimals': 18,
                 '_calculatedGranularity': 1,
                 '_decimals': 18,
                 '_formattedAmount': 2994000000000000000,
                 '_granularity': 1,
                 '_to': '0xCa478e11953FE327B46Dd71DD9fd31C92DC9A9Ae',
                 '_tokenAddress': '0x83241490517384cB28382Bdd4D1534eE54d9350F',
                 '_userData': b''},
        'blockHash': HexBytes('0x614b75ba52cbe0a643850b909a0cd29b9032a116059849f148e631e0e5764a52'),
        'blockNumber': 1785741,
        'event': 'AcceptedCrossTransfer',
        'logIndex': 3,
        'transactionHash': HexBytes('0x05f16236ee5ca06311f4a014b9fcaa40a32389c6c95b86267ab0bfcbc5616972'),
        'transactionIndex': 2
    }),
]
