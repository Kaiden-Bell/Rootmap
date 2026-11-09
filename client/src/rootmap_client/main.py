import os
import argparse

import httpx
from scripts.host import SystemCollector

argument_parser = argparse.ArgumentParser(description="Rootmap Client")
argument_parser.add_argument("--head-ip", type=str, default="127.0.0.1", help="IP address of the Rootmap head node")
argument_parser.add_argument("--head-port", type=int, default=5432, help="Port of the Rootmap head node")

args = argument_parser.parse_args()
HEAD_NODE_URL = f"http://{args.head_ip}:{args.head_port}"

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
