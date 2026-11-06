import os
import httpx
from scripts.host import SystemCollector

HEAD_NODE_URL = os.environ.get("ROOTMAP_HEAD_URL", "http://127.0.0.1:8000")


def main():
    # response = httpx.get(f"{HEAD_NODE_URL}/")
    # print(f"Status: {response.status_code}")
    # print(f"Response: {response.json()}")
    system_info = generate_report()
    send_report(system_info)

def generate_report():
    collector = SystemCollector()
    system_info = collector.get_system_info()
    return system_info
    # print("System Information:")
    # for key, value in system_info.items():
    #     print(f"{key}: {value}")

def send_report(system_info):
    response = httpx.post(f"{HEAD_NODE_URL}/client-report", json=system_info)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    main()
