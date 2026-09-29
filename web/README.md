# CiteHop web

Next.js (App Router) + React + TypeScript + Tailwind CSS v4 frontend for CiteHop.
Architecture and rules: `../design/docs/13-FRONTEND-ARCHITECTURE.md`. Agent rules: `CLAUDE.md`.

```bash
npm install
cp .env.example .env.local   # CITEHOP_API_URL, server-only
npm run dev                  # http://localhost:3000
```

| Check | Command |
|---|---|
| Lint | `npm run lint` |
| Types | `npm run typecheck` |
| Unit tests | `npm test` |
| Contract types | `npm run gen:types` |
| Build | `npm run build` |
