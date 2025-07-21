# caddy/Dockerfile
# Use the official Caddy builder image for compiling with plugins
FROM caddy:builder AS builder

# Build Caddy with the Cloudflare DNS plugin
RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare \
    --output /usr/bin/caddy

# Use the official Caddy production image as the base for the final image
FROM caddy:latest

# Copy the custom-built Caddy binary from the builder stage
COPY --from=builder /usr/bin/caddy /usr/bin/caddy

# Ensure the Caddy executable has the correct permissions (usually not strictly needed as caddy:latest handles it)
# RUN chmod +x /usr/bin/caddy

# Expose HTTP and HTTPS ports (Caddy's default image already exposes these, but explicitly stating is fine)
EXPOSE 80 443

# Set the entrypoint for Caddy. This is typically already handled by the base image.
# ENTRYPOINT ["caddy"]
# CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
