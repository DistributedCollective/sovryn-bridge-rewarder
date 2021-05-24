import os
from getpass import getpass
from dataclasses import dataclass, field, fields
from decimal import Decimal
from typing import Dict, NewType, Optional, Any

from eth_account import Account
from eth_account.signers.base import BaseAccount
from eth_utils import is_hex_address

BridgeAddressMap = NewType('RewardThresholdMap', Dict[str, str])
RewardThresholdMap = NewType('RewardThresholdMap', Dict[str, Decimal])
UIConfig = NewType('UIConfig', Dict[str, Any])


@dataclass()
class Config:
    bridge_addresses: BridgeAddressMap
    rpc_url: str
    db_url: str
    default_start_block: int
    required_block_confirmations: int
    reward_rbtc: Decimal
    reward_thresholds: RewardThresholdMap
    account: BaseAccount = field(repr=False)
    deposit_fee_percentage: Decimal = Decimal(0)
    sleep_seconds: int = 30
    explorer_url: str = 'https://explorer.rsk.co'
    sentry_dsn: str = ''
    ui: UIConfig = field(default_factory=dict)

    def validate(self):
        for field in fields(self):
            type_ = dict if field.name in ('bridge_addresses', 'reward_thresholds', 'ui') else field.type
            value = getattr(self, field.name, None)
            if value is None:
                raise ValueError(f'missing value for {field.name}')
            if not isinstance(value, type_):
                raise ValueError(f'expected {field.name} to be of type {type_}, was {type(value)}')

        for bridge_key, bridge_address in self.bridge_addresses.items():
            if not is_hex_address(bridge_address):
                raise ValueError(f'address {bridge_address!r} for bridge {bridge_key!r} is not a valid hex address')

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
    account = load_account_from_json(json_dict, password=os.getenv('KEYSTORE_PASSWORD'))
    try:
        raw_reward_thresholds = json_dict['rewardThresholds'].items()
        reward_thresholds = RewardThresholdMap({
            k: Decimal(v)
            for (k, v) in raw_reward_thresholds
        })
        config = Config(
            bridge_addresses=json_dict['bridgeAddresses'],
            rpc_url=json_dict['rpcUrl'],
            db_url=json_dict['dbUrl'],
            default_start_block=json_dict['defaultStartBlock'],
            required_block_confirmations=json_dict['requiredBlockConfirmations'],
            deposit_fee_percentage=Decimal(json_dict.get('depositFeePercentage', Config.deposit_fee_percentage)),
            reward_rbtc=Decimal(json_dict['rewardRbtc']),
            reward_thresholds=reward_thresholds,
            sleep_seconds=json_dict.get('sleepSeconds', Config.sleep_seconds),
            explorer_url=json_dict.get('explorerUrl', Config.explorer_url),
            account=account,
            sentry_dsn=json_dict.get('sentryDsn', Config.sentry_dsn),
            ui=json_dict.get('ui', Config.ui),
        )
    except KeyError as e:
        raise ValueError(f'missing required configuration option: {e.args[0]}')
    config.validate()
    return config


def load_account_from_json(json_dict, *, password=None) -> BaseAccount:
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
        if not password:
            password = getpass(f'Enter keystore password for {path}: ')
        private_key = Account.decrypt(raw_data, password)
    return Account.from_key(private_key)
