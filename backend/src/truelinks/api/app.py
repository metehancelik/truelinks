from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, cast

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from truelinks.api.schemas import (
    FieldDecisionIn,
    LeaseOut,
    RuleDecisionIn,
    SampleOut,
    UnitDetailOut,
    UnitOut,
)
from truelinks.modules.lease import service
from truelinks.modules.lease.demo import register_demo_leases
from truelinks.modules.lease.documents import UnreadableDocumentError, read_document
from truelinks.modules.lease.models import LeaseRow
from truelinks.modules.lease.rules import Rule, load_ruleset
from truelinks.modules.unit.models import UnitRow, list_units, seed_units
from truelinks.modules.unit.records import load_units
from truelinks.platform.db import Base, make_engine, make_session_factory
from truelinks.platform.llm.config import LLMSettings
from truelinks.platform.llm.openai_compatible import OpenAICompatibleProvider
from truelinks.platform.llm.stub import StubProvider
from truelinks.platform.llm.types import LLMProvider
from truelinks.platform.settings import AppSettings


@dataclass(frozen=True)
class Container:
    """Everything a request needs, built once at start-up."""

    settings: AppSettings
    sessions: sessionmaker[Session]
    llm: LLMProvider
    ruleset: list[Rule]


def build_llm(settings: AppSettings) -> LLMProvider:
    if settings.llm_provider == "stub":
        return register_demo_leases(StubProvider())
    return OpenAICompatibleProvider(LLMSettings())


def create_app(settings: AppSettings | None = None, llm: LLMProvider | None = None) -> FastAPI:
    settings = settings or AppSettings()
    engine = make_engine(settings.database_url)
    container = Container(
        settings=settings,
        sessions=make_session_factory(engine),
        llm=llm or build_llm(settings),
        ruleset=load_ruleset(settings.data_dir / "owner_ruleset.json"),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        Base.metadata.create_all(engine)
        with container.sessions() as session:
            seed_units(session, settings.tenant_id, load_units(settings.data_dir / "units.json"))
        yield

    app = FastAPI(title="Lease and property-issue agents", lifespan=lifespan)
    app.state.container = container
    _add_routes(app)
    return app


def _container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


def _session(container: Annotated[Container, Depends(_container)]) -> Iterator[Session]:
    with container.sessions() as session:
        yield session


Ctx = Annotated[Container, Depends(_container)]
Db = Annotated[Session, Depends(_session)]


def _lease(session: Session, container: Container, lease_id: str) -> LeaseRow:
    lease = session.get(LeaseRow, lease_id)
    if lease is None or lease.tenant_id != container.settings.tenant_id:
        raise HTTPException(404, "Lease not found.")
    return lease


def _lease_out(session: Session, container: Container, lease: LeaseRow) -> LeaseOut:
    return LeaseOut.of(lease, service.current_rules(session, lease, container.ruleset))


async def _process(container: Container, lease_id: str) -> None:
    with container.sessions() as session:
        await service.process_lease(session, container.llm, container.ruleset, lease_id)


def _add_routes(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Liveness probe for the container platform."""
        return {"status": "ok"}

    @app.get("/units")
    def units(session: Db, container: Ctx) -> list[UnitOut]:  # pyright: ignore[reportUnusedFunction]
        return [UnitOut.of(row) for row in list_units(session, container.settings.tenant_id)]

    @app.get("/units/{unit_id}")
    def unit(unit_id: str, session: Db, container: Ctx) -> UnitDetailOut:  # pyright: ignore[reportUnusedFunction]
        """A unit with every lease linked to it: the one place an owner looks."""
        row = session.get(UnitRow, unit_id)
        if row is None or row.tenant_id != container.settings.tenant_id:
            raise HTTPException(404, "Unit not found.")
        leases = session.scalars(
            select(LeaseRow).where(LeaseRow.unit_id == unit_id).order_by(LeaseRow.created_at.desc())
        )
        return UnitDetailOut(
            unit=UnitOut.of(row),
            leases=[_lease_out(session, container, lease) for lease in leases],
        )

    @app.get("/leases")
    def leases(session: Db, container: Ctx) -> list[LeaseOut]:  # pyright: ignore[reportUnusedFunction]
        rows = session.scalars(
            select(LeaseRow)
            .where(LeaseRow.tenant_id == container.settings.tenant_id)
            .order_by(LeaseRow.created_at.desc())
        )
        return [_lease_out(session, container, lease) for lease in rows]

    @app.get("/leases/{lease_id}")
    def lease(lease_id: str, session: Db, container: Ctx) -> LeaseOut:  # pyright: ignore[reportUnusedFunction]
        return _lease_out(session, container, _lease(session, container, lease_id))

    @app.get("/samples/leases")
    def samples(container: Ctx) -> list[SampleOut]:  # pyright: ignore[reportUnusedFunction]
        files = sorted((container.settings.samples_dir / "leases").glob("*.txt"))
        return [SampleOut(name=file.name) for file in files]

    @app.post("/leases", status_code=202)
    async def upload_lease(  # pyright: ignore[reportUnusedFunction]
        background: BackgroundTasks,
        session: Db,
        container: Ctx,
        file: UploadFile | None = None,
        sample: Annotated[str | None, Form()] = None,
    ) -> LeaseOut:
        """Store the document and return at once; the agent works in the background.

        A local model needs a minute or two per lease, far too long to hold a
        request open. The client polls the lease until it leaves PROCESSING.
        """
        if file is not None:
            filename, content = file.filename or "lease", await file.read()
        elif sample is not None:
            path = container.settings.samples_dir / "leases" / sample
            # A bare file name only: no way out of the samples folder.
            if Path(sample).name != sample or not path.is_file():
                raise HTTPException(404, "Sample not found.")
            filename, content = path.name, path.read_bytes()
        else:
            raise HTTPException(422, "Send a file or name a sample.")

        try:
            text = read_document(filename, content)
        except UnreadableDocumentError as error:
            raise HTTPException(422, str(error)) from error

        row = service.create_lease(session, container.settings.tenant_id, filename, text)
        background.add_task(_process, container, row.id)
        return _lease_out(session, container, row)

    @app.post("/leases/{lease_id}/fields/{name}/decision")
    def decide_field(  # pyright: ignore[reportUnusedFunction]
        lease_id: str, name: str, body: FieldDecisionIn, session: Db, container: Ctx
    ) -> LeaseOut:
        row = _lease(session, container, lease_id)
        _apply(lambda: service.decide_field(session, row, name, body.decision, body.value))
        return _lease_out(session, container, row)

    @app.post("/leases/{lease_id}/rules/{rule_id}/decision")
    def decide_rule(  # pyright: ignore[reportUnusedFunction]
        lease_id: str, rule_id: str, body: RuleDecisionIn, session: Db, container: Ctx
    ) -> LeaseOut:
        row = _lease(session, container, lease_id)
        _apply(lambda: service.decide_rule(session, row, rule_id, body.decision))
        return _lease_out(session, container, row)

    @app.post("/leases/{lease_id}/activate")
    def activate(lease_id: str, session: Db, container: Ctx) -> LeaseOut:  # pyright: ignore[reportUnusedFunction]
        row = _lease(session, container, lease_id)
        _apply(lambda: service.activate_lease(session, row, container.ruleset))
        return _lease_out(session, container, row)

    @app.post("/leases/{lease_id}/reject")
    def reject(lease_id: str, session: Db, container: Ctx) -> LeaseOut:  # pyright: ignore[reportUnusedFunction]
        row = _lease(session, container, lease_id)
        _apply(lambda: service.reject_lease(session, row))
        return _lease_out(session, container, row)


def _apply(action: Callable[[], None]) -> None:
    """Run a state change; a refusal becomes a 409 with the reason."""
    try:
        action()
    except service.LeaseActionError as error:
        raise HTTPException(409, str(error)) from error


app = create_app()
