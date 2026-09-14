# Leads marketing site

## Local setup

From `marketing-site`, install dependencies with `npm install`, then run `npm run dev`. Open `http://localhost:3000`.

Run `npm run typecheck`, `npm run lint`, and `npm run build` before deployment.

## Sandbox preview

The site lives on `feat/leads-marketing-site` and is isolated from the Python MCP service. Configure Vercel with `marketing-site` as Root Directory and deploy a Preview only. Do not attach the production domain in Phase 1.

## Environment variables

None are required. Do not copy backend secrets into this static marketing project.

## Deployment

After explicit approval, merge the approved commit using the repository workflow, deploy the exact commit in Vercel, and only then attach or verify `leads.chaddewet.com`.

## Placeholder replacement

The dashboard uses illustrative local data. Replace it with approved product screenshots or original assets with reserved dimensions. `/app` and `/login` are intentional placeholders until real routes are confirmed. Cards marked `PLANNED` must remain planned unless a working integration is verified.
