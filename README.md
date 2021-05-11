Bridge Rewarder
===============

A bot that gives RBTC to the Sovryn Citizens who move tokens to RSK via the token bridge

Running
------

Add your keystore file to `./secrets/testnet_keystore.json`, and then run:

```
python3.8 -m venv venv
source ./venv/bin/activate
pip install -e .
sovryn_bridge_rewarder config_testnet.json
```

Edit the config file as seen fit, or create your own.

Tests
-----

```
source ./venv/bin/activate
pip install -e '.[dev]'
pytest
```

