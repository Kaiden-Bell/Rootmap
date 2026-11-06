from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
async def read_root():
    return {"Welcome to": "Rootmap"}

@app.get("/init-request/")
async def read_request(timer_status: int, token_value: str):
    return {"timer_status": timer_status, "token_value": token_value}

@app.post("/client-report")
async def display_data(payload: dict):
    # 1. VIEW DATA ON SERVER SIDE: This prints the incoming JSON to your console
    print("\n================ RECEIVED POST DATA ================")
    print(payload)
    print("====================================================\n")
