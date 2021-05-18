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
    UserDataNotAddress,
    get_events,
    decode_address_from_userdata,
    is_contract,
)

CONFIG = {
    "bridge_address": "0x8e7199d5f496ea862492f4f983a1627d723328fd",
    "actual_testnet_eth_bridge_address": "0xc0e7a7fff4aba5e7286d5d67dd016b719dcc9156",
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


@pytest.fixture()
def eth_bridge_contract(web3) -> Contract:
    return get_bridge_contract(
        bridge_address=CONFIG['actual_testnet_eth_bridge_address'],
        web3=web3,
    )


def test_get_cross_transfer_events(bridge_contract: Contract):
    events = get_events(
        event=bridge_contract.events.AcceptedCrossTransfer,
        from_block=1784453,
        to_block=1785766,
    )
    assert events == EXAMPLE_CROSS_TRANSFER_EVENTS


def test_get_events_includes_events_from_to_block(bridge_contract: Contract):
    # There was a bug with this not always including the final block
    end_block = 1785741
    assert end_block == EXAMPLE_CROSS_TRANSFER_EVENTS[-1].blockNumber
    events = get_events(
        event=bridge_contract.events.AcceptedCrossTransfer,
        from_block=end_block,
        to_block=end_block,
    )
    assert len(events) == 1
    assert events == [EXAMPLE_CROSS_TRANSFER_EVENTS[-1]]


def test_get_events_no_duplicate_events(bridge_contract: Contract):
    # No bugs with this but test it anyway
    end_block = 1785741
    assert end_block == EXAMPLE_CROSS_TRANSFER_EVENTS[-1].blockNumber

    events = get_events(
        event=bridge_contract.events.AcceptedCrossTransfer,
        from_block=end_block - 4,
        to_block=end_block + 4,
        batch_size=0,  # 1 block at a time
    )
    assert len(events) == 1
    assert events == [EXAMPLE_CROSS_TRANSFER_EVENTS[-1]]


def test_get_cross_transfer_event_with_userdata(web3, eth_bridge_contract):
    # Failed reward in DB:
    # id                            | 2
    # status                        | error_confirming
    # reward_rbtc_wei               | 100000000000000
    # user_address                  | 0xc855fd4af3526215d37b39cc33fa3c352d42e6f8
    # deposit_side_token_address    | 0x4f2fc8d55c1888a5aca2503e2f3e5d74eef37c33
    # deposit_side_token_symbol     | esETH
    # deposit_main_token_address    | 0xa1f7efd2b12aba416f1c57b9a54ac92b15c3a792
    # deposit_amount_minus_fees_wei | 199000000000000000
    # deposit_log_index             | 6
    # deposit_block_hash            | 0xa4a5bcd4086485ae94c1639bd5b72d2a33764d4e3f09a3053f8194e6f478b58c
    # deposit_transaction_hash      | 0x4885316d0b42374b8debcbdc88dd552c8dba0420fb23cccb952854770df9af0e
    # reward_transaction_hash       | 0x4f7283fb570badd49cf5c62bdda3d32eb69de44f93f9540d0bbfea9490f0f8e2
    # reward_transaction_nonce      | 4
    # created_at                    | 2021-05-17 19:19:13.124205+00
    # sent_at                       | 2021-05-17 19:19:13.314632+00
    block = web3.eth.get_block('0xa4a5bcd4086485ae94c1639bd5b72d2a33764d4e3f09a3053f8194e6f478b58c')
    events = get_events(
        event=eth_bridge_contract.events.AcceptedCrossTransfer,
        from_block=block.number,
        to_block=block.number,
    )
    assert events == [EXAMPLE_CROSS_TRANSFER_EVENT_WITH_USERDATA]


def test_parse_deposits_from_events(web3, bridge_contract):
    deposits = parse_deposits_from_events(
        web3=web3,
        bridge_contract=bridge_contract,
        events=EXAMPLE_CROSS_TRANSFER_EVENTS,
        fee_percentage=Decimal('0.002'),
    )
    assert deposits == [
        Deposit(**{
            'amount_decimal': Decimal('2.5'),
            'amount_minus_fees_wei': 2495000000000000000,
            'block_hash': '0x11dcc6cd8198159ae7fdf252a42101ad20fc50c614981d3291e562367f66791a',
            'event': None,
            'log_index': 7,
            'main_token_address': '0x83241490517384cb28382bdd4d1534ee54d9350f',
            'side_token_address': '0x081d4aa03ac5cdaf2b758306a259e1bd0896c0ca',
            'side_token_symbol': 'DAIbs',
            'transaction_hash': '0x0462cb7f734cd277d087a80205b4098ed4e447ec3c7847b68652dd2994a44980',
            'contract_address': '0x8e7199d5f496ea862492f4f983a1627d723328fd',
            'user_address': '0xca478e11953fe327b46dd71dd9fd31c92dc9a9ae'
        }),
        Deposit(**{
            'amount_decimal': Decimal('3'),
            'amount_minus_fees_wei': 2994000000000000000,
            'block_hash': '0x284b7a205246897df0f416ed17dab9aa90c9dbedc8448dd7a13626e405906010',
            'event': None,
            'log_index': 3,
            'main_token_address': '0x83241490517384cb28382bdd4d1534ee54d9350f',
            'side_token_address': '0x081d4aa03ac5cdaf2b758306a259e1bd0896c0ca',
            'side_token_symbol': 'DAIbs',
            'transaction_hash': '0x79e1e0211c0832e55e29dc6b31e0be8e2aded15ee2783a8c7d5f1032ad7eddbd',
            'contract_address': '0x8e7199d5f496ea862492f4f983a1627d723328fd',
            'user_address': '0xca478e11953fe327b46dd71dd9fd31c92dc9a9ae'
        }),
        Deposit(**{
            'amount_decimal': Decimal('3'),
            'amount_minus_fees_wei': 2994000000000000000,
            'block_hash': '0x614b75ba52cbe0a643850b909a0cd29b9032a116059849f148e631e0e5764a52',
            'event': None,
            'log_index': 3,
            'main_token_address': '0x83241490517384cb28382bdd4d1534ee54d9350f',
            'side_token_address': '0x081d4aa03ac5cdaf2b758306a259e1bd0896c0ca',
            'side_token_symbol': 'DAIbs',
            'transaction_hash': '0x05f16236ee5ca06311f4a014b9fcaa40a32389c6c95b86267ab0bfcbc5616972',
            'contract_address': '0x8e7199d5f496ea862492f4f983a1627d723328fd',
            'user_address': '0xca478e11953fe327b46dd71dd9fd31c92dc9a9ae'
        })
    ]


def test_decode_address_from_userdata():
    user_data = (b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                 b'_\xc4\xd8\xb1\xf9j\x91f\x83\x95Brr\x1c\xfe\x96\xedZ9S')
    assert decode_address_from_userdata(user_data) == '0x5fc4d8b1f96a916683954272721cfe96ed5a3953'


def test_decode_address_from_invalid_userdata():
    user_data = b'_\xc4\xd8\xb1\xf9j\x91f\x83\x95Brr\x1c\xfe\x96\xedZ9'
    with pytest.raises(UserDataNotAddress):
        decode_address_from_userdata(user_data)


def test_is_contract_eoa(web3):
    assert is_contract(web3=web3, address='0xca478e11953fe327b46dd71dd9fd31c92dc9a9ae') is False


def test_is_contract_contract(web3):
    assert is_contract(web3=web3, address='0xc855fd4af3526215d37b39cc33fa3c352d42e6f8') is True


def test_parse_deposits_from_event_with_userdata(web3, eth_bridge_contract):
    deposits = parse_deposits_from_events(
        web3=web3,
        bridge_contract=eth_bridge_contract,
        events=[EXAMPLE_CROSS_TRANSFER_EVENT_WITH_USERDATA],
        fee_percentage=Decimal('0.002'),
    )
    assert len(deposits) == 1
    deposit = deposits[0]
    # Important part -- we want to decode the user_address to the actual receiver from user data
    assert deposit.user_address == '0x5fc4d8b1f96a916683954272721cfe96ed5a3953'
    # Verify these too, just to be sure
    assert deposit.side_token_symbol == 'esETH'
    assert deposit.transaction_hash == '0x4885316d0b42374b8debcbdc88dd552c8dba0420fb23cccb952854770df9af0e'
    assert deposit.block_hash == '0xa4a5bcd4086485ae94c1639bd5b72d2a33764d4e3f09a3053f8194e6f478b58c'
    assert deposit.log_index == 6
    assert deposit.amount_minus_fees_wei == 199000000000000000
    assert deposit.contract_address == '0xc0e7a7fff4aba5e7286d5d67dd016b719dcc9156'
    assert deposit.main_token_address == '0xa1f7efd2b12aba416f1c57b9a54ac92b15c3a792'  # WETH


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
EXAMPLE_CROSS_TRANSFER_EVENT_WITH_USERDATA = AttributeDict({
    'address': '0xC0E7A7FfF4aBa5e7286D5d67dD016B719DCc9156',
    'args': {'_amount': 199000000000000000,
             '_calculatedDecimals': 18,
             '_calculatedGranularity': 1,
             '_decimals': 18,
             '_formattedAmount': 199000000000000000,
             '_granularity': 1,
             '_to': '0xC855FD4aF3526215d37b39Cc33fa3C352d42e6F8',
             '_tokenAddress': '0xa1F7EfD2B12aBa416f1c57b9a54AC92B15C3A792',
             '_userData': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                          b'_\xc4\xd8\xb1\xf9j\x91f\x83\x95Brr\x1c\xfe\x96\xedZ9S'},
    'blockHash': HexBytes('0xa4a5bcd4086485ae94c1639bd5b72d2a33764d4e3f09a3053f8194e6f478b58c'),
    'blockNumber': 1851584,
    'event': 'AcceptedCrossTransfer',
    'logIndex': 6,
    'transactionHash': HexBytes('0x4885316d0b42374b8debcbdc88dd552c8dba0420fb23cccb952854770df9af0e'),
    'transactionIndex': 1
})

