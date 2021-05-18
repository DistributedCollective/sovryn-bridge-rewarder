from setuptools import setup, find_packages

setup(
    name='sovryn_bridge_rewarder',
    version='0.0.1',
    url='',
    author='Sovryn',
    packages=find_packages(exclude=['tests', 'tests*']),
    package_data={'': [
        'abi/*.json',
    ]},
    install_requires=[
        'web3',
        'hexbytes',
        'eth_account',
        'eth_typing',
        'eth_utils',
        'sqlalchemy',
        'click',
        'justpy',
        'sentry-sdk',
    ],
    extras_require={
        'dev': [
            # Testing
            'pytest',

            # Easier command-line experience
            'ipython',
            'ipdb',
        ]
    },
    entry_points={
        'console_scripts': [
            'sovryn_bridge_rewarder=sovryn_bridge_rewarder.cli:main',
        ]
    },
)
