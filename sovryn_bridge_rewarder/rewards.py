"""
Logic for queueing and sending rewards based on found deposits
Handles both DB and Web3 related logic.
"""
from decimal import Decimal
import logging
from typing import List, Optional

from eth_account.signers.base import BaseAccount
from hexbytes import HexBytes
from sqlalchemy import func
from sqlalchemy.orm.session import Session, sessionmaker
from web3 import Web3

from .config import RewardThresholdTable
from .deposits import Deposit
from .models import Reward, RewardStatus
from .utils import address, retryable, utcnow

logger = logging.getLogger(__name__)
MAX_PENDING_TRANSACTIONS = 4  # RSK limit


def queue_reward(
    *,
    deposit: Deposit,
    dbsession: Session,
    reward_amount_rbtc: Decimal,
    deposit_thresholds: RewardThresholdTable,
):
    threshold = deposit_thresholds.get(deposit.side_token_symbol)
    if not threshold:
        # TODO: maybe these should be added somewhere for post processing?
        logger.warning('Threshold not found for deposit %s -- cannot process', deposit)
        return
    if deposit.amount_decimal < threshold:
        logger.info('Threshold %s not met for deposit %s -- not rewarding', threshold, deposit)
        return

    existing_reward = dbsession.query(Reward).filter(
        func.lower(Reward.user_address) == deposit.user_address.lower()
    ).first()
    if existing_reward:
        logger.info('User %s has already been rewarded.', deposit.user_address)
        return

    logger.info('Rewarding user %s with %s RBTC', deposit.user_address, str(reward_amount_rbtc))

    reward = Reward(
        status=RewardStatus.queued,
        reward_rbtc_wei=int(reward_amount_rbtc * 10**18),
        user_address=deposit.user_address,
        deposit_side_token_address=deposit.side_token_address,
        deposit_side_token_symbol=deposit.side_token_symbol,
        deposit_main_token_address=deposit.main_token_address,
        deposit_amount_minus_fees_wei=deposit.amount_minus_fees_wei,
        deposit_log_index=deposit.log_index,
        deposit_block_hash=deposit.block_hash,
        deposit_transaction_hash=deposit.transaction_hash,
    )
    dbsession.add(reward)
    dbsession.flush()
    return reward


def get_queued_reward_ids(dbsession: Session):
    q = dbsession.query(Reward.id).filter_by(status=RewardStatus.queued).all()
    return [r.id for r in q]


def send_queued_rewards(
    *,
    web3: Web3,
    DBSession: sessionmaker,
    from_account: BaseAccount,
):
    with DBSession.begin() as dbsession:
        reward_ids = get_queued_reward_ids(dbsession)
    if not reward_ids:
        logger.info('No queued rewards found.')
        return

    logger.info('%s rewards in queue -- sending', len(reward_ids))
    nonce = web3.eth.get_transaction_count('pending')
    pending_transactions = []
    for reward_id in reward_ids:
        transaction_hash = send_reward(
            reward_id=reward_id,
            web3=web3,
            DBSession=DBSession,
            from_account=from_account,
            nonce=nonce,
        )
        if not transaction_hash:
            # It will return None if it didn't send a transaction
            continue
        pending_transactions.append(transaction_hash)
        nonce += 1
        if len(pending_transactions) >= MAX_PENDING_TRANSACTIONS:
            confirm_rewards(
                web3=web3,
                transaction_hashes=pending_transactions,
                DBSession=DBSession,
            )
            pending_transactions = []

    if pending_transactions:
        logger.info('Still waiting for %s pending transactions', len(pending_transactions))
        confirm_rewards(
            web3=web3,
            transaction_hashes=pending_transactions,
            DBSession=DBSession,
        )
    logger.info('Sent and confirmed %s rewards', len(reward_ids))


def send_reward(
    *,
    web3: Web3,
    DBSession: sessionmaker,
    from_account: BaseAccount,
    reward_id: int,
    nonce: int,
) -> Optional[HexBytes]:
    gas_price = web3.eth.gas_price
    gas_costs = gas_price * 21000 * 2
    from_address = from_account.address.lower()
    sender_rbtc_balance = web3.eth.get_balance(address(from_address))

    with DBSession.begin() as dbsession:
        reward = dbsession.query(Reward).filter_by(id=reward_id).one()
        if reward.status != RewardStatus.queued:
            logger.warning(
                'Invalid reward status: %s - expected %s',
                reward.status,
                RewardStatus.queued
            )
            return

        transaction_cost = reward.reward_rbtc_wei + gas_costs
        if sender_rbtc_balance < transaction_cost:
            logger.warning(
                'account %s balance %s is lower than tx cost %s -- not sending reward %s',
                from_address,
                sender_rbtc_balance,
                transaction_cost,
                reward_id,
            )
            return

        user_address = reward.user_address
        amount_wei = reward.reward_rbtc_wei
        signed_transaction = from_account.sign_transaction({
            'from': address(from_address),
            'to': address(user_address),
            'value': amount_wei,
            'nonce': nonce,
        })

        reward.status = RewardStatus.sending
        reward.reward_transaction_nonce = nonce
        reward.sent_at = utcnow()

    @retryable()
    def submit_transaction():
        return web3.eth.send_raw_transaction(signed_transaction)

    try:
        transaction_hash = submit_transaction()
    except Exception as e:
        with DBSession.begin() as dbsession:
            reward = dbsession.query(Reward).filter_by(id=reward_id).one()
            logger.error('Error sending reward %s: %s', reward, e)
            reward.status = RewardStatus.error_sending
        raise

    with DBSession.begin() as dbsession:
        reward = dbsession.query(Reward).filter_by(id=reward_id).one()
        if reward.status != RewardStatus.sending:
            logger.warning('Invalid status for reward %s, expected sending', reward)
        reward.status = RewardStatus.sent
        reward.reward_transaction_hash = transaction_hash.hex()

    return transaction_hash


def confirm_rewards(
    web3: Web3,
    transaction_hashes: List[HexBytes],
    DBSession: sessionmaker,
):
    """
    Wait (sequentially) for all given transactions and confirm in DB
    """
    for transaction_hash in transaction_hashes:
        logger.info('Waiting for transaction %s...', transaction_hash)
        receipt = web3.eth.wait_for_transaction_receipt(transaction_hash, timeout=256, poll_latency=1)
        with DBSession.begin() as dbsession:
            reward = dbsession.query(Reward).filter_by(reward_transaction_hash=transaction_hash.hex()).one_or_none()
            if not reward:
                logger.error('Reward with tx hash %s not found', transaction_hash.hex())
                continue
            if reward.status != RewardStatus.sent:
                logger.warning('Invalid status for reward %s, expected sent', reward)
            if receipt.status:
                logger.info('Confirmed reward %s', reward)
                reward.status = RewardStatus.confirmed
            else:
                logger.info('Reward transaction failed! %s %s', transaction_hash.hex(), reward)
                reward.status = RewardStatus.error_confirming
