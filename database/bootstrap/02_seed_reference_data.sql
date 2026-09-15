USE office_asset_mgmt;

SET NAMES utf8mb4;

-- Generic reference data only. Create the organization hierarchy in the
-- application after deployment; do not place company personnel or assets here.
INSERT INTO non_asset_type (type_code, type_name, unit_name)
VALUES
  ('monitor', '显示屏', '件'),
  ('mouse', '鼠标', '件'),
  ('keyboard', '键盘', '件'),
  ('docking_station', '拓展坞', '件'),
  ('headset', '耳机', '件'),
  ('usb_hub', 'USB集线器', '件'),
  ('webcam', '摄像头', '件')
ON DUPLICATE KEY UPDATE
  type_name = VALUES(type_name),
  unit_name = VALUES(unit_name),
  is_active = 1,
  updated_at = CURRENT_TIMESTAMP;
