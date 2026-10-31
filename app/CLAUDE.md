# Legacy app directory

The user selected Next.js/React + Tailwind CSS, FastAPI, MariaDB, and Neo4j. New frontend work belongs in `frontend/`; the HTTP API belongs in `citehop/api/`. Do not implement a Streamlit application here.

Read `docs/COURSE_TASKS.md` for current task IDs, `docs/ARCHITECTURE.md` for ownership/contracts, and `docs/design/COURSE_UI.md` before UI work. Earlier paper-search mockups are visual references only.

- All browser data access goes through FastAPI; no database credentials, SQL, or Cypher in the frontend.
- MariaDB owns documents, vectors, and relational search. Neo4j powers the derived graph explorer.
- Preserve exact source passages and real citation mappings. Never use fictional prototype content as product data.
- Graph limits apply in the backend and visible canvas. Show stale/truncated/unavailable states honestly.
- No metric without a saved run or live count. Include loading, empty, error, and missing states.
- The chosen dark navy/cyan direction and existing logo are settled in COURSE_UI.md; do not reopen old stack/theme decisions.
- Preserve the current branch and unrelated work. Save review screenshots under `.context/`.
