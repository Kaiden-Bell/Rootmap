import socket
import subprocess
import json
import os
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_PATH = "../result/"

class SystemCollector:
    def __init__(self):
        self.system_info = {
            "Operating System": "",
            "OS Release": "",
            "Hostname": socket.gethostname(),
            "IP Address": "", # socket.gethostbyname(socket.gethostname()) is 127.0.0.1
            "Subnet Mask": "", 
        }
        self.update_ip_info()
        self.update_os_info()
        self.update_subnet_mask()

        self.export_to_json(os.path.join(SCRIPT_DIR, EXPORT_PATH, "system_info.json"))

    def get_system_info(self):
        return self.system_info

    def update_ip_info(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 12345))
            self.system_info["IP Address"] = s.getsockname()[0]
            s.close()
        except Exception as e:
            self.system_info["IP Address"] = f"XXX.XXX.XXX.XXX"
            print(f"Error retrieving IP address: {e}")

    def update_subnet_mask(self):
        command = f"ip -o -f inet addr show | awk '/scope global/ {{print $4}}' | grep '{self.system_info['IP Address']}'"
        output = self.run_command(command)
        if output:
            self.system_info["Subnet Mask"] = output.split('/')[1]  # Extract the subnet mask

    def update_os_info(self):
        command = "cat /etc/os-release 2>/dev/null || true"
        output = self.run_command(command)
        if output:
            for line in output.split('\n'):
                if line.startswith('NAME='):
                    self.system_info["Operating System"] = line.split('=')[1].strip('"')
                elif line.startswith('VERSION='):
                    self.system_info["OS Release"] = line.split('=')[1].strip('"')

    def run_command(self, cmd):
        try:
            output = subprocess.check_output(cmd, shell=True, text=True)
            return output.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error executing command '{cmd}': {e}")
            return ""

    def export_to_json(self, file_path):
        Path(os.path.dirname(file_path)).mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(self.system_info, f, indent=4)

def main():
    collector = SystemCollector()
    system_info = collector.get_system_info()

if __name__ == "__main__":
    main()