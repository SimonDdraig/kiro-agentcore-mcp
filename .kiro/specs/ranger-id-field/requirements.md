# Requirements Document

## Introduction

Add a `ranger_id` field to the Bush Ranger wildlife sighting system so that each sighting record tracks which ranger made the observation. Additionally, create a new BushRangers DynamoDB table to store ranger profile information. This involves updating the data model, the MCP server (create and query paths), creating the Rangers table infrastructure, and the seed script that populates sample data.

## Glossary

- **Sighting_Record**: A single wildlife observation stored in the BushRangerSightings DynamoDB table, keyed by species (partition key) and date_location (sort key).
- **MCP_Server**: The Wildlife Sightings MCP server (`services/mcp_servers/wildlife_sightings/server.py`) that exposes tools for creating and querying sightings.
- **Seed_Script**: The Python script at `scripts/seed_sightings.py` that generates 1000 sample sighting records and writes them to DynamoDB.
- **Sighting_Model**: The shared dataclass in `models/sightings.py` that defines the shape of a sighting record.
- **Ranger_ID**: A string identifier for the park ranger who recorded a sighting (e.g. "ranger-001").
- **Rangers_Table**: A DynamoDB table (BushRangers) that stores ranger profile information, keyed by ranger_id.
- **Ranger_Record**: A single ranger profile stored in the BushRangers table containing operational details about a park ranger.

## Requirements

### Requirement 1: Add ranger_id to the Sighting Data Model

**User Story:** As a developer, I want the sighting data model to include a ranger_id field, so that the codebase has a single source of truth for the sighting record shape including ranger attribution.

#### Acceptance Criteria

1. THE Sighting_Model SHALL include a `ranger_id` field of type string with a default value of empty string.
2. WHEN a Sighting_Record is stored in DynamoDB, THE Sighting_Record SHALL contain a `ranger_id` attribute.

### Requirement 2: Accept ranger_id When Creating Sightings

**User Story:** As a park ranger, I want to provide my ranger ID when recording a sighting, so that the observation is attributed to me.

#### Acceptance Criteria

1. THE MCP_Server create_sighting tool SHALL accept an optional `ranger_id` parameter of type string.
2. WHEN a sighting is created with a `ranger_id` value, THE MCP_Server SHALL store the `ranger_id` in the Sighting_Record written to DynamoDB.
3. WHEN a sighting is created without a `ranger_id` value, THE MCP_Server SHALL store an empty string as the `ranger_id` in the Sighting_Record.
4. THE MCP_Server SHALL include `ranger_id` in the response dict returned after creating a sighting.

### Requirement 3: Return ranger_id When Querying Sightings

**User Story:** As a park ranger, I want to see which ranger recorded each sighting when I query sighting data, so that I can follow up with the original observer.

#### Acceptance Criteria

1. WHEN a Sighting_Record is converted to a response dict, THE MCP_Server SHALL include the `ranger_id` field in the output.
2. WHEN a Sighting_Record has no `ranger_id` attribute (legacy data), THE MCP_Server SHALL return an empty string for `ranger_id`.

### Requirement 4: Create BushRangers DynamoDB Table

**User Story:** As a system administrator, I want a dedicated Rangers table to store ranger profile information, so that sighting records can be linked to detailed ranger data.

#### Acceptance Criteria

1. THE Rangers_Table SHALL use `ranger_id` (string) as the partition key.
2. EACH Ranger_Record SHALL contain the following attributes: `ranger_id` (string), `name` (string), `email` (string), `region` (string), `phone` (string), `active` (boolean), `start_date` (string, ISO date format).
3. THE Rangers_Table SHALL be provisioned in the same region as the BushRangerSightings table.

### Requirement 5: Seed Script Generates ranger_id Values and Ranger Records

**User Story:** As a developer, I want the seed script to generate realistic ranger profiles and assign ranger_ids to sample sighting data, so that the development environment has representative records for testing ranger-based queries.

#### Acceptance Criteria

1. THE Seed_Script SHALL define at least 10 sample rangers with realistic names, emails, regions (matching existing LOCATIONS), phone numbers, active status, and start dates.
2. THE Seed_Script SHALL write all sample Ranger_Records to the BushRangers DynamoDB table.
3. WHEN generating a sighting record, THE Seed_Script SHALL assign a randomly selected ranger_id from the sample ranger list.
4. THE Seed_Script SHALL include the `ranger_id` field in every Sighting_Record written to DynamoDB.

### Requirement 6: Existing Tests Remain Passing

**User Story:** As a developer, I want existing unit and property-based tests to continue passing after the ranger_id field is added, so that the change does not introduce regressions.

#### Acceptance Criteria

1. WHEN the ranger_id field is added, THE MCP_Server unit tests SHALL pass without modification to existing assertions (ranger_id is optional with a default).
2. WHEN the ranger_id field is added, THE MCP_Server property-based tests SHALL continue to validate round-trip, filtering, and validation properties.
