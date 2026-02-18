FROM debian:bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    tar \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download DevRag v1.2.1
RUN curl -L -o devrag.tar.gz https://github.com/tomohiro-owada/devrag/releases/download/v1.2.1/devrag-linux-x64.tar.gz \
    && tar -xzf devrag.tar.gz \
    && mv devrag-linux-x64 /usr/local/bin/devrag \
    && chmod +x /usr/local/bin/devrag \
    && rm devrag.tar.gz

# DevRag runs in stdio mode (one-shot per session), keep container alive for exec
CMD ["tail", "-f", "/dev/null"]
