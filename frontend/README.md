# CodeMind Frontend

Enterprise Next.js dashboard for the CodeMind API.

## Quick start

```bash
# From repo root — ensure API is running on :8000
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment

| Variable | Default |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |

Set in `.env.local`.

## Features

- **Dashboard** — graphs, projects, coverage overview
- **Projects** — multi-repo grouping (source / test / ci / cd) with functional coverage
- **Graph detail** — Overview, Coverage, Architecture, Security, Health, Search, Docs
- **Ingest** — index repositories with role and project assignment
- **Command palette** — `Cmd+K` to jump to graphs
