"""Tool registration.

Each module exposes ``register(mcp, client)`` and defines thin tools that forward
to the in-Fusion add-in via ``client.call(op, params)``. The arbitrary-code
``script`` tool is only registered when explicitly enabled.
"""


def register_all(mcp, client, config):
    from . import (
        api,
        assembly,
        body,
        cam,
        construction,
        document,
        edit,
        export,
        feature,
        material,
        parameter,
        primitive,
        query,
        sketch,
        surface,
        units,
        view,
    )

    for module in (
        document,
        query,
        parameter,
        sketch,
        feature,
        primitive,
        body,
        construction,
        material,
        export,
        view,
        units,
        assembly,
        cam,
        edit,
        surface,
    ):
        module.register(mcp, client)

    # Read-only generic-API helpers (introspect/docs) are always available.
    api.register(mcp, client)

    # Power tools (arbitrary execution) are gated behind allow_arbitrary_code.
    if config.allow_arbitrary_code:
        from . import script

        script.register(mcp, client)
        api.register_power(mcp, client)
