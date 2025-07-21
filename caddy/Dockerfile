# Build Caddy with Cloudflare DNS plugin
FROM caddy:builder AS builder
RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare \
    --output /usr/bin/caddy

# Final image
FROM caddy:latest
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
EXPOSE 80 443
