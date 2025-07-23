# Stage 1: Build the React app using Node
FROM node:18 AS builder

# Setup environment
ENV npm_config_arch=x64

# Set working directory
WORKDIR /app

# Copy dependencies and install
COPY package*.json ./
RUN npm ci

# Copy the full source and build it
COPY . .
RUN npm run build

# Stage 2: Serve using nginx
FROM nginx:alpine

# Remove the default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy your optimized app
COPY --from=builder /app/dist /usr/share/nginx/html

# Add custom nginx config
COPY nginx.conf /etc/nginx/conf.d/

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
