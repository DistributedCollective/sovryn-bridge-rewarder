Bridge Rewarder
===============

A bot that gives RBTC to the Sovryn Citizens who move tokens to RSK via the token bridge

Running
------

Add your keystore file to `./secrets/testnet_keystore.json`, and then run:

```
python3.8 -m venv venv
source ./venv/bin/activate
pip install -r requirements-dev.txt
pip install -e '.[dev]'
sovryn_bridge_rewarder config_testnet.json
```

Edit the config file as seen fit, or create your own.

The build process needs some libraries on the machine. For ubuntu:
```
sudo apt install build-essential python3-dev
sudo apt install libpq-dev  # if using postgresql
```

Tests
-----

After installation:
```
source ./venv/bin/activate
pytest
```

