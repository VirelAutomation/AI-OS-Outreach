FROM python:3.11-slim

# Install Chromium + ChromeDriver for headless browser (IG/FB)
RUN apt-get update && apt-get install -y \
    chromium \
    wget \
    curl \
    gnupg \
    libnss3 \
    libxss1 \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libgbm1 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Download Render MCP at build time (if accessible from build environment)
RUN curl -fsSL https://mcp.render.com/mcp -o /usr/local/bin/mcp \
    && chmod +x /usr/local/bin/mcp || true

ENV CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --headless"
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Railway injects $PORT; expose it
EXPOSE 8000

CMD ["./start.sh"]
