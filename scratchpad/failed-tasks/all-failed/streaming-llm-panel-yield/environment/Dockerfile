FROM ubuntu:24.04

# Install required apt packages, Node.js v24 (needed by Reflex's Next.js
# frontend at runtime/export), uv (Astral Python package manager), and the
# Python libraries used by the initial- and final-state pytest scripts.
RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git bash ripgrep unzip xz-utils procps \
        python3 python3-pip python3-pytest \
        build-essential && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages pytest-json-ctrf && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Prepare the user directory and an empty project workspace. The executor is
# expected to initialize the Reflex project inside this directory using `uv`.
RUN mkdir -p /home/user && chmod 0755 /home/user && \
    mkdir -p /home/user/streaming_llm_panel && \
    chmod 0755 /home/user/streaming_llm_panel

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex streaming LLM panel task environment: Ubuntu 24.04 with Python 3, uv, Node.js v24, and an empty /home/user/streaming_llm_panel workspace."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - extra apt packages: unzip xz-utils procps build-essential (procps provides pkill/pgrep used in tests)
#   - always required pip3 packages: pytest-json-ctrf
#   - Node.js v24 (required by Reflex's Next.js frontend)
#   - uv (Astral Python package manager) installed to /root/.local/bin and symlinked into /usr/local/bin
#   - /home/user/streaming_llm_panel: empty workspace where the executor will create the Reflex project
