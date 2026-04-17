PUBLIC_INDEXES = [
    "https://pypi.org/simple"
]


def is_public_source(source: dict) -> bool:
    registry = source.get("registry")
    return registry in PUBLIC_INDEXES
