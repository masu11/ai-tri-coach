from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "AI Tri Coach backend running"}
