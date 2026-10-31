from fastapi import FastAPI
from pydantic import BaseModel

from citehop.health import service_status

app = FastAPI(title="CiteHop", version="0.1.0")


class Health(BaseModel):
    status: str
    services: dict[str, str]


@app.get("/api/v1/health", response_model=Health)
def health():
    # HTTP 200 means the API is alive; readiness is explicit per service.
    return Health(status="ok", services=service_status())
