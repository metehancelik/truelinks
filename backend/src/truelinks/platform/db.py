from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class of every table."""


def make_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        # One shared connection keeps an in-memory database alive across
        # sessions, and lets the background task use it from another thread.
        in_memory = ":memory:" in database_url or database_url == "sqlite://"
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if in_memory else None,
        )
    return create_engine(database_url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
