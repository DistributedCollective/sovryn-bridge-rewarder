from sqlalchemy import Column, Text, Integer, BigInteger, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class BlockInfo(Base):
    __tablename__ = 'block_info'
    key = Column(Text, primary_key=True)
    block_number = Column(Integer, nullable=False)

    def __repr__(self):
        return f'<LastProcessedBlock({self.block_number})>'


class RewardStatus(Enum):
    queued = 'queued'
    sent = 'sent'
    confirmed = 'confirmed'
    error = 'error'


class Reward(Base):
    __tablename__ = 'reward'

    id = Column(Integer, primary_key=True)
    status = Column(Text, nullable=False)  # could be enum

    reward_rbtc_wei = Column(Integer, nullable=False)

    user_address = Column(Text, nullable=False)

    # These are mostly for debugging
    deposit_side_token_address = Column(Text, nullable=False)
    deposit_side_token_symbol = Column(Text, nullable=False)
    deposit_main_token_address = Column(Text, nullable=False)
    deposit_amount_minus_fees = Column(Integer, nullable=False)
    deposit_log_index = Column(Text, nullable=False)
    deposit_block_hash = Column(Text, nullable=False)
    deposit_tx_hash = Column(Text, nullable=False)

    # Maybe not needed
    #deposit_token_address = Column(Text, nullable=False)

    reward_tx_hash = Column(Text, nullable=True)

    def __repr__(self):
        return f'<Reward(to={self.user_address})>'
