"""Main FastAPI application for Brandmark API."""

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from app.config import get_settings
from app.models import APIError
from app.database import init_db, close_db
from app.cache import init_redis, close_redis
from app.routers import availability, suggestions, discovery, providers, brand_intelligence, cost_intelligence, startup_intelligence, funding_correlation, market_intelligence, investor_reports, brand_dna, competitive_moat, subscriptions, integrations, domain_pricing, trademark_search, webhooks, monitoring, contact, check

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    logger.info("Starting Brandmark API")
    await init_db()
    await init_redis()
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Brandmark API")
    await close_db()
    await close_redis()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="The Bloomberg Terminal for Brand Intelligence - comprehensive brand investment analysis with cost optimization, funding correlation insights, and availability checking across 25+ platforms.",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files for frontend
    import os
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    if os.path.exists(frontend_dir):
        app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    # Include routers
    app.include_router(availability.router, prefix="/v1", tags=["availability"])
    app.include_router(suggestions.router, prefix="/v1", tags=["suggestions"])
    app.include_router(check.router, prefix="/v1", tags=["check"])
    app.include_router(discovery.router, prefix="/v1", tags=["discovery"])
    app.include_router(providers.router, prefix="/v1", tags=["providers"])
    app.include_router(brand_intelligence.router, prefix="/v1/brand-intelligence", tags=["brand-intelligence"])
    app.include_router(cost_intelligence.router, prefix="/v1/cost-intelligence", tags=["cost-intelligence"])
    app.include_router(domain_pricing.router, prefix="/v1/domain-pricing", tags=["domain-pricing"])
    app.include_router(trademark_search.router, prefix="/v1/trademark-search", tags=["trademark-search"])
    app.include_router(webhooks.router, prefix="/v1/webhooks", tags=["webhooks"])
    app.include_router(monitoring.router, prefix="/v1/monitoring", tags=["monitoring"])
    app.include_router(startup_intelligence.router, prefix="/v1/startup-intelligence", tags=["startup-intelligence"])
    app.include_router(funding_correlation.router, prefix="/v1/funding-correlation", tags=["funding-correlation"])
    app.include_router(market_intelligence.router, prefix="/v1/market-intelligence", tags=["market-intelligence"])
    app.include_router(investor_reports.router, prefix="/v1/investor-reports", tags=["investor-reports"])

    # Phase 3: Market Dominance - Revolutionary Features
    app.include_router(brand_dna.router, tags=["brand-dna"])
    app.include_router(competitive_moat.router, tags=["competitive-moat"])

    # Phase 4: Monetization - $50K MRR Features
    app.include_router(subscriptions.router, prefix="/v1/subscriptions", tags=["subscriptions"])
    app.include_router(integrations.router, prefix="/v1/integrations", tags=["integrations"])

    # Contact form
    app.include_router(contact.router, tags=["contact"])
    
    # Add main endpoints
    @app.get("/")
    async def root():
        """Root endpoint - serve frontend or API info."""
        frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
        index_path = os.path.join(frontend_dir, "index.html")

        # Serve frontend if available, otherwise API info
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            return {
                "message": "Brandmark API",
                "version": get_settings().app_version,
                "docs": "/docs",
                "status": "operational"
            }

    @app.options("/")
    async def root_options():
        """Handle CORS preflight for root endpoint."""
        return JSONResponse(
            content={"message": "OK"},
            headers={
                "access-control-allow-origin": "*",
                "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
                "access-control-allow-headers": "*",
                "access-control-allow-credentials": "true"
            }
        )

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        from app.database import check_database_health
        from app.cache import check_redis_health
        
        checks = {
            'database': await check_database_health(),
            'redis': await check_redis_health(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        healthy = all(checks[key] for key in ['database', 'redis'])
        status_code = 200 if healthy else 503
        
        return JSONResponse(
            content={
                'status': 'healthy' if healthy else 'unhealthy',
                'checks': checks
            },
            status_code=status_code
        )
    
    # Exception handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions with consistent error format."""
        error = APIError(
            error_code=f"HTTP_{exc.status_code}",
            message=exc.detail,
            timestamp=datetime.utcnow()
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error.model_dump(mode='json')
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors."""
        error = APIError(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            timestamp=datetime.utcnow()
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error.model_dump(mode='json')
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle validation errors."""
        error = APIError(
            error_code="VALIDATION_ERROR",
            message=str(exc),
            timestamp=datetime.utcnow()
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error.model_dump(mode='json')
        )
    
    return app


# Create the application instance
app = create_app()
