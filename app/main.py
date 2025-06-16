from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import cpas, uploads

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="SuperCPE v2 - Simplified CPA Compliance Tracking"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cpas.router)
app.include_router(uploads.router)

@app.get("/")
async def root():
    return {
        "message": "SuperCPE v2 API",
        "version": settings.api_version,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
