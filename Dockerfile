FROM oven/bun:1.3.0

WORKDIR /app

# Python is required for mini-services/collect_observations.py
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-pip \
  && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* bun.lock* ./
RUN bun install

COPY . .

# Prisma client for Next.js API routes.
RUN bunx prisma generate

# Local Python package for d2jsp collection + parser.
RUN python3 -m pip install --no-cache-dir -e ./d2lut requests

RUN bun run build

EXPOSE 3000
CMD ["bun", "run", "start"]
