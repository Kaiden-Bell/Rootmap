import socket
import subprocess
import json
import os
from pathlib import Path
import re
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_PATH = "results/"

version_regex = r"(\d+\.\d+\.\d+)"  # Regex to match version numbers like 1.2.3

class ServiceCollector:
    def __init__(self):
        self.export_to_json(os.path.join(SCRIPT_DIR, EXPORT_PATH, "service_versions.json"))
        self.get_conf_files()

    def run_command(self, cmd):
        try:
            output = subprocess.check_output(cmd, shell=True, text=True)
            return output.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error executing command '{cmd}': {e}")
            return ""
        
    def collect_versions(self):
        commands = [
            ("nginx", "nginx -v 2>&1 || true"),
            ("apache2", "apache2 -v 2>&1 || true"),
            ("mysql", "mysql --version 2>&1 || true"),
            ("postgresql", "psql --version 2>&1 || true"),
            ("mongodb", "mongod --version 2>&1 || true"),
            ("mariaDB", "mariadb --version 2>&1 || true"),
            ("docker", "docker --version 2>&1 || true"),
            ("docker-compose", "docker-compose --version 2>&1 || true"),
            ("nodejs", "node -v 2>&1 || true"),
            ("python3", "python3 --version 2>&1 || true"), # Need to get global python version (not in venv)
            ("git", "git --version 2>&1 || true"),
            ("php", "php -v 2>&1 || true"),
            ("cups", "cupsd -v 2>&1 || true"),
            ("dnsmasq", "dnsmasq --version 2>&1 || true"),
            ("fail2ban", "fail2ban-client --version 2>&1 || true"),
            ("guacamole", "guacd -v 2>&1 || true"),
            ("tomcat9", "catalina.sh version 2>&1 || true"),
            ("autofs", "autofs -V 2>&1 || true"),
            ("bind9", "named -v 2>&1 || true"),
            ("vsftpd", "vsftpd -v 2>&1 || true"),
            ("ganesha", "ganesha.nfsd -v 2>&1 || true"),
            ("uwsgi", "uwsgi --version 2>&1 || true"),
            ("sshd", "sshd -V 2>&1 || true"),
            ("dnsmasq", "dnsmasq --version 2>&1 || true"),
            ("containerd", "containerd --version 2>&1 || true"),
            ("k3s", "k3s --version 2>&1 || true"),
            ("ufw", "ufw --version 2>&1 || true"),
            ("sssd", "sssd --version 2>&1 || true"),
            ("auditd", "auditd -v 2>&1 || true"),
            ("ansible", "ansible --version 2>&1 || true"),
        ]
        body = {}
        for service, cmd in commands:
            output = self.run_command(cmd)
            if output:
                version = re.search(version_regex, output)
                if version:
                    body[service] = version.group()
                else:
                    continue  # Skip if version not found, do not append anything
                    # body.append(f"{service}: Version not found in output.")
            else:
                body[service] = f"{service}: Service not found or error occurred."
        # print("\n".join(body.values()))
        return body

    def export_to_json(self, file_path):
        Path(os.path.dirname(file_path)).mkdir(parents=True, exist_ok=True)
        versions = self.collect_versions()
        with open(file_path, "w") as f:
            json.dump(versions, f, indent=4)

    def get_conf_files(self):
        conf_files = {
            "nginx": ["/etc/nginx/nginx.conf", "/etc/nginx/sites-enabled/default"],
            "apache2": ["/etc/apache2/apache2.conf", "/etc/apache2/sites-enabled/000-default.conf"],
            "mysql": ["/etc/mysql/my.cnf"],
            "postgresql": ["/etc/postgresql/postgresql.conf", "/etc/postgresql/14/main/postgresql.conf"], # Adjust version as needed
            "mongodb": ["/etc/mongod.conf"],
            "mariaDB": ["/etc/mysql/mariadb.conf.d/50-server.cnf"],
            "docker": ["/etc/docker/daemon.json"],
            "docker-compose": None,  # No default config file
            "nodejs": None,  # No default config file
            "python3": None,  # No default config file
            "git": None,  # No default config file
            "php": ["/etc/php/7.4/cli/php.ini"],  # Adjust version as needed
            "cups": ["/etc/cups/cupsd.conf"],
            "dnsmasq": ["/etc/dnsmasq.conf"],
            "fail2ban": ["/etc/fail2ban/jail.conf"],
            "guacamole": ["/etc/guacamole/guacamole.properties"],
            "tomcat9": ["/etc/tomcat9/server.xml"],
            "autofs": ["/etc/auto.master"],
            "bind9": ["/etc/bind/named.conf.options"],
            "vsftpd": ["/etc/vsftpd.conf"],
            "ganesha": ["/etc/ganesha/ganesha.conf"],
            "uwsgi": ["/etc/uwsgi/uwsgi.ini"],
            "sshd": ["/etc/ssh/sshd_config"],
            "containerd": ["/etc/containerd/config.toml"],
            "k3s": ["/etc/rancher/k3s/k3s.yaml"],
            "ufw": None,  # No default config file
            "sssd": ["/etc/sssd/sssd.conf"],
            "auditd": ["/etc/audit/auditd.conf"],
            "ansible": None,  # No default config file
        }
        Path(os.path.join(SCRIPT_DIR, EXPORT_PATH, "configs")).mkdir(parents=True, exist_ok=True)
        for service, paths in conf_files.items():
            if paths:
                for path in paths:
                    if os.path.exists(path):
                        dest_dir = os.path.join(SCRIPT_DIR, EXPORT_PATH, "configs", service)
                        Path(dest_dir).mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.copy(path, dest_dir)
                        except Exception as e:
                            print(f"Error copying {path} to {dest_dir}: {e}")

def main():
    collector = ServiceCollector()
    collector.collect_versions()

if __name__ == "__main__":
    main()