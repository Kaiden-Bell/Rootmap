# RootMap - Cross-host Dependency Mapper

RootMap is a Linux-based system designed to discover, collect, and visualize service dependencies across multiple hosts within a network.

The system uses a centralized head node to manage connected Linux hosts, coordinate data collection, process reports, and display discovered relationships through a web-based dashboard.

## Project Goals

- Dependency Mapping: Identify and visualize relationships between services running across Linux hosts.
- Automated Collection: Collect system and service information through scheduled collection scripts.
- Centralized Management: Manage connected hosts, collection schedules, and reports from a single dashboard.
- Script Synchronization: Maintain consistent collection script versions across connected hosts.
- Security: Authenticate clients and protect communication between hosts and the head node.

## Repo Structure

```text
rootmap/
├── backend/
├── client/
├── frontend/
├── scripts/
├── deploy/
├── docs/
└── .github/
```

## Environment Setup
### Installation (Proxmox LXC - Ubuntu 26.04 LTS)
**1. Install Git**  
```bash
sudo apt install git
```
  
**2. Clone the repository**  
```bash
git clone -b dev-branch https://github.com/Kaiden-Bell/Rootmap.git
```

**3. Configure ports and credentials in installation scripts if desired**
   
**4. Install Rootmap components**  
Backend (API and Database): `cd Rootmap/backend && ./install_backend.sh`  
Frontend (Dashboard): `cd Rootmap/frontend && ./install_frontend.sh`  
Client (Agent): `cd Rootmap/client && ./install_client.sh`  

**5. Run client collection script**  
```bash
cd Rootmap/client/src/rootmap_client/scripts && uv run main.py --head-ip <head_ip> --head-port <head_backend_port>
```  

