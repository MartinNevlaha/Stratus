"""Starlette app factory with lifespan for database management."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from stratus.memory.database import Database
from stratus.orchestration.coordinator import SpecCoordinator
from stratus.orchestration.models import TeamConfig
from stratus.retrieval.embed_cache import EmbedCache
from stratus.retrieval.unified import UnifiedRetriever
from stratus.server.routes_memory import routes as memory_routes
from stratus.server.routes_retrieval import routes as retrieval_routes
from stratus.server.routes_session import routes as session_routes
from stratus.server.routes_system import routes as system_routes


def create_app(
    db_path: str = ":memory:",
    learning_db_path: str | None = None,
) -> Starlette:
    """Create a Starlette app with the given database path."""

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        from pathlib import Path

        from stratus.learning.config import load_learning_config
        from stratus.learning.database import LearningDatabase
        from stratus.learning.watcher import ProjectWatcher
        from stratus.orchestration.delivery_config import load_delivery_config
        from stratus.retrieval.config import DevRagConfig, load_retrieval_config
        from stratus.retrieval.devrag import DevRagClient
        from stratus.retrieval.governance_store import GovernanceStore
        from stratus.retrieval.vexor import VexorClient
        from stratus.session.config import get_data_dir

        app.state.db = Database(db_path)
        app.state.embed_cache = EmbedCache()

        # Governance store for DevRag
        gov_db_path = str(get_data_dir() / "governance.db")
        app.state.governance_store = GovernanceStore(gov_db_path)
        devrag_client = DevRagClient(
            config=DevRagConfig(enabled=True),
            store=app.state.governance_store,
            project_root=str(Path.cwd().resolve()),
        )
        ai_framework_path = Path.cwd() / ".ai-framework.json"
        retrieval_config = load_retrieval_config(ai_framework_path)
        vexor_client = VexorClient(config=retrieval_config.vexor)
        app.state.retriever = UnifiedRetriever(
            vexor=vexor_client,
            devrag=devrag_client,
            config=retrieval_config,
        )

        # Orchestration subsystem — delivery or spec based on config
        session_dir = (
            Path(
                os.environ.get("AI_FRAMEWORK_DATA_DIR", str(Path.home() / ".ai-framework" / "data"))
            )
            / "sessions"
            / "default"
        )
        session_dir.mkdir(parents=True, exist_ok=True)
        delivery_config = load_delivery_config()
        if delivery_config.enabled:
            from stratus.orchestration.delivery_coordinator import DeliveryCoordinator

            app.state.delivery_coordinator = DeliveryCoordinator(
                session_dir=session_dir,
                config=delivery_config,
            )
            app.state.coordinator = None
        else:
            app.state.coordinator = SpecCoordinator(
                session_dir=session_dir,
                project_root=Path.cwd(),
                api_url=f"http://127.0.0.1:{os.environ.get('AI_FRAMEWORK_PORT', '41777')}",
            )
            app.state.delivery_coordinator = None
        app.state.team_config = TeamConfig()

        # Learning subsystem
        ai_framework_path = Path.cwd() / ".ai-framework.json"
        app.state.learning_config = load_learning_config(ai_framework_path)
        resolved_learning_path = learning_db_path or str(get_data_dir() / "learning.db")
        app.state.learning_db = LearningDatabase(resolved_learning_path)
        app.state.learning_watcher = ProjectWatcher(
            config=app.state.learning_config,
            db=app.state.learning_db,
            project_root=Path.cwd(),
        )

        # Skills and rules subsystem
        from stratus.rule_engine.index import RulesIndex
        from stratus.skills.registry import SkillRegistry

        project_root = Path.cwd()
        app.state.skill_registry = SkillRegistry(
            skills_dir=project_root / ".claude" / "skills",
            agents_dir=project_root / ".claude" / "agents",
        )
        app.state.rules_index = RulesIndex(project_root=project_root)

        yield

        app.state.governance_store.close()
        app.state.learning_db.close()
        app.state.embed_cache.close()
        app.state.db.close()

    from stratus.server.routes_analytics import routes as analytics_routes
    from stratus.server.routes_dashboard import routes as dashboard_routes
    from stratus.server.routes_delivery import routes as delivery_routes
    from stratus.server.routes_learning import routes as learning_routes
    from stratus.server.routes_orchestration import routes as orchestration_routes
    from stratus.server.routes_skills import routes as skills_routes

    static_dir = Path(__file__).parent / "static"
    app = Starlette(
        routes=(
            system_routes
            + memory_routes
            + session_routes
            + retrieval_routes
            + learning_routes
            + analytics_routes
            + orchestration_routes
            + delivery_routes
            + skills_routes
            + dashboard_routes
            + [Mount("/dashboard/static", StaticFiles(directory=str(static_dir)))]
        ),
        lifespan=lifespan,
    )
    return app
