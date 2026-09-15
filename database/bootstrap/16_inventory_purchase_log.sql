USE office_asset_mgmt;

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS inventory_purchase_log (
  purchase_log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  type_name VARCHAR(128) NOT NULL DEFAULT '',
  brand_name VARCHAR(128) NOT NULL DEFAULT '',
  model_name VARCHAR(128) NOT NULL DEFAULT '',
  quantity INT UNSIGNED NOT NULL,
  inbound_date DATE NULL,
  cpu VARCHAR(128) NULL,
  memory VARCHAR(64) NULL,
  storage VARCHAR(128) NULL,
  gpu VARCHAR(128) NULL,
  source_label VARCHAR(255) NOT NULL DEFAULT '',
  note VARCHAR(500) NOT NULL DEFAULT '',
  source_movement_log_id BIGINT UNSIGNED NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (purchase_log_id),
  UNIQUE KEY uq_inventory_purchase_source (source_movement_log_id),
  KEY idx_inventory_purchase_date (inbound_date, purchase_log_id),
  KEY idx_inventory_purchase_type (type_name, inbound_date),
  CONSTRAINT ck_inventory_purchase_quantity CHECK (quantity > 0),
  CONSTRAINT ck_inventory_purchase_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

-- 非电脑库存不再保留电脑配置或库存型号入库日期。
UPDATE it_inventory_model model
JOIN non_asset_type type
  ON type.non_asset_type_id = model.non_asset_type_id
SET model.inbound_date = NULL,
    model.cpu = NULL,
    model.memory = NULL,
    model.storage = NULL,
    model.gpu = NULL
WHERE NOT (
  LOWER(TRIM(type.type_code)) IN ('computer', 'pc')
  OR TRIM(type.type_name) = '电脑'
);

-- 将已有的外部导入、电脑入库、手工新增流水回填为采购入库记录。
-- 回填只执行一次：source_movement_log_id 使用原流水唯一关联。
INSERT IGNORE INTO inventory_purchase_log (
  type_name,
  brand_name,
  model_name,
  quantity,
  inbound_date,
  cpu,
  memory,
  storage,
  gpu,
  source_label,
  note,
  source_movement_log_id,
  created_at
)
SELECT
  movement.type_name,
  movement.brand_name,
  movement.model_name,
  movement.quantity,
  DATE(movement.occurred_at),
  CASE
    WHEN TRIM(movement.type_name) = '电脑' THEN (
      SELECT model.cpu
      FROM it_inventory_model model
      JOIN it_inventory_brand brand
        ON brand.brand_id = model.brand_id
      JOIN non_asset_type type
        ON type.non_asset_type_id = model.non_asset_type_id
      WHERE type.type_name = movement.type_name
        AND brand.brand_name = movement.brand_name
        AND model.model_name = movement.model_name
      ORDER BY model.model_id DESC
      LIMIT 1
    )
    ELSE NULL
  END,
  CASE
    WHEN TRIM(movement.type_name) = '电脑' THEN (
      SELECT model.memory
      FROM it_inventory_model model
      JOIN it_inventory_brand brand
        ON brand.brand_id = model.brand_id
      JOIN non_asset_type type
        ON type.non_asset_type_id = model.non_asset_type_id
      WHERE type.type_name = movement.type_name
        AND brand.brand_name = movement.brand_name
        AND model.model_name = movement.model_name
      ORDER BY model.model_id DESC
      LIMIT 1
    )
    ELSE NULL
  END,
  CASE
    WHEN TRIM(movement.type_name) = '电脑' THEN (
      SELECT model.storage
      FROM it_inventory_model model
      JOIN it_inventory_brand brand
        ON brand.brand_id = model.brand_id
      JOIN non_asset_type type
        ON type.non_asset_type_id = model.non_asset_type_id
      WHERE type.type_name = movement.type_name
        AND brand.brand_name = movement.brand_name
        AND model.model_name = movement.model_name
      ORDER BY model.model_id DESC
      LIMIT 1
    )
    ELSE NULL
  END,
  CASE
    WHEN TRIM(movement.type_name) = '电脑' THEN (
      SELECT model.gpu
      FROM it_inventory_model model
      JOIN it_inventory_brand brand
        ON brand.brand_id = model.brand_id
      JOIN non_asset_type type
        ON type.non_asset_type_id = model.non_asset_type_id
      WHERE type.type_name = movement.type_name
        AND brand.brand_name = movement.brand_name
        AND model.model_name = movement.model_name
      ORDER BY model.model_id DESC
      LIMIT 1
    )
    ELSE NULL
  END,
  movement.source_label,
  movement.note,
  movement.movement_log_id,
  movement.occurred_at
FROM inventory_movement_log movement
WHERE movement.movement_direction = 'increase'
  AND movement.source_label IN ('外部导入', '电脑入库', '手工新增');
