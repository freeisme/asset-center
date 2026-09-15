SET NAMES utf8mb4;

-- 办公终端库存型号的入库日期以关联采购入库记录中最早的一次为准。
-- 仅回填空值，避免覆盖已经人工确认过的日期；重复执行不会改变结果。
DROP TEMPORARY TABLE IF EXISTS tmp_computer_inbound_dates;

CREATE TEMPORARY TABLE tmp_computer_inbound_dates (
  model_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
  first_inbound_date DATE NOT NULL
);

INSERT INTO tmp_computer_inbound_dates (model_id, first_inbound_date)
SELECT
  purchase.model_id,
  MIN(purchase.inbound_date)
FROM inventory_purchase_log purchase
JOIN non_asset_type purchase_type
  ON purchase_type.non_asset_type_id = purchase.non_asset_type_id
WHERE purchase.is_active = 1
  AND purchase.model_id IS NOT NULL
  AND purchase.inbound_date IS NOT NULL
  AND (
    LOWER(TRIM(purchase_type.type_code)) IN ('computer', 'pc')
    OR TRIM(purchase_type.type_name) IN ('电脑', '办公终端', '办公设备终端')
  )
GROUP BY purchase.model_id;

UPDATE it_inventory_model m
JOIN non_asset_type t
  ON t.non_asset_type_id = m.non_asset_type_id
JOIN tmp_computer_inbound_dates inbound
  ON inbound.model_id = m.model_id
SET m.inbound_date = inbound.first_inbound_date
WHERE m.inbound_date IS NULL
  AND (
    LOWER(TRIM(t.type_code)) IN ('computer', 'pc')
    OR TRIM(t.type_name) IN ('电脑', '办公终端', '办公设备终端')
  );

DROP TEMPORARY TABLE tmp_computer_inbound_dates;
