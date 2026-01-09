"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings, log_configuration
from app.api.routes.langgraph_routes import router as langgraph_router
from app.api.routes.hitl_routes import router as hitl_router
from app.api.routes.cache_routes import router as cache_router
from app.api.routes.plan_routes import router as plan_router
from app.api.routes.session_routes import router as session_router

# Lazy import of optional dependencies
try:
    from app.api import router as api_router
    API_ROUTER_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"API router not available (missing dependencies): {e}")
    API_ROUTER_AVAILABLE = False
    api_router = None

try:
    from app.db import init_db
    DB_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Database not available (missing dependencies): {e}")
    DB_AVAILABLE = False
    init_db = None

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Log configuration after logging is set up
log_configuration()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting up Coding Agent API...")
    logger.info(f"Reasoning model endpoint: {settings.vllm_reasoning_endpoint}")
    logger.info(f"Coding model endpoint: {settings.vllm_coding_endpoint}")

    # Initialize database (if available)
    if DB_AVAILABLE and init_db:
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")

        # Initialize SessionStore with database persistence for multi-user support
        try:
            from app.db.database import get_db_context
            from app.core.session_store import init_session_store_with_db
            init_session_store_with_db(get_db_context)
            logger.info("SessionStore initialized with database persistence")
        except ImportError as e:
            logger.warning(f"SessionStore database persistence not available: {e}")
    else:
        logger.warning("Database initialization skipped (not available)")

    yield
    logger.info("Shutting down Coding Agent API...")


# Create FastAPI app
app = FastAPI(
    title="Coding Agent API",
    description="Full-stack coding agent with Microsoft Agent Framework and vLLM",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
if API_ROUTER_AVAILABLE and api_router:
    app.include_router(api_router, prefix="/api")
    logger.info("✅ Standard API routes registered")
else:
    logger.warning("⚠️  Standard API routes not registered (dependencies missing)")

# Always include LangGraph routes (no external dependencies)
app.include_router(langgraph_router, prefix="/api")
logger.info("✅ LangGraph routes registered at /api/langgraph")

# Include HITL routes
app.include_router(hitl_router, prefix="/api")
logger.info("✅ HITL routes registered")

# Include Cache management routes
app.include_router(cache_router, prefix="/api")
logger.info("✅ Cache management routes registered at /api/cache")

# Include Plan Mode routes (Phase 5)
app.include_router(plan_router, prefix="/api")
logger.info("✅ Plan Mode routes registered at /api/plan")

# Include Session routes (for remote client)
app.include_router(session_router, prefix="/api")
logger.info("✅ Session routes registered at /api/sessions")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Coding Agent API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Enhanced health check endpoint with component status."""
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "components": {}
    }

    # Check LangGraph workflow
    try:
        from app.agent.langgraph.unified_workflow import unified_workflow
        health_status["components"]["langgraph_workflow"] = {
            "status": "operational",
            "graph_compiled": unified_workflow.graph is not None,
            "tools_available": len(unified_workflow.tools)
        }
    except Exception as e:
        health_status["components"]["langgraph_workflow"] = {
            "status": "error",
            "error": str(e)
        }

    # Check filesystem tools
    try:
        from app.agent.langgraph.tools.filesystem_tools import FILESYSTEM_TOOLS
        health_status["components"]["filesystem_tools"] = {
            "status": "operational",
            "tools_count": len(FILESYSTEM_TOOLS),
            "tools": [tool.name for tool in FILESYSTEM_TOOLS]
        }
    except Exception as e:
        health_status["components"]["filesystem_tools"] = {
            "status": "error",
            "error": str(e)
        }

    # Check routes
    langgraph_routes = [r.path for r in app.routes if '/langgraph' in r.path]
    health_status["components"]["langgraph_routes"] = {
        "status": "operational",
        "count": len(langgraph_routes),
        "endpoints": langgraph_routes
    }

    # Overall status
    failed_components = [
        name for name, comp in health_status["components"].items()
        if comp.get("status") == "error"
    ]

    if failed_components:
        health_status["status"] = "degraded"
        health_status["failed_components"] = failed_components

    return health_status
