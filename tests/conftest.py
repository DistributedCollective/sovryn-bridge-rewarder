import os
import pytest
from sqlalchemy.orm.session import sessionmaker, Session
from sovryn_bridge_rewarder.main import init_sqlalchemy


#TEST_DB_PATH = os.path.abspath(
#    os.path.join(
#        os.path.dirname(__file__),
#        '..',
#        'tests.sqlite3',
#    )
#)
#TEST_DB_URL = f'sqlite:///{TEST_DB_PATH}'
TEST_DB_URL = f'sqlite://'  # in-memory database


@pytest.fixture()
def database() -> sessionmaker:
    #if os.path.exists(TEST_DB_PATH):
    #    os.unlink(TEST_DB_PATH)
    return init_sqlalchemy(TEST_DB_URL, create_models=True)


@pytest.fixture()
def dbsession(database) -> Session:
    with database.begin() as sess:
        yield sess
