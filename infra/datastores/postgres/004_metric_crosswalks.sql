-- metric_crosswalks: maps a source's native metric name onto a canonical metric_definition.
-- This table was inserted into by 005_eval_fabric_runtime_seed.sql and read by the eval-fabric-api
-- (get_frontier_provenance LEFT JOIN, get_metric_crosswalks ORDER BY created_at) but its CREATE TABLE
-- existed nowhere in version control, so a fresh eval_fabric_migrate failed at 005. Added here, ordered
-- before 005. Columns are fixed by existing usage (005 insert list + the two read queries); created_at is
-- required by get_metric_crosswalks' `order by created_at desc`. No FKs: get_frontier_provenance LEFT JOINs
-- it, matching the standalone-by-text-id convention of source_descriptors / metric_definitions.
create table if not exists metric_crosswalks (
  metric_crosswalk_id text primary key,
  source_descriptor_id text not null,
  source_metric_name text not null,
  canonical_metric_definition_id text not null,
  transform_notes text not null,
  created_at timestamptz not null default now()
);
