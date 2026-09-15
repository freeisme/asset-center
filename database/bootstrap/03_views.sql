USE office_asset_mgmt;

SET NAMES utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

DROP VIEW IF EXISTS v_employee_org_tree;
DROP VIEW IF EXISTS v_employee_office_device_summary;
DROP VIEW IF EXISTS v_employee_office_devices;
DROP VIEW IF EXISTS v_org_unit_tree;
DROP VIEW IF EXISTS v_computer_asset_detail;

CREATE VIEW v_org_unit_tree AS
WITH RECURSIVE org_tree AS (
  SELECT
    ou.org_unit_id,
    ou.parent_org_unit_id,
    ou.org_code,
    ou.org_name,
    ou.sort_order,
    0 AS org_level,
    CAST(CONCAT(LPAD(ou.sort_order, 6, '0'), '-', ou.org_code) AS CHAR(2000)) AS sort_path,
    CAST(ou.org_name AS CHAR(2000)) AS organization_path,
    CAST(ou.org_code AS CHAR(2000)) AS organization_code_path
  FROM org_unit ou
  WHERE ou.parent_org_unit_id IS NULL
    AND ou.is_active = 1

  UNION ALL

  SELECT
    child.org_unit_id,
    child.parent_org_unit_id,
    child.org_code,
    child.org_name,
    child.sort_order,
    parent.org_level + 1 AS org_level,
    CAST(
      CONCAT(
        parent.sort_path,
        '/',
        LPAD(child.sort_order, 6, '0'),
        '-',
        child.org_code
      ) AS CHAR(2000)
    ) AS sort_path,
    CAST(CONCAT(parent.organization_path, ' / ', child.org_name) AS CHAR(2000)) AS organization_path,
    CAST(CONCAT(parent.organization_code_path, ' / ', child.org_code) AS CHAR(2000)) AS organization_code_path
  FROM org_unit child
  JOIN org_tree parent
    ON parent.org_unit_id = child.parent_org_unit_id
  WHERE child.is_active = 1
)
SELECT
  org_unit_id,
  parent_org_unit_id,
  org_code,
  org_name,
  sort_order,
  org_level,
  sort_path,
  organization_path,
  organization_code_path
FROM org_tree;

CREATE VIEW v_computer_asset_detail AS
SELECT
  ca.computer_id,
  ca.device_name,
  COALESCE(tree.org_code, ou.org_code, 'UNASSIGNED') AS org_code,
  COALESCE(tree.org_name, ou.org_name) AS organization_name,
  COALESCE(tree.organization_path, ou.org_name, '未分配组织') AS organization_path,
  COALESCE(tree.organization_code_path, ou.org_code, 'UNASSIGNED') AS organization_code_path,
  tree.org_level,
  COALESCE(tree.sort_path, CONCAT('999999-', COALESCE(ou.org_code, 'UNASSIGNED'))) AS organization_sort_path,
  ca.device_type,
  ca.brand,
  ca.model,
  ca.cpu,
  ca.memory,
  ca.storage,
  ca.gpu,
  ca.fixed_asset_code,
  ca.purchase_date,
  ca.registered_date,
  ca.sn_st,
  ca.wifi_mac,
  ca.ethernet_mac,
  ca.location,
  ca.department,
  ca.position_name,
  e.employee_id AS current_user_id,
  e.employee_no AS current_user_no,
  e.employee_name AS current_user_name,
  ca.it_asset_status,
  ca.remarks
FROM computer_asset ca
LEFT JOIN org_unit ou
  ON ou.org_unit_id = ca.org_unit_id
LEFT JOIN v_org_unit_tree tree
  ON tree.org_unit_id = ca.org_unit_id
LEFT JOIN computer_assignment ass
  ON ass.computer_id = ca.computer_id
 AND ass.returned_at IS NULL
 AND ass.assignment_status = 'active'
LEFT JOIN employee e
  ON e.employee_id = ass.employee_id;

CREATE VIEW v_employee_office_devices AS
SELECT
  e.employee_id,
  e.employee_no,
  e.employee_name,
  COALESCE(tree.org_name, ou.org_name, '未分配组织') COLLATE utf8mb4_unicode_ci AS organization_name,
  COALESCE(tree.organization_path, ou.org_name, '未分配组织') COLLATE utf8mb4_unicode_ci AS organization_path,
  COALESCE(tree.organization_code_path, ou.org_code, 'UNASSIGNED') COLLATE utf8mb4_unicode_ci AS organization_code_path,
  tree.org_level,
  COALESCE(tree.sort_path, CONCAT('999999-', COALESCE(ou.org_code, 'UNASSIGNED'))) COLLATE utf8mb4_unicode_ci AS organization_sort_path,
  'computer' COLLATE utf8mb4_unicode_ci AS device_category,
  ca.device_name COLLATE utf8mb4_unicode_ci AS device_name,
  COALESCE(ca.model, '') COLLATE utf8mb4_unicode_ci AS model,
  1 AS quantity,
  ca.device_name COLLATE utf8mb4_unicode_ci AS device_display_name
FROM employee e
LEFT JOIN org_unit ou
  ON ou.org_unit_id = e.org_unit_id
LEFT JOIN v_org_unit_tree tree
  ON tree.org_unit_id = e.org_unit_id
JOIN computer_assignment ass
  ON ass.employee_id = e.employee_id
 AND ass.returned_at IS NULL
 AND ass.assignment_status = 'active'
JOIN computer_asset ca
  ON ca.computer_id = ass.computer_id

UNION ALL

SELECT
  e.employee_id,
  e.employee_no,
  e.employee_name,
  COALESCE(tree.org_name, ou.org_name, '未分配组织') COLLATE utf8mb4_unicode_ci AS organization_name,
  COALESCE(tree.organization_path, ou.org_name, '未分配组织') COLLATE utf8mb4_unicode_ci AS organization_path,
  COALESCE(tree.organization_code_path, ou.org_code, 'UNASSIGNED') COLLATE utf8mb4_unicode_ci AS organization_code_path,
  tree.org_level,
  COALESCE(tree.sort_path, CONCAT('999999-', COALESCE(ou.org_code, 'UNASSIGNED'))) COLLATE utf8mb4_unicode_ci AS organization_sort_path,
  'monitor' COLLATE utf8mb4_unicode_ci AS device_category,
  mu.display_name COLLATE utf8mb4_unicode_ci AS device_name,
  mu.model COLLATE utf8mb4_unicode_ci AS model,
  mu.quantity,
  CASE
    WHEN mu.model = '' THEN mu.display_name
    ELSE CONCAT(mu.display_name, ' ', mu.model)
  END COLLATE utf8mb4_unicode_ci AS device_display_name
FROM employee e
LEFT JOIN org_unit ou
  ON ou.org_unit_id = e.org_unit_id
LEFT JOIN v_org_unit_tree tree
  ON tree.org_unit_id = e.org_unit_id
JOIN employee_monitor_usage mu
  ON mu.employee_id = e.employee_id

UNION ALL

SELECT
  e.employee_id,
  e.employee_no,
  e.employee_name,
  COALESCE(tree.org_name, ou.org_name, '未分配组织') COLLATE utf8mb4_unicode_ci AS organization_name,
  COALESCE(tree.organization_path, ou.org_name, '未分配组织') COLLATE utf8mb4_unicode_ci AS organization_path,
  COALESCE(tree.organization_code_path, ou.org_code, 'UNASSIGNED') COLLATE utf8mb4_unicode_ci AS organization_code_path,
  tree.org_level,
  COALESCE(tree.sort_path, CONCAT('999999-', COALESCE(ou.org_code, 'UNASSIGNED'))) COLLATE utf8mb4_unicode_ci AS organization_sort_path,
  'non_asset' COLLATE utf8mb4_unicode_ci AS device_category,
  nat.type_name COLLATE utf8mb4_unicode_ci AS device_name,
  TRIM(CONCAT_WS(' ', NULLIF(enau.brand, ''), NULLIF(enau.model, ''))) COLLATE utf8mb4_unicode_ci AS model,
  enau.quantity,
  CASE
    WHEN TRIM(CONCAT_WS(' ', NULLIF(enau.brand, ''), NULLIF(enau.model, ''))) = '' THEN nat.type_name
    ELSE CONCAT(nat.type_name, ' ', TRIM(CONCAT_WS(' ', NULLIF(enau.brand, ''), NULLIF(enau.model, ''))))
  END COLLATE utf8mb4_unicode_ci AS device_display_name
FROM employee e
LEFT JOIN org_unit ou
  ON ou.org_unit_id = e.org_unit_id
LEFT JOIN v_org_unit_tree tree
  ON tree.org_unit_id = e.org_unit_id
JOIN employee_non_asset_usage enau
  ON enau.employee_id = e.employee_id
JOIN non_asset_type nat
  ON nat.non_asset_type_id = enau.non_asset_type_id
 AND nat.is_active = 1;

CREATE VIEW v_employee_office_device_summary AS
SELECT
  e.employee_id,
  e.employee_no,
  e.employee_name,
  COALESCE(tree.org_name, ou.org_name, '未分配组织') AS organization_name,
  COALESCE(tree.organization_path, ou.org_name, '未分配组织') AS organization_path,
  COALESCE(tree.organization_code_path, ou.org_code, 'UNASSIGNED') AS organization_code_path,
  tree.org_level,
  COALESCE(tree.sort_path, CONCAT('999999-', COALESCE(ou.org_code, 'UNASSIGNED'))) AS organization_sort_path,
  e.department,
  e.position_name,
  e.employment_status,
  COALESCE(
    GROUP_CONCAT(
      CONCAT(
        d.device_display_name,
        CASE
          WHEN d.quantity > 1 THEN CONCAT(' x', d.quantity)
          ELSE ''
        END
      )
      ORDER BY d.device_category, d.device_display_name
      SEPARATOR ', '
    ),
    ''
  ) AS office_devices
FROM employee e
LEFT JOIN org_unit ou
  ON ou.org_unit_id = e.org_unit_id
LEFT JOIN v_org_unit_tree tree
  ON tree.org_unit_id = e.org_unit_id
LEFT JOIN v_employee_office_devices d
  ON d.employee_id = e.employee_id
GROUP BY
  e.employee_id,
  e.employee_no,
  e.employee_name,
  tree.org_name,
  ou.org_name,
  tree.organization_path,
  tree.organization_code_path,
  tree.org_level,
  tree.sort_path,
  e.department,
  e.position_name,
  e.employment_status;

CREATE VIEW v_employee_org_tree AS
SELECT
  e.employee_id,
  e.employee_no,
  e.employee_name,
  e.department,
  e.position_name,
  e.employment_status,
  COALESCE(tree.org_unit_id, e.org_unit_id) AS org_unit_id,
  tree.parent_org_unit_id,
  COALESCE(tree.org_code, ou.org_code, 'UNASSIGNED') AS org_code,
  COALESCE(tree.org_name, ou.org_name, '未分配组织') AS organization_name,
  COALESCE(tree.organization_path, ou.org_name, '未分配组织') AS organization_path,
  COALESCE(tree.organization_code_path, ou.org_code, 'UNASSIGNED') AS organization_code_path,
  tree.org_level,
  tree.sort_order,
  COALESCE(tree.sort_path, CONCAT('999999-', COALESCE(ou.org_code, 'UNASSIGNED'))) AS organization_sort_path,
  COALESCE(summary.office_devices, '') AS office_devices,
  CONCAT(
    COALESCE(tree.sort_path, CONCAT('999999-', COALESCE(ou.org_code, 'UNASSIGNED'))),
    '/EMP-',
    LPAD(CAST(e.employee_id AS CHAR(20)), 10, '0')
  ) AS tree_sort_key
FROM employee e
LEFT JOIN org_unit ou
  ON ou.org_unit_id = e.org_unit_id
LEFT JOIN v_org_unit_tree tree
  ON tree.org_unit_id = e.org_unit_id
LEFT JOIN v_employee_office_device_summary summary
  ON summary.employee_id = e.employee_id;
