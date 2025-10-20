FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install runtime dependencies: Java (for Ostrich), time, bc, core tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    time \
    bc \
    ca-certificates \
    dos2unix \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Copy repository contents
COPY . /app

# Ensure scripts are executable and normalized
RUN find /app/scripts -type f -name "*.sh" -exec dos2unix {} \; && \
    chmod +x /app/scripts/*.sh && \
    chmod +x /app/bin/* || true

# Default logs/results location inside container
ENV TIMEOUT_SECS=120

# Use tini for proper signal handling; default to bash
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/bin/bash"]
