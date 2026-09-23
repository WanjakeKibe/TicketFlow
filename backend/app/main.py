from fastapi import FastAPI

app = FastAPI(
    title="Ticketflw API",
    version="1.0.0",
    description="Multi-tenant Field Service & Work Management Platform",
)


@app.get("/")
def root():
    return {
        "message": "Welcome to Ticketflw API",
        "version": "v1",
    }


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy"
    }
