# BAsight: Business Intelligence & Predictive Analysis

The chat/agent layer isn't wired up yet — there's an intentionally disabled
placeholder on the dashboard where it will go (see `components/ChatComingSoon.tsx`).

## Run it

```bash
npm install
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_URL at your backend
npm run dev
```

Requires the backend from the previous step running (default `http://127.0.0.1:8000`).
Needs internet access on first build/dev run to fetch fonts from Google Fonts
(`next/font/google`) — standard for any Next.js project using it, not specific
to this setup.

## Design direction: "The Ledger"

Built around retail's own vernacular — receipts, price tags, ledgers, barcodes —
instead of generic SaaS dashboard chrome. Concretely:

- **Palette**: warm near-black `ink` (#100E0B) as the primary surface, `paper`
  (#F6F1E4) used for card/receipt surfaces rather than the whole page, one
  bold accent (`signal`, a sale-tag orange, #F0631F). `mint`/`brick` are used
  *only* functionally, for revenue up/down — never decoratively.
- **Type**: Big Shoulders Display (condensed industrial signage face, built for
  the Chicago Design System — shopfront character) for headlines; IBM Plex
  Sans for body/UI; IBM Plex Mono for every number and data label, so figures
  read like a receipt printer rather than a generic UI font.
- **Signature moment**: file upload triggers a till-receipt that visibly
  "prints" the cleaning pipeline (rows found, columns typed, revenue detected)
  line by line before tearing off into the dashboard — dramatizing the actual
  value prop (messy file → clean numbers) instead of a generic spinner. See
  `components/ReceiptLoader.tsx`.
- Every dashboard metric that the backend couldn't compute renders as an
  explicit `N/A — <reason>` rather than a blank space or a crash (e.g. "no
  date column detected") — pulled from the backend's `unavailable_metrics`.

## Structure

```
app/
  layout.tsx        Font loading (next/font/google), root HTML shell
  page.tsx           State machine: upload -> processing -> dashboard
  globals.css         Theme base styles + reusable texture utilities (perforated
                       edges, barcode, halftone grain)
components/
  UploadScreen.tsx    Hero drag-and-drop
  ReceiptLoader.tsx   Signature "printing receipt" loading sequence
  Dashboard.tsx       Assembles all sections below
  KpiCard.tsx         Ticket-stub styled metric card, animated count-up
  RevenueChart.tsx    Recharts area chart, themed
  TopProductsReceipt.tsx  Receipt-style itemized product list
  CategoryBreakdown.tsx   Category revenue share bars
  DataQualityBanner.tsx   Surfaces backend warnings (dupes, ambiguous dates, etc.)
  ChatComingSoon.tsx      Disabled placeholder for the not-yet-built agent
  Reveal.tsx              IntersectionObserver-based scroll-reveal wrapper
hooks/
  useCountUp.ts       Animates KPI numbers on mount, respects reduced-motion
lib/
  api.ts              Typed fetch client for the FastAPI backend
  types.ts            TypeScript mirrors of the backend's Pydantic models
```

## Known gaps / deliberate cuts

- **No loading/retry for transient network failures** beyond the one-shot
  upload error path — fine for a demo, would want retry-with-backoff for
  production.
- **`npm audit` still flags two `high` advisories** against Next.js's broader
  advisory range (Server Actions, Middleware, Image Optimizer, edge cache
  poisoning) — none of which this app uses (no server actions, no middleware,
  no `next/image`, no custom server). Pinned to `14.2.35`, the latest patch on
  the 14.x line, rather than jumping to Next 16 unverified.
- Currency formatting is hardcoded to USD in a few display spots
  (`toLocaleString(..., { currency: "USD" })`) — worth making configurable
  once there's a real multi-currency SME user.
