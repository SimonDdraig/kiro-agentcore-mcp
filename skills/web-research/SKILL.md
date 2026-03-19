---
name: web-research
description: Instructions for using authoritative Australian government URLs, validating web sources, and when to use Fetch Server vs conservation docs
allowed-tools:
  - fetch
---

# Web Research

## Authoritative Australian Government URLs

When fetching live web content, prefer these authoritative government sources:

| Domain | Organisation | Use For |
|--------|-------------|---------|
| **bom.gov.au** | Bureau of Meteorology | Weather warnings, radar, climate data, flood alerts |
| **dcceew.gov.au** | Dept. of Climate Change, Energy, Environment and Water | National threatened species lists, EPBC Act listings, conservation policies |
| **parks.vic.gov.au** | Parks Victoria | Victorian park closures, fire restrictions, visitor alerts |
| **nsw.gov.au** | NSW Government (Parks, Reserves and Protected Areas) | NSW park information, wildlife management, fire bans |

## When to Use Fetch Server vs Conservation Docs

### Use Conservation Docs (preferred) when:
- The question is about a species, park, or procedure that is likely covered by pre-loaded documents.
- You need detailed management plans or emergency procedures that have been curated for this system.
- The ranger needs offline-reliable information (conservation docs are always available).

### Use Fetch Server when:
- The ranger asks for **current** or **real-time** information (e.g., today's fire bans, active weather warnings).
- The conservation docs do not contain the needed information, or the search returned no results.
- The ranger specifically asks about a government website or external resource.
- You need to verify or supplement conservation doc information with the latest official data.

## Source Validation

When presenting information fetched from the web:

1. **Verify the domain** — Only trust content from the authoritative domains listed above or other `.gov.au` sites.
2. **Check the date** — Note when the page was last updated. Warn the ranger if the information may be outdated.
3. **Cross-reference** — Where possible, compare fetched content with conservation docs to confirm consistency.
4. **Disclose the source** — Always tell the ranger which URL the information came from so they can verify independently.
5. **Handle fetch failures gracefully** — If a URL is unreachable, inform the ranger and suggest alternative sources or conservation docs.
