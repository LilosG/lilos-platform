ARG HERMES_IMAGE=docker.io/nousresearch/hermes-agent:v2026.8.19@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
FROM ${HERMES_IMAGE}

USER root

COPY --chmod=0755 scripts/render_start_hermes.sh /usr/local/bin/lilos-render-start-hermes
COPY infrastructure/hermes/plugins/lilos /opt/hermes/plugins/lilos

ENTRYPOINT ["/usr/local/bin/lilos-render-start-hermes"]
CMD ["gateway", "run", "--no-supervise", "--external-supervisor"]
