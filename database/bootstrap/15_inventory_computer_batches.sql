USE office_asset_mgmt;

SET NAMES utf8mb4;

INSERT INTO non_asset_type (type_code, type_name, unit_name)
VALUES ('computer', '电脑', '台')
ON DUPLICATE KEY UPDATE
  type_name = VALUES(type_name),
  unit_name = VALUES(unit_name),
  is_active = 1,
  updated_at = CURRENT_TIMESTAMP;

SET @add_inventory_model_batch_key := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'it_inventory_model'
     AND column_name = 'batch_key') = 0,
  'ALTER TABLE it_inventory_model ADD COLUMN batch_key VARCHAR(64) NOT NULL DEFAULT '''' AFTER model_name',
  'SELECT 1'
);
PREPARE add_inventory_model_batch_key_stmt FROM @add_inventory_model_batch_key;
EXECUTE add_inventory_model_batch_key_stmt;
DEALLOCATE PREPARE add_inventory_model_batch_key_stmt;

SET @add_inventory_model_inbound_date := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'it_inventory_model'
     AND column_name = 'inbound_date') = 0,
  'ALTER TABLE it_inventory_model ADD COLUMN inbound_date DATE NULL AFTER quantity',
  'SELECT 1'
);
PREPARE add_inventory_model_inbound_date_stmt FROM @add_inventory_model_inbound_date;
EXECUTE add_inventory_model_inbound_date_stmt;
DEALLOCATE PREPARE add_inventory_model_inbound_date_stmt;

SET @add_inventory_model_cpu := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'it_inventory_model'
     AND column_name = 'cpu') = 0,
  'ALTER TABLE it_inventory_model ADD COLUMN cpu VARCHAR(128) NULL AFTER inbound_date',
  'SELECT 1'
);
PREPARE add_inventory_model_cpu_stmt FROM @add_inventory_model_cpu;
EXECUTE add_inventory_model_cpu_stmt;
DEALLOCATE PREPARE add_inventory_model_cpu_stmt;

SET @add_inventory_model_memory := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'it_inventory_model'
     AND column_name = 'memory') = 0,
  'ALTER TABLE it_inventory_model ADD COLUMN memory VARCHAR(64) NULL AFTER cpu',
  'SELECT 1'
);
PREPARE add_inventory_model_memory_stmt FROM @add_inventory_model_memory;
EXECUTE add_inventory_model_memory_stmt;
DEALLOCATE PREPARE add_inventory_model_memory_stmt;

SET @add_inventory_model_storage := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'it_inventory_model'
     AND column_name = 'storage') = 0,
  'ALTER TABLE it_inventory_model ADD COLUMN storage VARCHAR(128) NULL AFTER memory',
  'SELECT 1'
);
PREPARE add_inventory_model_storage_stmt FROM @add_inventory_model_storage;
EXECUTE add_inventory_model_storage_stmt;
DEALLOCATE PREPARE add_inventory_model_storage_stmt;

SET @add_inventory_model_gpu := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'it_inventory_model'
     AND column_name = 'gpu') = 0,
  'ALTER TABLE it_inventory_model ADD COLUMN gpu VARCHAR(128) NULL AFTER storage',
  'SELECT 1'
);
PREPARE add_inventory_model_gpu_stmt FROM @add_inventory_model_gpu;
EXECUTE add_inventory_model_gpu_stmt;
DEALLOCATE PREPARE add_inventory_model_gpu_stmt;

UPDATE it_inventory_model
SET batch_key = ''
WHERE batch_key IS NULL;

SET @drop_old_inventory_model_uq := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = DATABASE()
     AND table_name = 'it_inventory_model'
     AND index_name = 'uq_it_inventory_model') > 0
  AND
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = DATABASE()
     AND table_name = 'it_inventory_model'
     AND index_name = 'uq_it_inventory_model'
     AND column_name = 'batch_key') = 0,
  'ALTER TABLE it_inventory_model DROP INDEX uq_it_inventory_model',
  'SELECT 1'
);
PREPARE drop_old_inventory_model_uq_stmt FROM @drop_old_inventory_model_uq;
EXECUTE drop_old_inventory_model_uq_stmt;
DEALLOCATE PREPARE drop_old_inventory_model_uq_stmt;

SET @add_inventory_model_uq := IF(
  (SELECT COUNT(*) FROM information_schema.statistics
   WHERE table_schema = DATABASE()
     AND table_name = 'it_inventory_model'
     AND index_name = 'uq_it_inventory_model') = 0,
  'ALTER TABLE it_inventory_model ADD UNIQUE KEY uq_it_inventory_model (brand_id, model_name, batch_key)',
  'SELECT 1'
);
PREPARE add_inventory_model_uq_stmt FROM @add_inventory_model_uq;
EXECUTE add_inventory_model_uq_stmt;
DEALLOCATE PREPARE add_inventory_model_uq_stmt;
