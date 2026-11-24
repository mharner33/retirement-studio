# Tech stack

- `backend/`: FastAPI and SQLite.
- `agent/`: LangChain's `create_agent` on OpenRouter. Potential agents include `retirement research agent`, `data extraction agent` for extracting data from pdf files, and `planning agent` that ties all of the data together.  All data should be sent through API's to/from the SQLite backend. 
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- The app should be optimized for running in a container (either Docker or Podman) so design the build/deployment according to what is available.
Python 3.12 or later with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
- The extraction of data from pdf files will use the [pymupdf](https://pymupdf.readthedocs.io/en/latest/the-basics.html)
