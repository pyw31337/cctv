CREATE TABLE IF NOT EXISTS camera_quality_rollups (
  bucket TEXT NOT NULL,
  camera_id TEXT NOT NULL,
  camera_name TEXT,
  source TEXT,
  region TEXT,
  samples INTEGER NOT NULL DEFAULT 0,
  success INTEGER NOT NULL DEFAULT 0,
  failure INTEGER NOT NULL DEFAULT 0,
  fallback INTEGER NOT NULL DEFAULT 0,
  slow INTEGER NOT NULL DEFAULT 0,
  first_frame_ms_sum INTEGER NOT NULL DEFAULT 0,
  fail_ms_sum INTEGER NOT NULL DEFAULT 0,
  stall_count_sum INTEGER NOT NULL DEFAULT 0,
  width_sum INTEGER NOT NULL DEFAULT 0,
  height_sum INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (bucket, camera_id)
);

CREATE INDEX IF NOT EXISTS idx_camera_quality_rollups_bucket ON camera_quality_rollups(bucket);
CREATE INDEX IF NOT EXISTS idx_camera_quality_rollups_source_bucket ON camera_quality_rollups(source, bucket);
CREATE INDEX IF NOT EXISTS idx_camera_quality_rollups_region_bucket ON camera_quality_rollups(region, bucket);
