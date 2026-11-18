FROM node:20-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Node requirements
COPY package*.json ./
RUN npm install --omit=dev

# Copy project files
COPY . .

ENV PORT=3000
EXPOSE 3000

CMD ["npm", "start"]
