from collections import defaultdict
from decimal import Decimal
from typing import cast

import pytest
from hexbytes import HexBytes
from sqlalchemy.orm import Session
from web3 import Web3

from sovryn_bridge_rewarder.models import Reward, RewardStatus
from sovryn_bridge_rewarder.deposits import Deposit
from sovryn_bridge_rewarder.config import RewardThresholdMap
from sovryn_bridge_rewarder.rewards import (
    queue_reward,
    get_queued_reward_ids,
)


EXAMPLE_DEPOSIT = Deposit(
    amount_decimal=Decimal('30'),
    amount_minus_fees_wei=29940000000000000000,
    block_hash='0x614b75ba52cbe0a643850b909a0cd29b9032a116059849f148e631e0e5764a52',
    log_index=3,
    main_token_address='0x83241490517384cb28382bdd4d1534ee54d9350f',
    side_token_address='0x081d4aa03ac5cdaf2b758306a259e1bd0896c0ca',
    side_token_symbol='DAIbs',
    transaction_hash='0x05f16236ee5ca06311f4a014b9fcaa40a32389c6c95b86267ab0bfcbc5616972',
    user_address='0xca478e11953fe327b46dd71dd9fd31c92dc9a9ae',
    contract_address='0x8e7199d5f496ea862492f4f983a1627d723328fd',
)
ANOTHER_DEPOSIT_DIFFERENT_USER = Deposit(
    amount_decimal=Decimal('2.5'),
    amount_minus_fees_wei=2495000000000000000,
    block_hash='0x11dcc6cd8198159ae7fdf252a42101ad20fc50c614981d3291e562367f66791a',
    log_index=7,
    main_token_address='0x83241490517384cb28382bdd4d1534ee54d9350f',
    side_token_address='0x081d4aa03ac5cdaf2b758306a259e1bd0896c0ca',
    side_token_symbol='DAIbs',
    transaction_hash='0x0462cb7f734cd277d087a80205b4098ed4e447ec3c7847b68652dd2994a44980',
    user_address='0xf00AF1989184Ae43577Fd33E006baD4bF760F98F',
    contract_address='0x8e7199d5f496ea862492f4f983a1627d723328fd',
)
ANOTHER_DEPOSIT_SAME_USER = Deposit(
    amount_decimal=Decimal('2.5'),
    amount_minus_fees_wei=2495000000000000000,
    block_hash='0x11dcc6cd8198159ae7fdf252a42101ad20fc50c614981d3291e562367f66791a',
    log_index=7,
    main_token_address='0x83241490517384cb28382bdd4d1534ee54d9350f',
    side_token_address='0x081d4aa03ac5cdaf2b758306a259e1bd0896c0ca',
    side_token_symbol='DAIbs',
    transaction_hash='0x0462cb7f734cd277d087a80205b4098ed4e447ec3c7847b68652dd2994a44980',
    user_address='0xca478e11953fe327b46dd71dd9fd31c92dc9a9ae',
    contract_address='0x8e7199d5f496ea862492f4f983a1627d723328fd',
)


def _normalize_address(a):
    if isinstance(a, HexBytes):
        a = a.hex()
    return a.lower()


class MockEth:
    def __init__(self):
        self._balances = defaultdict(int)
        self._transaction_counts = defaultdict(int)

    def get_balance(self, address) -> int:
        return self._balances[_normalize_address(address)]

    def get_transaction_count(self, address) -> int:
        return self._transaction_counts[_normalize_address(address)]

    def set_balance(self, address, value: int):
        self._balances[_normalize_address(address)] = value

    def set_transaction_count(self, address, value: int):
        self._transaction_counts[_normalize_address(address)] = value


class MockWeb3:
    eth: MockEth

    def __init__(self):
        self.eth = MockEth()


@pytest.fixture
def mock_web3() -> MockWeb3:
    # By default, the users have no balances and no transactions
    return MockWeb3()


def test_queue_reward_threshold_not_met(dbsession: Session, mock_web3):
    queue_reward(
        deposit=EXAMPLE_DEPOSIT,
        dbsession=dbsession,
        web3=mock_web3,
        reward_amount_rbtc=Decimal('0.01'),
        deposit_thresholds=RewardThresholdMap({
            'DAIbs': Decimal('30.01'),
        }),
    )
    assert dbsession.query(Reward).count() == 0


def test_queue_reward_token_not_found(dbsession: Session, mock_web3):
    queue_reward(
        deposit=EXAMPLE_DEPOSIT,
        dbsession=dbsession,
        web3=mock_web3,
        reward_amount_rbtc=Decimal('0.01'),
        deposit_thresholds=RewardThresholdMap({
            'FOO': Decimal('30.00'),
        })
    )
    assert dbsession.query(Reward).count() == 0


def test_queue_reward_threshold_is_met(dbsession: Session, mock_web3):
    queue_reward(
        deposit=EXAMPLE_DEPOSIT,
        dbsession=dbsession,
        web3=mock_web3,
        reward_amount_rbtc=Decimal('0.01'),
        deposit_thresholds=RewardThresholdMap({
            'DAIbs': Decimal('30.00'),
        })
    )
    assert dbsession.query(Reward).count() == 1
    reward = dbsession.query(Reward).first()
    assert reward.user_address == EXAMPLE_DEPOSIT.user_address
    assert reward.reward_rbtc_wei == 10_000_000_000_000_000
    assert reward.reward_transaction_hash is None
    assert reward.sent_at is None
    for key in [
        'amount_minus_fees_wei',
        'block_hash',
        'log_index',
        'main_token_address',
        'side_token_address',
        'side_token_symbol',
        'transaction_hash',
    ]:
        assert getattr(reward, f'deposit_{key}') == getattr(EXAMPLE_DEPOSIT, key)


def test_reward_not_queued_twice(dbsession: Session, mock_web3):
    def queue():
        return queue_reward(
            deposit=EXAMPLE_DEPOSIT,
            dbsession=dbsession,
            web3=mock_web3,
            reward_amount_rbtc=Decimal('0.01'),
            deposit_thresholds=RewardThresholdMap({
                'DAIbs': Decimal('30.00'),
            })
        )

    reward = queue()
    assert reward
    assert dbsession.query(Reward).count() == 1

    another = queue()
    assert not another
    assert dbsession.query(Reward).count() == 1

    reward.status = RewardStatus.sent
    dbsession.flush()
    another = queue()
    assert not another
    assert dbsession.query(Reward).count() == 1


def test_queue_multiple_rewards(dbsession, mock_web3):
    reward_amount_rbtc = Decimal('0.01')
    deposit_thresholds = RewardThresholdMap({
        'DAIbs': Decimal('2.00'),
    })
    queue_reward(
        deposit=EXAMPLE_DEPOSIT,
        dbsession=dbsession,
        web3=mock_web3,
        reward_amount_rbtc=reward_amount_rbtc,
        deposit_thresholds=deposit_thresholds,
    )
    assert dbsession.query(Reward).count() == 1
    another_reward = queue_reward(
        deposit=ANOTHER_DEPOSIT_DIFFERENT_USER,
        dbsession=dbsession,
        web3=mock_web3,
        reward_amount_rbtc=reward_amount_rbtc,
        deposit_thresholds=deposit_thresholds,
    )
    assert another_reward
    assert dbsession.query(Reward).count() == 2
    assert another_reward.deposit_transaction_hash == ANOTHER_DEPOSIT_DIFFERENT_USER.transaction_hash


def test_reward_not_queued_again_for_same_user(dbsession, mock_web3):
    reward_amount_rbtc = Decimal('0.01')
    deposit_thresholds = RewardThresholdMap({
        'DAIbs': Decimal('2.00'),
    })
    queue_reward(
        deposit=EXAMPLE_DEPOSIT,
        dbsession=dbsession,
        web3=mock_web3,
        reward_amount_rbtc=reward_amount_rbtc,
        deposit_thresholds=deposit_thresholds,
    )
    assert dbsession.query(Reward).count() == 1
    another_reward = queue_reward(
        deposit=ANOTHER_DEPOSIT_SAME_USER,
        dbsession=dbsession,
        web3=mock_web3,
        reward_amount_rbtc=reward_amount_rbtc,
        deposit_thresholds=deposit_thresholds,
    )
    assert dbsession.query(Reward).count() == 1
    assert not another_reward


def test_get_queued_reward_ids(dbsession, mock_web3):
    reward_amount_rbtc = Decimal('0.01')
    deposit_thresholds = RewardThresholdMap({
        'DAIbs': Decimal('2.00'),
    })
    reward_1 = queue_reward(
        deposit=EXAMPLE_DEPOSIT,
        dbsession=dbsession,
        web3=mock_web3,
        reward_amount_rbtc=reward_amount_rbtc,
        deposit_thresholds=deposit_thresholds,
    )
    reward_2 = queue_reward(
        deposit=ANOTHER_DEPOSIT_DIFFERENT_USER,
        dbsession=dbsession,
        web3=mock_web3,
        reward_amount_rbtc=reward_amount_rbtc,
        deposit_thresholds=deposit_thresholds,
    )
    assert dbsession.query(Reward).count() == 2  # sanity check

    assert get_queued_reward_ids(dbsession) == [reward_1.id, reward_2.id]

    reward_1.status = RewardStatus.sent
    dbsession.flush()

    assert get_queued_reward_ids(dbsession) == [reward_2.id]


def test_queue_reward_user_has_existing_balance(dbsession: Session, mock_web3: MockWeb3):
    """Users with existing RBTC balances should not be rewarded"""
    mock_web3.eth.set_balance(EXAMPLE_DEPOSIT.user_address, 1)
    queue_reward(
        deposit=EXAMPLE_DEPOSIT,
        dbsession=dbsession,
        web3=cast(Web3, mock_web3),
        reward_amount_rbtc=Decimal('0.01'),
        deposit_thresholds=RewardThresholdMap({
            'DAIbs': Decimal('30.00'),
        })
    )
    assert dbsession.query(Reward).count() == 0


def test_queue_reward_user_has_existing_transactions(dbsession: Session, mock_web3: MockWeb3):
    """Users who have already done transactions in RSK should not be rewarded"""
    mock_web3.eth.set_transaction_count(EXAMPLE_DEPOSIT.user_address, 1)
    queue_reward(
        deposit=EXAMPLE_DEPOSIT,
        dbsession=dbsession,
        web3=cast(Web3, mock_web3),
        reward_amount_rbtc=Decimal('0.01'),
        deposit_thresholds=RewardThresholdMap({
            'DAIbs': Decimal('30.00'),
        })
    )
    assert dbsession.query(Reward).count() == 0
