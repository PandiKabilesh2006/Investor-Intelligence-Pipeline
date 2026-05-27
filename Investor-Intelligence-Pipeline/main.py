from fastapi import FastAPI

app = FastAPI(
    title="Investor Intelligence Pipeline",
    version="1.0.0"
)

@app.get("/")
def home():
    return {
        "message": "Investor Intelligence Pipeline Running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }