# Phase 4 Manual Verification

Phase 4 proves bounded public-market discovery and deep research. It does not
claim to search the entire internet, collect personal contacts, generate
outreach, or bypass source access controls.

## 1. Start the backend

Use a real contact address or public contact URL that may appear in the
collector User-Agent. It is not stored in campaign evidence.

```powershell
Set-Location "<path-to-your-clone>\GTM-Agent"
$env:GTM_RESEARCH_CONTACT = "research-contact@example.com"
uv run uvicorn src.runtime.api:app --reload --host 127.0.0.1 --port 8001
```

Optionally broaden candidate discovery with a local Brave Search API key:

```powershell
$env:GTM_BRAVE_SEARCH_API_KEY = "your-brave-search-api-key"
```

Only industry and region terms are included in that search query. Search
results remain untrusted candidate hints until official-site evidence is
successfully collected.

For English summaries of non-English pages, also set both optional Colab values
before starting the backend:

```powershell
$env:GTM_TRANSLATION_ENDPOINT = "https://your-colab-tunnel.example/translate"
$env:GTM_TRANSLATION_API_KEY = "your-long-random-secret"
```

The ignored response cache is created at `data/research-cache.sqlite3`. If port
8001 is unavailable, choose another local port.

## 2. Start the frontend

In a second terminal:

```powershell
Set-Location "<path-to-your-clone>\GTM-Agent\frontend"
$env:GTM_API_PROXY_TARGET = "http://127.0.0.1:8001"
npm.cmd run dev
```

Open the local URL printed by Vite.

## 3. Configure and approve a campaign

1. Submit a product and ICP with no more than three industries and, when
   targeting a specific market, one or more regions.
2. Review every proposed product claim.
3. Approve at least one claim and reject or approve the rest.
4. Confirm the research workspace initially labels fixture prospects as
   synthetic.

## 4. Run live discovery

Optionally enter up to ten public HTTPS market pages, one per line. Useful
sources include public industry associations, directories, registries, and
market lists whose access rules permit automated retrieval.

Select **Run live market discovery**. Independent sources and unique candidate
sites run concurrently within a bounded deadline; each host still keeps its
own rate and robots limits. It uses the machine's internet connection and
therefore consumes its Wi-Fi/mobile data.

Confirm:

- live candidates replace the fixture list;
- each candidate displays priority, evidence quality, coverage, uncertainty,
  factor states, and citations;
- unsupported size, role, or pain factors remain `unknown` and add no score;
- when regions are supplied, every eligible candidate has cited matching region
  evidence; unsupported and out-of-region candidates are excluded;
- source failures or robots denials produce an explicit error or warning;
- citations open only validated HTTPS public pages.

Discovery can legitimately return no candidates for a sparse industry. Add a
relevant permitted market seed rather than treating missing evidence as a
match.

An official website may redirect to a different company domain because of a
rebrand or merger. A cross-domain destination is admitted only for a permanent
301/308 redirect from an existing structured official-site record, with public
DNS, HTTPS, bounded hops, and company/domain identity checks. Search hints and
temporary redirects cannot open this path. A denied redirect keeps the
candidate when it already has structured evidence and reports an explicit
warning.

## 5. Select and research one prospect

1. Select one candidate.
2. Confirm the campaign moves to `awaiting_prospect_research`; selection alone
   has not authorized positioning.
3. Select **Research selected company**.
4. Inspect the short company, offerings, projects, news, and technical findings;
   confirm unknown sections remain explicit and every finding retains citations.
5. For a non-English source, confirm the summary is English and is labeled with
   its source language and translation status. If Colab is offline, confirm the
   UI says translation is unavailable instead of displaying invented content.

The deep run reads at most twelve evidence pages on admitted official hosts,
including relevant second-level links. When the homepage exposes no useful
links, one bounded `/sitemap.xml` index request supplies same-host candidates.
Focused extraction removes common navigation noise. The run targets company,
offerings, projects, newsroom, and technical material. PDF links are recorded
as a limitation but are not extracted in this phase.

## 6. Acceptance gate

Approve Phase 4 only if:

- the final state is `prospect_researched`;
- the UI clearly stops before outreach generation;
- evidence belongs to the displayed run and selected prospect;
- a failed source cannot create prospects or a research profile;
- no emails, phone numbers, credentials, full page copies, or model artifacts
  appear in Git.

Stop the backend and frontend with `Ctrl+C`. The campaign disappears on backend
restart; the ignored cache may be retained or deleted locally.
