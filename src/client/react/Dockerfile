# Stage: Dev server for Vite
FROM node:20-alpine

# Create app dir
WORKDIR /app

# Install deps (use npm ci if you have a lockfile)
COPY package*.json ./
RUN npm ci

# Copy the rest
COPY . .

# Expose Vite default port
EXPOSE 5173

# Run Vite dev server binding to 0.0.0.0 so Docker can expose it
CMD [ "npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173" ]
