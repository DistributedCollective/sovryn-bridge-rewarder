import logging
from time import sleep
from typing import Union, Type

import sqlalchemy
from eth_typing import Address, AnyAddress
from sqlalchemy.orm import sessionmaker, Session
from web3 import Web3
from web3.contract import Contract

from .deposits import get_deposits
from .utils import address, load_abi
from .models import Base, BlockInfo

logger = logging.getLogger(__name__)
BRIDGE_ABI = load_abi('Bridge.json')


def run_rewarder(
    *,
    bridge_address: Address,
    rpc_url: str,
    default_start_block: int,
    required_block_confirmations: int,
    db_url: str = 'sqlite:///db.sqlite3',  # TODO: better default or no default
    sleep_seconds: int = 30,
):
    logger.info('Starting rewarder')
    DBSession = init_sqlalchemy(db_url, create_models=True)

    web3 = Web3(Web3.HTTPProvider(rpc_url))
    logger.info('Connected to chain %s, rpc url: %s', web3.eth.chain_id, rpc_url)

    bridge_contract = get_bridge_contract(
        bridge_address=bridge_address,
        web3=web3
    )

    with DBSession.begin() as dbsession:
        start_block = get_start_block(dbsession, default_start_block)

    while True:
        current_block = web3.eth.get_block_number()
        to_block = current_block - required_block_confirmations
        logger.info('Starting round from %s to %s', start_block, to_block)

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
        with DBSession.begin() as dbsession:
            # TODO: queue rewards
            last_processed_block = to_block
            update_last_processed_block(dbsession, last_processed_block)
            start_block = last_processed_block + 1
        logger.info('Round complete, sleeping %s s', sleep_seconds)
        sleep(sleep_seconds)


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
