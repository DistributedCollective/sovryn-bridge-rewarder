"""
Logic for queueing and sending rewards based on found deposits
Handles both DB and Web3 related logic.
"""
from decimal import Decimal
import logging

from sqlalchemy import func
from sqlalchemy.orm.session import Session

from .config import RewardThresholdTable
from .deposits import Deposit
from .models import Reward, RewardStatus


logger = logging.getLogger(__name__)


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

