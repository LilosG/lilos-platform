ARG HERMES_IMAGE=docker.io/nousresearch/hermes-agent:v2026.8.3
FROM ${HERMES_IMAGE}

USER root

COPY --chmod=0755 scripts/render_start_hermes.sh /usr/local/bin/lilos-render-start-hermes

ENTRYPOINT ["/usr/local/bin/lilos-render-start-hermes"]
CMD ["gateway", "run", "--no-supervise", "--external-supervisor"]
