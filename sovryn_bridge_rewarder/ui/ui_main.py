from typing import List

import justpy as jp
import time
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from eth_utils import from_wei
from web3 import Web3

from ..config import Config
from ..models import BlockInfo, Reward


def run_ui(config: Config):
    engine = create_engine(config.db_url)
    Session = sessionmaker(bind=engine)
    web3 = Web3(Web3.HTTPProvider(config.rpc_url))

    rbtc_balance = ''

    page = jp.WebPage(
        title="Sovryn Bridge Rewarder",
        css=STYLES,
        delete_flag=False,
    )
    container = jp.Div(classes='container mx-auto', a=page)
    jp.H1(
        text='Sovryn Bridge Rewarder',
        classes='inline-block my-2 text-3xl font-extrabold text-gray-900 tracking-tight',
        a=container,
    )
    main_content = jp.Div(classes='my-2', a=container)

    meta_info = jp.Div(
        classes="my-2 p-4 bg-gray-200 rounded-md meta-info grid grid-flow-col auto-cols-max",
        a=main_content,
    )

    jp.H2(
        text="Latest given rewards",
        classes='text-2xl my-2 font-extrabold text-gray-900 tracking-tight',
        a=main_content,
    )
    reward_table = jp.parse_html("""
    <table class="table-auto text-left w-full">
        <thead>
            <tr>
                <th>id</th>
                <th>timestamp</th>
                <th>user address</th>
                <th>deposit (-fees)</th>
                <th>reward amount</th>
                <th>status</th>
            </tr>
        </thead>
    </table>
    """, a=main_content)
    reward_tbody = jp.Tbody(a=reward_table)

    async def update_page():
        nonlocal rbtc_balance
        try:
            rbtc_balance_wei = web3.eth.get_balance(config.account.address)
            rbtc_balance = from_wei(rbtc_balance_wei, 'ether')
        except Exception:
            pass
        with Session.begin() as dbsession:
            # TODO: the DB/Web3 calls should be async
            last_processed_block = dbsession.query(BlockInfo.block_number).filter_by(
                key='last_processed_block'
            ).scalar()
            latest_rewards = dbsession.query(Reward).order_by(
                Reward.created_at.desc()
            ).limit(50).all()

            meta_info.delete_components()
            column1 = jp.parse_html(
                f"""
                <div class="column">
                    <div class="item">
                        <div class="key">Last processed block</div>
                        <div class="value">{last_processed_block}</div>
                    </div>
                    <div class="item">
                        <div class="key">Rewarder account</div>
                        <div class="value">
                            <a href="{config.explorer_url}/address/{str(config.account.address).lower()}" target="_blank">
                                {str(config.account.address).lower()}
                            </a>
                        </div>
                    </div>
                    <div class="item">
                        <div class="key">Rewarder balance</div>
                        <div class="value">
                            {rbtc_balance} RBTC
                        </div>
                    </div>
                    <div class="item">
                        <div class="key">RPC Url</div>
                        <div class="value">
                            {config.rpc_url}
                        </div>
                    </div>
                </div>
                """,
                a=meta_info
            )
            for bridge_key, bridge_address in config.bridge_addresses.items():
                jp.parse_html(f"""
                    <div class="item">
                        <div class="key">Bridge address ({bridge_key})</div>
                        <div class="value">
                            <a href="{config.explorer_url}/address/{bridge_address}" target="_blank">
                                {bridge_address}
                            </a>
                        </div>
                    </div>
                """, a=column1)
            column2 = jp.Div(classes="column", a=meta_info)
            for symbol, threshold in config.reward_thresholds.items():
                item = jp.Div(classes="item", a=column2)
                jp.Div(
                    text=f'{symbol} threshold',
                    classes="key",
                    a=item
                )
                jp.Div(
                    text=str(threshold),
                    classes="value",
                    a=item
                )

            reward_tbody.delete_components()
            for reward in latest_rewards:
                rbtc_decimal = from_wei(reward.reward_rbtc_wei, 'ether')
                # TODO: store this in the model (without fees)
                deposit_amount_decimal = from_wei(reward.deposit_amount_minus_fees_wei, 'ether')

                status_html = str(reward.status)
                if reward.reward_transaction_hash:
                    status_html = (
                        f'<a target="_blank" href="{config.explorer_url}/tx/{reward.reward_transaction_hash}">'
                        f'{status_html}</a>'
                    )

                user_address_html = (
                    f'<a target="_blank" href="{config.explorer_url}/address/{reward.user_address}">'
                    f'{reward.user_address}</a>'
                )

                jp.parse_html(
                    f"""
                    <tr>
                        <td>{reward.id}</td>
                        <td>{reward.created_at}</td>
                        <td>{user_address_html}</td>
                        <td>{str(deposit_amount_decimal)} {reward.deposit_side_token_symbol}</td>
                        <td>{str(rbtc_decimal)} RBTC</td>
                        <td>{status_html}</td>
                    </tr>
                    """,
                    a=reward_tbody
                )

        jp.run_task(page.update())

    async def startup():
        async def updater():
            while True:
                await update_page()
                await asyncio.sleep(20)

        jp.run_task(updater())

    async def app():
        return page

    ui_config = config.ui or {}
    host = ui_config.get('host', "0.0.0.0")
    port = ui_config.get('port', 8000)
    jp.justpy(app, startup=startup, host=host, port=port)


STYLES = """
a {
    text-decoration: underline;
    color: #60A5FA;
}
a:hover {
    text-decoration: none;
}
table td, table th {
    padding: 0.25rem;
}
table tr:nth-child(even) {
    background-color: #F3F4F6;
}
.meta-info {
}
.meta-info .item .key {
    padding-right: 0.5rem;
    font-weight: bold;
    display: inline-block;
}
.meta-info .item .value {
    padding-right: 1rem;
    display: inline-block;
}
"""
