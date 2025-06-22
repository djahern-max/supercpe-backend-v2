from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import cpas, uploads, compliance, time_windows, payments, auth, ce_broker
from fastapi.routing import APIRoute
from fastapi.responses import PlainTextResponse

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="SuperCPE v2 - Simplified CPA Compliance Tracking",
)

# CORS middleware for React frontend - UPDATED TO INCLUDE PRODUCTION
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "https://nh.supercpe.com",  # Production frontend
        "https://*.supercpe.com",  # Any supercpe.com subdomain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cpas.router)
app.include_router(uploads.router)
app.include_router(compliance.router)
app.include_router(time_windows.router)
app.include_router(payments.router)
app.include_router(auth.router)
app.include_router(ce_broker.router)


@app.get("/routes-simple", response_class=PlainTextResponse)
async def get_routes_simple():
    """
    Returns a concise list of all routes with their paths and methods.
    """
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            methods = ", ".join(route.methods)
            routes.append(f"{methods}: {route.path}")

    return "\n".join(routes)


@app.get("/")
async def root():
    return {
        "message": "SuperCPE v2 API",
        "version": settings.api_version,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
