FROM mcr.microsoft.com/playwright:v1.64.1-noble

WORKDIR /workspace
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY tests/e2e/package.json /workspace/package.json
RUN npm install --no-audit --no-fund
COPY tests/e2e /workspace/tests/e2e

CMD ["npx", "playwright", "test", "--config=tests/e2e/playwright.config.ts"]
