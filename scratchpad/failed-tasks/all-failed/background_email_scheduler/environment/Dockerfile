FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        procps build-essential sqlite3 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    pip3 install --break-system-packages pytest-json-ctrf requests pytest-xprocess && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex task environment for the background scheduled email digest generator: Ubuntu 24.04 with python3, uv, Node.js v22, sqlite3, and pytest-xprocess for managing the Reflex backend during verification."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - additional apt packages: procps (provides pkill/pgrep used to kill leftover Reflex servers), build-essential (some Reflex deps compile), sqlite3 (handy CLI inspection of the rx.Model SQLite DB)
#   - always required pip3 packages: pytest-json-ctrf
#   - additional pip3 packages used by tests: requests (HTTP probing of the FastAPI control endpoints), pytest-xprocess (managing the long-running Reflex backend during the final-state pytest run)
#   - Astral uv installed via the official installer and symlinked into /usr/local/bin so the executor can `uv init` / `uv add reflex` non-interactively per the research plan
#   - Node.js v22 installed via the NodeSource setup script so `reflex init --template blank` and `reflex run` can bootstrap the Next.js frontend (even though tests run only the backend, `reflex init` requires npm at project bootstrap time)
#   - /home/user: empty home directory; the executor creates /home/user/email_scheduler from scratch
