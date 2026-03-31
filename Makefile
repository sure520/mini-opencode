install:
	uv sync

build:
	uv build

dev:
	powershell "$$logFile = Join-Path $$env:TEMP 'mini-OpenCode\langgraph.log'; uvx --refresh --from 'langgraph-cli[inmem]' --with-editable . --python 3.12 langgraph dev --no-browser --allow-blocking 2>&1 | Tee-Object $$logFile"
