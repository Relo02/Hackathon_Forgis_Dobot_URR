# Forgis Robot Control

Control system for a UR3 robot arm, running on ROS 2 Humble inside Docker.

## Architecture

Two Docker containers share the host network to communicate with each other (via DDS) and with the robot (via Ethernet):

```
┌─────────────────────────────────────────────────────┐
│  Host machine (network_mode: host)                  │
│                                                     │
│  ┌──────────────┐       ┌────────────────────────┐  │
│  │  ur-driver    │  DDS  │  backend               │  │
│  │              │◄─────►│                        │  │
│  │  UR robot    │       │  RobotNode             │  │
│  │  driver      │       │  PickAndPlacePipeline  │  │
│  └──────┬───────┘       └────────────────────────┘  │
│         │ Ethernet                                   │
└─────────┼───────────────────────────────────────────┘
          │
    ┌─────┴─────┐
    │   UR3     │
    └───────────┘
```

**ur-driver** — Launches the `ur_robot_driver` which connects to the robot over Ethernet and exposes ROS 2 topics (`/joint_states`, `/urscript_interface/script_command`, IO states, etc.).

**backend** — Runs two ROS 2 nodes:
- `RobotNode` (`nodes/ur_node.py`) — Abstraction over the UR driver. Sends URScript commands, reads joint positions and IO states, detects rising edges on digital inputs, and publishes digital input changes to `/events/digital_input_change`.
- `PickAndPlacePipeline` (`pipelines/pick_and_place_pipeline.py`) — Listens for a rising edge on a configurable digital input pin. When triggered, runs a pick-and-place sequence: moves through a series of joint poses, toggling a digital output (vacuum) at pick/place positions.

## Setup

### Prerequisites

- Docker and Docker Compose
- **Docker Desktop**: Enable **host networking** in Settings → Resources → Network → "Enable host networking"
- UR3 connected via Ethernet
- Robot powered on with brakes released

### Network Configuration

The PC and robot must be on the same subnet. The UR driver listens on port 5002, which the robot's External Control program connects to.

**1. Set your PC's Ethernet IP:**

On Windows:
1. Open **Control Panel** → **Network and Sharing Center**
2. Click **Ethernet** → **Properties**
3. Select **Internet Protocol Version 4 (TCP/IPv4)** → **Properties**
4. Configure:
   - IP address: `192.168.0.10`
   - Subnet mask: `255.255.255.0`
   - Gateway: leave blank
5. Click OK

Verify with `ipconfig` — Ethernet should show `192.168.0.10`.

**2. Configure External Control on the robot pendant:**

1. Go to **Installation** → **URCaps** → **External Control**
2. Set Host IP to your PC's IP (e.g., `192.168.0.10`)
3. Set Port to `50002` (default)
4. Save

**3. Verify connectivity:**

```bash
ping 192.168.0.101   # ping the robot from your PC
```

### Configuration

Edit `.env`:

```env
ROBOT_IP=192.168.0.101   # your robot's IP (check pendant: Settings > Network)
UR_TYPE=ur3               # ur3, ur3e, ur5, ur5e, ur10, ur10e, ur16e
ROS_DOMAIN_ID=0           # change if other ROS 2 systems share the network

# Camera / Vision
YOLO_MODEL=yolov8n.pt

# Azure OpenAI (for label reading)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

### RealSense Camera Setup (Windows)

The RealSense camera runs in a Docker container but requires USB passthrough from Windows to WSL2.

**1. Install usbipd-win:**

Open PowerShell as Administrator:
```powershell
winget install usbipd
```

**2. List USB devices:**

```powershell
usbipd list
```

Find your RealSense camera (Intel RealSense). Note the **BUSID** (e.g., `2-3`).

**3. Bind and attach to WSL2:**

```powershell
# Bind the device (one-time setup)
usbipd bind --busid <BUSID>

# Attach to WSL2 (run each time you reconnect the camera)
usbipd attach --wsl --busid <BUSID>
```

**4. Verify in WSL2:**

```bash
lsusb | grep -i intel
```

You should see the RealSense device listed.

**5. Rebuild and run:**

```bash
docker compose up --build
```

**Note:** After unplugging/replugging the camera, you need to run `usbipd attach --wsl --busid <BUSID>` again.

### Run

**1. Start all services (in WSL):**

```bash
docker compose up --build
```

For Panda, run the backend directly in Panda mode:

```bash
ROBOT_TYPE=panda docker compose up --build
```

**2. Open the frontend:**

Open http://localhost in your browser.

**3. On the teach pendant:**

Load and **Play** the External Control program. You should see the backend log: `RobotNode initialized` and joint states being received.

### Frontend Configuration

The frontend runs on Windows and proxies API/WebSocket requests to the backend in WSL.

**If the backend is unreachable**, update the WSL IP in `frontend/vite.config.ts`:

```bash
# Get WSL IP (run in WSL terminal, not inside Docker)
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'
```

Update the proxy target in `vite.config.ts`:
```typescript
proxy: {
  '/api': {
    target: 'http://<WSL_IP>:8000',
    changeOrigin: true,
  },
  '/ws': {
    target: 'ws://<WSL_IP>:8000',
    ws: true,
  },
},
```

### Flow Execution API

The backend exposes a REST API and WebSocket for flow-based robot control on port 8000.

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/flows` | List all flows |
| GET | `/api/flows/{id}` | Get flow definition |
| POST | `/api/flows` | Create/update flow |
| POST | `/api/flows/{id}/start` | Start flow execution |
| POST | `/api/flows/abort` | Abort current flow |
| GET | `/api/flows/status` | Get execution status |
| GET | `/api/skills` | List available skills |
| GET | `/api/robot/state` | Get robot state |
| GET | `/api/camera/state` | Get camera state |
| GET | `/api/camera/snapshot` | Get JPEG snapshot |
| POST | `/api/camera/stream/start` | Start WebSocket streaming |
| POST | `/api/camera/stream/stop` | Stop WebSocket streaming |
| GET | `/health` | Health check |
| WS | `/ws` | WebSocket for real-time events |

**Example — start the pick and place flow:**

```bash
curl -X POST http://localhost:8000/api/flows/pick_and_place_v1/start
```

**Monitor via WebSocket:**

```bash
websocat ws://localhost:8000/ws
```

### Camera Testing

**Test camera snapshot:**

```bash
curl http://localhost:8000/api/camera/snapshot --output test.jpg
```

**Test object detection:**

```bash
curl -X POST http://localhost:8000/api/flows/camera_test/start
```

**Check camera state:**

```bash
curl http://localhost:8000/api/camera/state
```
