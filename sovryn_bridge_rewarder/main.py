import logging
from time import sleep
from typing import Dict, Optional, Union

import sqlalchemy
from eth_typing import AnyAddress
from sqlalchemy.orm import Session, sessionmaker
from web3 import Web3
from web3.contract import Contract

from .config import Config
from .deposits import get_deposits
from .models import Base, BlockInfo
from .rewards import queue_reward, send_queued_rewards
from .utils import address, load_abi

logger = logging.getLogger(__name__)
BRIDGE_ABI = load_abi('Bridge.json')


def run_rewarder(config: Config):
    logger.info('Starting rewarder')
    DBSession = init_sqlalchemy(config.db_url, create_models=True)

    web3 = Web3(Web3.HTTPProvider(config.rpc_url))
    logger.info('Connected to chain %s, rpc url: %s', web3.eth.chain_id, config.rpc_url)
    gas_price = web3.eth.gas_price
    logger.info('Gas price: %s (%s GWei)', gas_price, gas_price * 10**9 / 10**18)
    bridge_contracts = {}
    logger.info('Rewarder account is %s', config.account.address.lower())
    for k, v in config.bridge_addresses.items():
        logger.info('Bridge contract for %s is %s', k, v)
        bridge_contracts[k] = get_bridge_contract(
            bridge_address=v,
            web3=web3
        )

    # Clear any existing rewards
    send_queued_rewards(
        web3=web3,
        DBSession=DBSession,
        from_account=config.account,
    )

    with DBSession.begin() as dbsession:
        start_block = get_start_block(dbsession, config.default_start_block)
    while True:
        try:
            logger.info('Starting rewarder round')
            new_start_block = process_new_deposits(
                web3=web3,
                bridge_contracts=bridge_contracts,
                DBSession=DBSession,
                config=config,
                start_block=start_block,
            )
            if new_start_block:
                start_block = new_start_block

            send_queued_rewards(
                web3=web3,
                DBSession=DBSession,
                from_account=config.account,
            )
            logger.info('Round complete, sleeping %s s', config.sleep_seconds)
            sleep(config.sleep_seconds)
        except KeyboardInterrupt:
            logger.info('Quitting.')
            break
        except Exception:
            logger.exception('Error running rewarder, sleeping a bit and trying again.')
            sleep(60)


def process_new_deposits(
    *,
    web3: Web3,
    bridge_contracts: Dict[str, Contract],
    DBSession: sessionmaker,
    config: Config,
    start_block: int,
) -> Optional[int]:
    current_block = web3.eth.get_block_number()
    to_block = current_block - config.required_block_confirmations
    logger.info('Processing new deposits from %s to %s', start_block, to_block)

    if to_block < start_block:
        logger.info('to_block %s is smaller than start_block %s, not doing anything', to_block, start_block)
        return None

    deposits = []
    for bridge_key, bridge_contract in bridge_contracts.items():
        logger.info("Getting deposits for %s", bridge_key)
        bridge_deposits = get_deposits(
            bridge_contract=bridge_contract,
            web3=web3,
            from_block=start_block,
            to_block=to_block,
            fee_percentage=config.deposit_fee_percentage,
        )
        logger.info("Found %s deposits for %s", len(bridge_deposits), bridge_key)
        deposits.extend(bridge_deposits)

    with DBSession.begin() as dbsession:
        for deposit in deposits:
            queue_reward(
                deposit=deposit,
                dbsession=dbsession,
                reward_amount_rbtc=config.reward_rbtc,
                deposit_thresholds=config.reward_thresholds,
            )
        last_processed_block = to_block
        update_last_processed_block(dbsession, last_processed_block)
        start_block = last_processed_block + 1
        return start_block


def get_bridge_contract(*, bridge_address: Union[str, AnyAddress], web3: Web3) -> Contract:
    return web3.eth.contract(
        address=address(bridge_address),
        abi=BRIDGE_ABI
    )


def get_start_block(dbsession: Session, default: int) -> int:
    last_processed_block = dbsession.query(BlockInfo.block_number).filter_by(key='last_processed_block').scalar()
    if not last_processed_block:
        return default
    else:
        return last_processed_block + 1


def update_last_processed_block(dbsession: Session, block_number: int):
    block_info = dbsession.query(BlockInfo).filter_by(key='last_processed_block').one_or_none()
    if block_info:
        block_info.block_number = block_number
    else:
        block_info = BlockInfo(
            key='last_processed_block',
            block_number=block_number,
        )
        dbsession.add(block_info)


def init_sqlalchemy(db_url: str, *, create_models: bool = True) -> sessionmaker:
    logger.info('Connecting to database %s', db_url)
    engine = sqlalchemy.create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)
    if create_models:
        try:
            Base.metadata.create_all(engine)
        except Exception:
            pass
    return Session
