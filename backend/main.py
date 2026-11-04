from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def read_root():
    return {"Welcome to": "Rootmap"}

@app.get("/init-request/")
async def read_request(timer_status: int, token_value: str):
    return {"timer_status": timer_status, "token_value": token_value}
