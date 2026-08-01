"""FastAPI application entrypoint for the Phase 0 development baseline."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create the API application without product routes or external dependencies."""
    return FastAPI(
        title="LILOs Platform API",
        description="Development foundation; product APIs are not implemented in Phase 0.",
        version="0.1.0",
    )


app = create_app()
