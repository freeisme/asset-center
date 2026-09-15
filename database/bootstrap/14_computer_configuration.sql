USE office_asset_mgmt;

SET NAMES utf8mb4;

SET @add_computer_cpu := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND column_name = 'cpu') = 0,
  'ALTER TABLE computer_asset ADD COLUMN cpu VARCHAR(128) NULL AFTER model',
  'SELECT 1'
);
PREPARE add_computer_cpu_stmt FROM @add_computer_cpu;
EXECUTE add_computer_cpu_stmt;
DEALLOCATE PREPARE add_computer_cpu_stmt;

SET @add_computer_memory := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND column_name = 'memory') = 0,
  'ALTER TABLE computer_asset ADD COLUMN memory VARCHAR(64) NULL AFTER cpu',
  'SELECT 1'
);
PREPARE add_computer_memory_stmt FROM @add_computer_memory;
EXECUTE add_computer_memory_stmt;
DEALLOCATE PREPARE add_computer_memory_stmt;

SET @add_computer_storage := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND column_name = 'storage') = 0,
  'ALTER TABLE computer_asset ADD COLUMN storage VARCHAR(128) NULL AFTER memory',
  'SELECT 1'
);
PREPARE add_computer_storage_stmt FROM @add_computer_storage;
EXECUTE add_computer_storage_stmt;
DEALLOCATE PREPARE add_computer_storage_stmt;

SET @add_computer_gpu := IF(
  (SELECT COUNT(*) FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND column_name = 'gpu') = 0,
  'ALTER TABLE computer_asset ADD COLUMN gpu VARCHAR(128) NULL AFTER storage',
  'SELECT 1'
);
PREPARE add_computer_gpu_stmt FROM @add_computer_gpu;
EXECUTE add_computer_gpu_stmt;
DEALLOCATE PREPARE add_computer_gpu_stmt;
