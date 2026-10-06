FROM caddy:2.11.7-alpine@sha256:d76116d819d5162f464b0f2cd09bd28c568a86148c7bc539ce17c33eb22d8bbb

RUN setcap -r /usr/bin/caddy \
    && addgroup -S -g 10001 netguard \
    && adduser -S -D -u 10001 -G netguard netguard \
    && chown -R 10001:10001 /data /config
COPY Caddyfile tls-options.caddy /etc/caddy/
USER 10001:10001
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
    CMD wget -q -O /dev/null http://127.0.0.1:2019/config/ || exit 1
