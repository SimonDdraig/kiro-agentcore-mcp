---
name: conservation-research
description: Instructions for searching conservation documents, document categories, cross-referencing species data, and summarizing findings
allowed-tools:
  - list_documents
  - get_document
  - search_documents
---

# Conservation Research

## Document Categories

Conservation documents are organised into three categories:

| Category | Contents | Examples |
|----------|----------|----------|
| **species** | Species fact sheets with habitat, diet, behaviour, threats, and conservation status | koala.md, platypus.md |
| **management_plans** | National park and reserve management plans, land-use strategies | kakadu_plan.md |
| **emergency** | Emergency response procedures for bushfires, floods, and wildlife rescue | bushfire_response.md |

## Search Strategies

### Finding Documents by Category
Use `list_documents` with a category filter to browse available documents within a specific category. This is the best starting point when you know the type of information needed but not the exact document.

### Keyword Search
Use `search_documents` with a keyword to find documents containing specific terms. Tips for effective searches:
- Use species common names (e.g., "koala") or scientific names
- Search for specific topics (e.g., "habitat", "breeding", "fire response")
- Try broader terms if specific searches return no results

### Retrieving a Specific Document
Use `get_document` with the document key when you know exactly which document is needed. The key is returned by `list_documents` or `search_documents`.

## Cross-Referencing

When answering ranger questions, cross-reference multiple document types for comprehensive answers:

1. **Species + Management Plans** — Check if a species fact sheet mentions a specific park, then retrieve the management plan for that park to find relevant conservation actions.
2. **Species + Emergency** — If a ranger asks about protecting a species during a bushfire, combine the species fact sheet (habitat, behaviour) with the emergency bushfire response procedures.
3. **Management Plans + Emergency** — When planning field activities in a park, review both the management plan (permitted activities, sensitive areas) and relevant emergency procedures.

## Summarising Findings for Field Use

When presenting research findings to rangers:

1. **Lead with the answer** — State the key finding first, then provide supporting details.
2. **Keep it practical** — Focus on actionable information relevant to field operations.
3. **Cite sources** — Reference the specific document(s) used so rangers can read the full text if needed.
4. **Flag uncertainties** — If documents contain conflicting information or gaps, note this clearly.
5. **Suggest follow-up** — If the available documents do not fully answer the question, suggest using the web-research skill to check government sources.
