FROM authelia/authelia:4.39.28@sha256:bd97cff4fcbf715b5ff1f9ae286afbe6033afce385302520b0368122d43a6f54

RUN mkdir -p /var/lib/authelia \
    && chown 10001:10001 /var/lib/authelia
COPY configuration.yml /etc/authelia/configuration.yml
ENV X_AUTHELIA_CONFIG=/etc/authelia/configuration.yml \
    X_AUTHELIA_CONFIG_FILTERS=template
USER 10001:10001
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
    CMD wget -q -O /dev/null http://localhost:9091/auth/api/health || exit 1
