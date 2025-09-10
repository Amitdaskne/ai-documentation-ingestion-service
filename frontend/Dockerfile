FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE 59420

# Start the application
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "59420"]