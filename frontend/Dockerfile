# Frontend Dockerfile for Windsurf Sustainable City POC
# Node.js Alpine image (Vite 7 requires Node 20.19+ or 22.12+)

FROM node:22-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# For development, serve with Vite
# For production, use nginx or serve static files
EXPOSE 3000

# Development command
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
