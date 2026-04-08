-- Dolt Observation table
CREATE TABLE observations (
  observation_id VARCHAR(191) PRIMARY KEY,
  source_system VARCHAR(128) NOT NULL,
  source_record_id VARCHAR(255),
  observed_at DATETIME(6) NOT NULL,
  normalized_payload JSON,
  trust_class VARCHAR(32),
  content_hash VARCHAR(255) NOT NULL,
  identity_hash VARCHAR(255) NOT NULL,
  lineage_hash VARCHAR(255),
  state VARCHAR(32) DEFAULT 'active',
  created_at DATETIME(6) NOT NULL
);
