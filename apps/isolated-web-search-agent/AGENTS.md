# Isolated Web Search Agent

This project was built with the microsoft-foundry skill. Before working on or answering questions about foundry agents, read the microsoft-foundry skill first.

## Project Invariant

The model that reads the web holds no privileged tools. The model that holds privileged tools never reads raw web content.

Keep the main harness and web research subagent separated by the JSON task/findings contract in `src/isolated-web-search-agent/isolation_contracts.py`.
