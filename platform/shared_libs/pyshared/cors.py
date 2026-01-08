from __future__ import annotations

from typing import Iterable, List, Sequence

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _parse_origins_from_env(env_value: str | None) -> List[str]:
    """
    Parse a comma- or space-separated list of origins from an env var.

    Empty tokens are ignored, and duplicates are de-duplicated while
    preserving order.
    """
    if not env_value:
        return []

    # Support both comma and space separated lists
    raw_tokens: list[str] = []
    for part in env_value.split(","):
        raw_tokens.extend(part.split())

    seen: set[str] = set()
    origins: list[str] = []
    for token in raw_tokens:
        origin = token.strip()
        if origin and origin not in seen:
            seen.add(origin)
            origins.append(origin)

    return origins


def add_env_cors(
    app: FastAPI,
    env_var_name: str = "CORS_ALLOWED_ORIGINS",
    *,
    default_local_origins: Sequence[str] | None = None,
    allow_credentials: bool = True,
    allow_methods: Iterable[str] | None = None,
    allow_headers: Iterable[str] | None = None,
) -> None:
    """
    Attach CORS middleware to a FastAPI app using configuration from env.

    - env_var_name: name of the environment variable to read allowed origins from.
      Example format:
        CORS_ALLOWED_ORIGINS="https://app.example.com, https://admin.example.com"
    - default_local_origins: extra localhost origins to always allow (useful in dev).
      If None, a sensible set of localhost defaults will be used.
    - allow_credentials / allow_methods / allow_headers: passed through to
      `CORSMiddleware`. If methods/headers are None, `"*"` is used.
    """
    if default_local_origins is None:
        default_local_origins = (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://teems-web-app.vercel.app",
            "http://teems-web-app.vercel.app",
        )

    env_value = os.getenv(env_var_name)
    env_origins = _parse_origins_from_env(env_value)

    # Merge env origins with defaults, preserving order and de-duplicating.
    all_origins: list[str] = []
    seen: set[str] = set()

    for origin in list(default_local_origins) + env_origins:
        if origin not in seen:
            seen.add(origin)
            all_origins.append(origin)

    methods = list(allow_methods) if allow_methods is not None else ["*"]
    headers = list(allow_headers) if allow_headers is not None else ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=all_origins,
        allow_credentials=allow_credentials,
        allow_methods=methods,
        allow_headers=headers,
    )


