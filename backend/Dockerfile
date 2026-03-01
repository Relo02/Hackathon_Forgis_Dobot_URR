FROM ros:humble

RUN apt-get update && apt-get install -y \
    curl \
    git \
    python3-colcon-common-extensions \
    ros-humble-ur \
    ros-humble-realsense2-camera \
    ros-humble-realsense2-description \
    && rm -rf /var/lib/apt/lists/*

# Build dobot_msgs_v4 (Python service/message bindings for DOBOT Nova 5).
# Only the message package is built here; the full DOBOT driver runs in the dobot-driver container.
RUN mkdir -p /dobot_msgs_ws/src && \
    cd /dobot_msgs_ws/src && \
    git clone --depth 1 --filter=blob:none --sparse \
        https://github.com/Dobot-Arm/DOBOT_6Axis_ROS2_V4.git && \
    cd DOBOT_6Axis_ROS2_V4 && \
    git sparse-checkout set dobot_msgs_v4 && \
    cd /dobot_msgs_ws && \
    . /opt/ros/humble/setup.sh && \
    colcon build --symlink-install --packages-select dobot_msgs_v4

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Install franky-control (Python bindings for libfranka) from pre-built wheels
RUN apt-get update && apt-get install -y wget unzip && rm -rf /var/lib/apt/lists/* && \
    wget -q -O /tmp/libfranka_wheels.zip \
        "https://github.com/TimSchneider42/franky/releases/latest/download/libfranka_0-9-2_wheels.zip" && \
    unzip -o /tmp/libfranka_wheels.zip -d /tmp/franky_wheels && \
    uv pip install --no-index --find-links=/tmp/franky_wheels/dist franky-control && \
    rm -rf /tmp/libfranka_wheels.zip /tmp/franky_wheels

COPY src/ ./src/
COPY scripts/ ./scripts/
RUN sed -i 's/\r$//' scripts/*.sh && chmod +x scripts/*.sh

# Create flows directory for flow persistence
RUN mkdir -p /app/flows

# Pre-create Ultralytics settings to avoid runtime delay
RUN mkdir -p /root/.config/Ultralytics /app/weights && \
    printf "settings_version: 0.0.6\ndatasets_dir: /root/datasets\nweights_dir: /app/weights\nruns_dir: /root/runs\nuuid: none\nsync: false\napi_key: ''\n" > /root/.config/Ultralytics/settings.yaml

# Expose FastAPI port
EXPOSE 8000

CMD ["bash", "scripts/start_backend.sh"]