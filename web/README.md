# ONER — Web

The student site and, later, the admin panel. Next.js 16 (App Router) + Tailwind v4 + [motion](https://motion.dev). The look follows `oner-motion.html`: near-monochrome, one blue accent, Inter, soft motion everywhere.

## Run

```bash
npm install
cp .env.local.example .env.local   # or set NEXT_PUBLIC_API_URL yourself
npm run dev                         # http://localhost:3000
```

The pages need the API running (see the repo root README). The catalog is fetched on the server and cached for 60 seconds.

## API types

`src/lib/api/schema.d.ts` is generated from the API's OpenAPI spec. After a backend change:

```bash
# from the repo root
uv run python -c "import json; from app.main import create_app; json.dump(create_app().openapi(), open('web/openapi.json', 'w'), indent=2, ensure_ascii=False)"
# then in web/
npm run api:types
```

## Where things are

- `src/app` — routes: `/` (hero, catalog, FAQ), `/courses/[slug]`
- `src/components/motion.tsx` — reveal, enter, rising headline, magnetic, count-up
- `src/components/tilt.tsx` — pointer tilt and spotlight
- `src/app/globals.css` — design tokens for light and dark

What to build next is in [ONER_Frontend_TODO.md](../ONER_Frontend_TODO.md).
