from decimal import Decimal

from sovryn_bridge_rewarder.config import Config, RewardThresholdTable, load_from_json


EXAMPLE_CONFIG_JSON = {
    "bridgeAddress": "0x8e7199d5f496ea862492f4f983a1627d723328fd",
    "rpcUrl": "https://testnet.sovryn.app/rpc",
    "dbUrl": "sqlite:///db.sqlite3",
    "defaultStartBlock": 1784453,
    "requiredBlockConfirmations": 2,
    "depositFeePercentage": "0.002",
    "rewardRbtc": "0.001",
    "rewardThresholds": {
        "DAIbs": "100.0",
        "ETHbs": "0.25"
    }
}


def test_load_from_json():
    config = load_from_json(EXAMPLE_CONFIG_JSON)
    assert isinstance(config, Config)
    assert config == Config(
        bridge_address="0x8e7199d5f496ea862492f4f983a1627d723328fd",
        rpc_url="https://testnet.sovryn.app/rpc",
        db_url="sqlite:///db.sqlite3",
        default_start_block=1784453,
        required_block_confirmations=2,
        deposit_fee_percentage=Decimal("0.002"),
        reward_rbtc=Decimal("0.001"),
        reward_thresholds=RewardThresholdTable({
            "DAIbs": Decimal("100.0"),
            "ETHbs": Decimal("0.25"),
        }),
    )
