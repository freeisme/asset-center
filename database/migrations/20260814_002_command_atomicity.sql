USE office_asset_mgmt;

SET NAMES utf8mb4;

ALTER TABLE api_idempotency_key
  MODIFY COLUMN response_json JSON NULL;

ALTER TABLE inventory_allocation_history
  ADD COLUMN stock_adjusted TINYINT(1) NOT NULL DEFAULT 1 AFTER quantity;

UPDATE inventory_allocation_history
SET stock_adjusted = 1
WHERE stock_adjusted IS NULL;
