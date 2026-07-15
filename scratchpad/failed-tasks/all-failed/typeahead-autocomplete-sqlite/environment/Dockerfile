FROM ubuntu:24.04

ARG POCHI_VERSION
ARG AGENT_BROWSER_VERSION=0.27.3-pochi

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep \
        unzip xz-utils build-essential \
        ffmpeg libxcb-shm0 libx11-xcb1 libx11-6 libxcb1 libxext6 libxrandr2 libxcomposite1 libxcursor1 libxdamage1 libxfixes3 libxi6 libgtk-3-0t64 libpangocairo-1.0-0 libpango-1.0-0 libatk1.0-0t64 libcairo-gobject2 libcairo2 libgdk-pixbuf-2.0-0 libxrender1 libasound2t64 libfreetype6 libfontconfig1 libdbus-1-3 libnss3 libnspr4 libatk-bridge2.0-0t64 libdrm2 libxkbcommon0 libatspi2.0-0t64 libcups2t64 libxshmfence1 libgbm1 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    curl -fsSL https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx && \
    curl -fsSL https://getpochi.com/install.sh | bash -s ${POCHI_VERSION} && \
    ln -s /root/.pochi/bin/pochi /usr/local/bin/pochi && \
    curl -fsSL https://github.com/TabbyML/agent-browser/releases/download/v${AGENT_BROWSER_VERSION}/install.sh | bash && \
    ln -s /root/.pochi/bin/agent-browser /usr/local/bin/agent-browser && \
    agent-browser install && \
    pip3 install --break-system-packages pytest-json-ctrf pytest-xprocess requests pochi-verifier && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

# Seed the product catalog dataset the app must import into SQLite.
RUN mkdir -p /home/user/catalog_app && \
    cat >/home/user/catalog_app/products.csv <<'EOF'
name,category,price,description
Apple,Fruit,1.50,Crisp red apple
Apricot,Fruit,2.00,Sweet orange apricot
Application Server,Software,499.00,Enterprise application server
Pineapple,Fruit,3.25,Tropical golden pineapple
Snapple,Beverage,2.50,Bottled fruit drink
Banana,Fruit,0.75,Ripe yellow banana
Blackberry,Fruit,4.00,Fresh blackberries
Blueberry,Fruit,4.50,Fresh blueberries
Strawberry,Fruit,3.75,Red ripe strawberries
Raspberry,Fruit,5.00,Bright red raspberries
Grape,Fruit,2.20,Seedless green grapes
Mango,Fruit,1.80,Sweet tropical mango
Laptop Pro,Electronics,1299.00,High-end professional laptop
Projector,Electronics,650.00,Ultra HD home projector
Processor,Electronics,320.00,Eight-core desktop CPU
Notebook,Stationery,3.50,Ruled paper notebook
Notebook Pro,Electronics,1499.00,Premium ultralight notebook laptop
Keyboard,Electronics,45.00,Wireless mechanical keyboard
Application Framework,Software,0.00,Open-source web framework
Grapefruit,Fruit,2.10,Pink juicy grapefruit
Cranberry,Fruit,3.10,Tart red cranberries
Appliance Hub,Electronics,89.00,Smart home appliance hub
Pear,Fruit,1.20,Green Bartlett pear
Peach,Fruit,2.30,Juicy yellow peach
EOF

LABEL Author="generate-harbor-tasks"
LABEL Description="Reflex + uv + Node.js 20 environment for a SQLite-backed typeahead autocomplete app, including browser verification tooling."

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]

# Container contents:
#   - always required apt packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash ripgrep
#   - always required pip3 packages: pytest-json-ctrf
#   - test/verification pip3 packages: pytest-xprocess, requests, pochi-verifier
#   - uv package manager (for building/running the Reflex app), Node.js 20, unzip/xz for bun
#   - browser verification: agent-browser, pochi-verifier, and X/GTK/ffmpeg runtime libs
#   - /home/user/catalog_app: project directory
#   - /home/user/catalog_app/products.csv: seed catalog dataset the app must load into SQLite

# Setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
