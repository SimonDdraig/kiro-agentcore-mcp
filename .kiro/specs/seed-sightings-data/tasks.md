# Tasks — Seed Sightings Data

## Task 1: Seed DynamoDB with 1000 example wildlife sightings

- [x] 1. Create seed script at `scripts/seed_sightings.py` that inserts 1000 realistic wildlife sighting records into the BushRangerSightings DynamoDB table
  - [x] 1.1 Define 30 Australian species with accurate IUCN conservation statuses
  - [x] 1.2 Define 20 real Australian park/reserve locations with GPS coordinates
  - [x] 1.3 Define 10 biologically accurate, species-specific observer notes per species (300 total) — each note must reflect real behaviours, diet, reproduction, and ecology for that species (e.g. kangaroos have joeys in pouches, not eggs; platypus forage in creeks using electroreception). No generic templates shared across species.
  - [x] 1.4 Generate random dates spanning 2024-01-01 to 2026-03-29
  - [x] 1.5 Jitter coordinates around base locations so sightings cluster naturally
  - [x] 1.6 Use DynamoDB batch_writer for efficient writes (25 items per batch)
  - [x] 1.7 Replicate the exact sort key format (`date#lochash`) from the wildlife sightings MCP server
  - [x] 1.8 Print a summary of species and conservation status distribution on completion

## Task 2: Run the seed script

- [x] 2. Execute `scripts/seed_sightings.py` to populate the BushRangerSightings DynamoDB table with 1000 records
  - [x] 2.1 Run `AWS_DEFAULT_REGION=us-east-1 python scripts/seed_sightings.py`
  - [x] 2.2 Verify the output shows 1000 records written and a species/status distribution summary
