from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="BateaControl API",
    description="Sistema Municipal de Gestión de Bateas Comunitarias",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"sistema": "BateaControl", "estado": "operacional", "version": "1.0.0"}

@app.get("/api/health")
def health():
    return {"status": "ok"}
