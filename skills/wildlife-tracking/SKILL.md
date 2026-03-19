---
name: wildlife-tracking
description: Instructions for recording wildlife sightings, IUCN conservation status categories, required fields, and observation best practices
allowed-tools:
  - create_sighting
  - query_by_species
  - query_by_location
  - query_by_status
---

# Wildlife Tracking

## Recording Sightings

When recording a wildlife sighting, always collect and verify the following required fields before calling `create_sighting`:

| Field | Description | Example |
|-------|-------------|---------|
| **species** | Common or scientific name of the species observed | Eastern Grey Kangaroo |
| **latitude** | Decimal degrees within Australian bounds (-44 to -10) | -33.8688 |
| **longitude** | Decimal degrees within Australian bounds (113 to 154) | 151.2093 |
| **date** | ISO 8601 date of the observation (must not be in the future) | 2025-01-15 |
| **conservation_status** | IUCN category (see below) | least_concern |
| **observer_notes** | Free-text description of behaviour, habitat, and conditions | Feeding near creek bed at dusk |

## IUCN Conservation Status Categories

Use one of the following standardised values for `conservation_status`:

- **critically_endangered** — Extremely high risk of extinction in the wild
- **endangered** — Very high risk of extinction in the wild
- **vulnerable** — High risk of extinction in the wild
- **near_threatened** — Close to qualifying for a threatened category in the near future
- **least_concern** — Widespread and abundant, lowest risk

Always confirm the correct status with the ranger if uncertain. When in doubt, query existing sightings for the same species to check previously recorded statuses.

## Querying Sightings

- Use `query_by_species` to find historical records for a particular species within a date range.
- Use `query_by_location` to discover what has been sighted near a specific coordinate and radius (in kilometres).
- Use `query_by_status` to find all sightings of species with a particular conservation status, useful for monitoring endangered populations.

## Wildlife Observation Best Practices

1. **Minimise disturbance** — Observe from a safe distance. Do not approach nesting sites or dens.
2. **Record conditions** — Note weather, time of day, habitat type, and animal behaviour in observer notes.
3. **Be precise with location** — Use GPS coordinates rather than place names for accuracy.
4. **Photograph when possible** — Reference photos help verify species identification later.
5. **Report injured wildlife** — If the animal appears injured or distressed, note this prominently and follow local wildlife rescue procedures.
6. **Check for duplicates** — Before creating a new sighting, query recent records for the same species and location to avoid duplicate entries.
