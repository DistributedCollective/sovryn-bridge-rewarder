import os
from getpass import getpass
from dataclasses import dataclass, field, fields
from decimal import Decimal
from typing import Dict, NewType

from eth_account import Account
from eth_account.signers.base import BaseAccount
from eth_utils import is_hex_address

RewardThresholdTable = NewType('RewardThresholdTable', Dict[str, Decimal])


@dataclass()
class Config:
    bridge_address: str
    rpc_url: str
    db_url: str
    default_start_block: int
    required_block_confirmations: int
    deposit_fee_percentage: Decimal
    reward_rbtc: Decimal
    reward_thresholds: RewardThresholdTable
    account: BaseAccount = field(repr=False)
    sleep_seconds: int = 30

    def validate(self):
        for field in fields(self):
            type_ = dict if field.name == 'reward_thresholds' else field.type
            value = getattr(self, field.name, None)
            if value is None:
                raise ValueError(f'missing value for {field.name}')
            if not isinstance(value, type_):
                raise ValueError(f'expected {field.name} to be of type {type_}, was {type(value)}')

        if not is_hex_address(self.bridge_address):
            raise ValueError(f'bridge_address {self.bridge_address!r} is not a valid hex address')

        if self.reward_rbtc > Decimal('0.1'):
            raise ValueError(
                f'RBTC reward amount {str(self.reward_rbtc)} is dangerously high. '
                'Did you accidentally pass in the amount as WEI instead of decimal?'
            )
        if self.deposit_fee_percentage > Decimal('0.1'):
            raise ValueError(
                f'Invalid deposit fee percentage {str(self.deposit_fee_percentage)} '
                'Cannot be over 10% (0.1).'
            )

        if not self.reward_thresholds:
            raise ValueError(
                'Empty reward_thresholds -- no rewards would be given'
            )
        for key, value in self.reward_thresholds.items():
            if not isinstance(key, str):
                raise ValueError('expected reward_threshold keys to be strings (token symbols)')
            if not isinstance(value, Decimal):
                raise ValueError('expected reward_threshold values to be Decimals (amounts)')


def load_from_json(json_dict) -> Config:
    account = load_account_from_json(json_dict)
    try:
        raw_reward_thresholds = json_dict['rewardThresholds'].items()
        reward_thresholds = RewardThresholdTable({
            k: Decimal(v)
            for (k, v) in raw_reward_thresholds
        })
        config = Config(
            bridge_address=json_dict['bridgeAddress'],
            rpc_url=json_dict['rpcUrl'],
            db_url=json_dict['dbUrl'],
            default_start_block=json_dict['defaultStartBlock'],
            required_block_confirmations=json_dict['requiredBlockConfirmations'],
            deposit_fee_percentage=Decimal(json_dict['depositFeePercentage']),
            reward_rbtc=Decimal(json_dict['rewardRbtc']),
            reward_thresholds=reward_thresholds,
            sleep_seconds=json_dict.get('sleepSeconds', Config.sleep_seconds),
            account=account,
        )
    except KeyError as e:
        raise ValueError(f'missing required configuration option: {e.args[0]}')
    config.validate()
    return config


def load_account_from_json(json_dict) -> BaseAccount:
    if 'keyStoreFile' in json_dict:
        path = json_dict['keyStoreFile']
        secrets_type = 'keyStore'
    elif 'privateKeyFile' in json_dict:
        path = json_dict['privateKeyFile']
        secrets_type = 'privateKey'
    else:
        raise ValueError('specify either keyStoreFile or privateKeyFile in config')

    if not os.path.exists(path):
        raise ValueError(f'{secrets_type} path {path} not found')
    with open(path) as f:
        raw_data = f.read().strip()
    if secrets_type == 'privateKey':
        private_key = raw_data
    else:
        # TODO: this now prompts here, making config potentially interactive...
        password = getpass(f'Enter keystore password for {path}: ')
        private_key = Account.decrypt(raw_data, password)
    return Account.from_key(private_key)
