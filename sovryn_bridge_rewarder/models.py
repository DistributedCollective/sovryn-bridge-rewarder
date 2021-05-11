from sqlalchemy import Column, Text, Integer, BigInteger, DateTime, Enum, Numeric
from sqlalchemy.ext.declarative import declarative_base
from .utils import utcnow


Base = declarative_base()


class BlockInfo(Base):
    __tablename__ = 'block_info'
    key = Column(Text, primary_key=True)
    block_number = Column(Integer, nullable=False)

    def __repr__(self):
        return f'<LastProcessedBlock({self.block_number})>'


class RewardStatus(Enum):
    queued = 'queued'
    sending = 'sending'
    sent = 'sent'
    confirmed = 'confirmed'
    error_sending = 'error_sending'
    error_confirming = 'error_confirming'


class Reward(Base):
    __tablename__ = 'reward'

    id = Column(Integer, primary_key=True)
    status = Column(Text, nullable=False)  # could be enum

    _reward_rbtc_wei = Column('reward_rbtc_wei', Text, nullable=False)  # Text for sqlite support...

    user_address = Column(Text, nullable=False, index=True)

    # These are mostly for debugging
    deposit_side_token_address = Column(Text, nullable=False)
    deposit_side_token_symbol = Column(Text, nullable=False)
    deposit_main_token_address = Column(Text, nullable=False)
    _deposit_amount_minus_fees_wei = Column('deposit_amount_minus_fees_wei', Text, nullable=False)  # Text for sqlite
    deposit_log_index = Column(Integer, nullable=False)
    deposit_block_hash = Column(Text, nullable=False)
    deposit_transaction_hash = Column(Text, nullable=False, index=True)

    # Maybe not needed
    #deposit_token_address = Column(Text, nullable=False)

    reward_transaction_hash = Column(Text, nullable=True)
    reward_transaction_nonce = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def reward_rbtc_wei(self) -> int:
        return int(self._reward_rbtc_wei)

    @reward_rbtc_wei.setter
    def reward_rbtc_wei(self, value: int):
        self._reward_rbtc_wei = str(value)

    @property
    def deposit_amount_minus_fees_wei(self) -> int:
        return int(self._deposit_amount_minus_fees_wei)

    @deposit_amount_minus_fees_wei.setter
    def deposit_amount_minus_fees_wei(self, value: int):
        self._deposit_amount_minus_fees_wei = str(value)

    def __repr__(self):
        return f'<Reward(to={self.user_address})>'
