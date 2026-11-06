import socket
import subprocess
import json
import os
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_PATH = "results/"

class ConnectionScanner:
    def __init__(self):
        self.sockets_info = self.get_sockets()
        self.export_to_json(os.path.join(SCRIPT_DIR, EXPORT_PATH, "sockets_info.json"))

    def get_sockets(self):
        services = [
            "nginx",
            "apache2",
            "mysql",
            "postgresql",
            "mongodb",
            "mariaDB",
            "docker",
            "docker-compose",
            "nodejs",
            "python3",
            "git",
            "php",
            "cups",
            "dnsmasq",
            "fail2ban",
            "guacamole",
            "tomcat9",
            "autofs",
            "bind9",
            "vsftpd",
            "ganesha",
            "uwsgi",
            "sshd",
            "containerd",
            "k3s",
            "ufw",
            "sssd",
            "auditd",
            "ansible"
        ]
        rows = []
        parsed = []
        try:
            # Use 'ss' command to get socket information
            output = subprocess.check_output("sudo ss -tulpn", shell=True, text=True)
            rows = output.strip().split('\n')[1:] # Skip the header line
            for row in rows:
                for service in services:
                    if service in row:
                        # Extract relevant information from the row
                        parts = row.split()
                        local_address = parts[4].rpartition(':')[0]  # Local Address:Port
                        port = parts[4].rpartition(':')[2]  # Port
                        pid_program = parts[-1]    # PID/Program name
                        parsed.append({
                            "Service": service,
                            "Local Address": local_address,
                            "Port": port,
                            "PID/Program": pid_program
                        })
        except subprocess.CalledProcessError as e:
            print(f"Error executing command 'ss -tulpn': {e}")
            return ""
        return parsed

    def export_to_json(self, file_path):
            Path(os.path.dirname(file_path)).mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                json.dump(self.sockets_info, f, indent=4)

def main():
    scanner = ConnectionScanner()

if __name__ == "__main__":
    main()