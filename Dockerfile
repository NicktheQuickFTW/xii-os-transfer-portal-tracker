FROM alpine:3.19

# Install system dependencies
RUN apk add --no-cache \
    nodejs \
    npm \
    python3 \
    py3-pip \
    postgresql-dev \
    gcc \
    python3-dev \
    musl-dev \
    linux-headers \
    curl \
    make \
    g++ \
    chromium \
    chromium-chromedriver \
    zsh

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    NODE_ENV=production

# Create app directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY requirements.txt ./

# Install dependencies
RUN npm ci --only=production
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Playwright
RUN mkdir -p /ms-playwright
RUN playwright install chromium

# Copy application code
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE 3001

# Start the application
CMD ["npm", "start"] 