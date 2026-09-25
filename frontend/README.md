# CareConnect frontend

React 19 + TypeScript + Vite, styled with Tailwind CSS v4 (`src/index.css`), data via TanStack
Query, API types generated from `../docs/openapi.yaml`.

```bash
npm ci
npm run dev        # http://localhost:5173, proxies /api to :8000
npm run lint && npm run typecheck && npm test && npm run build
npm run gen:api    # regenerate src/api/schema.d.ts (commit the result)
npm run e2e        # Playwright; resets the LOCAL database, see ../README.md
```

Source layout: `src/api` (client, error messages, generated types), `src/auth`, `src/components`,
`src/features/<area>` (pages, hooks, tests), `e2e/` (Playwright specs incl. the accessibility pass
and the full journey). Setup and conventions are in the root `README.md` and `docs/`.
