import os

import httpx

HEAD_NODE_URL = os.environ.get("ROOTMAP_HEAD_URL", "http://127.0.0.1:8000")


def main():
    response = httpx.get(f"{HEAD_NODE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
