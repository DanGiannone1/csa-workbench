# Backend

The backend has three Python packages:

- `api` serves browser requests and calls the assistant runtime;
- `assistant` runs assistant sessions and owns the product skills; and
- `core` contains the rules, persistence, security helpers, and result types both applications use.

The API and assistant may depend on `core`. They must not import each other.

The repository root owns the shared Python environment and lock file. Run `uv sync` from the root;
do not create separate component lock files.
