"""Run the CSA Workbench assistant runtime."""

import uvicorn


def main() -> None:
    uvicorn.run("workbench_assistant.server:app", host="127.0.0.1", port=8080)


if __name__ == "__main__":
    main()
