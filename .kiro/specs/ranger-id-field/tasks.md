# Implementation Plan: Ranger ID Field

## Overview

Add ranger attribution to the wildlife sighting system by introducing a `ranger_id` field on sighting records, creating a `BushRangers` DynamoDB table for ranger profiles, and updating the seed script to generate ranger data. All changes are backward-compatible — existing tests pass without modification.

## Tasks

- [x] 1. Update data models
  - [x] 1.1 Add `ranger_id` field to `SightingRecord` in `models/sightings.py`
    - Add `ranger_id: str = ""` after the existing `sighting_id` field
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Create `models/rangers.py` with `RangerRecord` dataclass
    - Define `TABLE_NAME = "BushRangers"` and `PARTITION_KEY = "ranger_id"` constants
    - Define `RangerRecord` dataclass with fields: `ranger_id`, `name`, `email`, `region`, `phone`, `active` (bool), `start_date` (str)
    - _Requirements: 4.2_

- [x] 2. Update MCP server to handle ranger_id
  - [x] 2.1 Add `ranger_id` parameter to `create_sighting` in `services/mcp_servers/wildlife_sightings/server.py`
    - Add optional `ranger_id: str = ""` parameter to the function signature
    - Include `ranger_id` in the DynamoDB item dict passed to `put_item`
    - Include `ranger_id` in the response dict returned to the caller
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 2.2 Update `_record_to_dict` to include `ranger_id`
    - Add `"ranger_id": item.get("ranger_id", "")` to the returned dict
    - This covers all three query tools (`query_by_species`, `query_by_location`, `query_by_status`)
    - _Requirements: 3.1, 3.2_

- [x] 3. Checkpoint — Verify existing tests still pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add BushRangers DynamoDB table to CDK stack
  - [x] 4.1 Add `_create_rangers_table` method in `infra/stacks/bush_ranger_stack.py`
    - Create a new DynamoDB table named `BushRangers` with `ranger_id` (String) as partition key
    - Use `PAY_PER_REQUEST` billing mode and `DESTROY` removal policy to match existing table pattern
    - Call the new method from `__init__` alongside the existing sightings table creation
    - _Requirements: 4.1, 4.3_

- [x] 5. Update seed script with ranger data
  - [x] 5.1 Add sample ranger profiles to `scripts/seed_sightings.py`
    - Define a `RANGERS` list with at least 10 ranger dicts containing `ranger_id`, `name`, `email`, `region`, `phone`, `active`, `start_date`
    - Regions should match existing `LOCATIONS` entries
    - _Requirements: 5.1_

  - [x] 5.2 Write ranger records to BushRangers table
    - Add a function to batch-write all ranger records to the `BushRangers` table using `batch_writer`
    - Call it from the main seed flow before writing sightings
    - _Requirements: 5.2_

  - [x] 5.3 Assign `ranger_id` to each generated sighting record
    - Randomly select a `ranger_id` from the `RANGERS` list for each sighting
    - Include `ranger_id` in every sighting item written to DynamoDB
    - _Requirements: 5.3, 5.4_

- [x] 6. Checkpoint — Run seed script dry-check and verify model consistency
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Add unit and property-based tests
  - [x] 7.1 Add unit tests for ranger_id behavior in `tests/test_wildlife_sightings.py`
    - `test_create_sighting_with_ranger_id` — verify ranger_id is stored and returned
    - `test_create_sighting_without_ranger_id` — verify default empty string behavior
    - `test_record_to_dict_legacy_item` — verify legacy items without ranger_id get `""`
    - `test_ranger_record_dataclass` — verify RangerRecord fields
    - `test_sample_rangers_count` — verify at least 10 sample rangers defined
    - _Requirements: 2.2, 2.3, 2.4, 3.1, 3.2, 4.2, 5.1, 6.1_

  - [x] 7.2 Write property test: Ranger ID round-trip through create_sighting
    - **Property 1: Ranger ID round-trip through create_sighting**
    - Generate random non-empty strings for `ranger_id` and valid sighting params; call `create_sighting` with mocked DynamoDB; assert `put_item` item contains the `ranger_id` and response dict matches
    - **Validates: Requirements 2.2, 2.4**

  - [x] 7.3 Write property test: Create response always contains ranger_id
    - **Property 2: Create response always contains ranger_id**
    - Generate random valid sighting params, optionally with or without `ranger_id`; assert response dict always has `ranger_id` key of type `str`
    - **Validates: Requirements 2.4, 2.3**

  - [x] 7.4 Write property test: Record-to-dict always includes ranger_id
    - **Property 3: Record-to-dict always includes ranger_id**
    - Generate random DynamoDB item dicts, some with `ranger_id` and some without; assert `_record_to_dict` output always contains `ranger_id` as a string, matching input when present or defaulting to `""`
    - **Validates: Requirements 3.1, 3.2**

  - [x] 7.5 Write property test: Seed sighting ranger_ids are from the valid ranger set
    - **Property 4: Seed sighting ranger_ids are from the valid ranger set**
    - Generate random sighting records using the seed script's generation logic; assert each `ranger_id` is in the set of defined sample ranger IDs
    - **Validates: Requirements 5.3, 5.4**

- [x] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis
- Unit tests validate specific examples and edge cases
- The design uses Python throughout — all code examples use Python
