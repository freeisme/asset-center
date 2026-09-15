USE office_asset_mgmt;

SET NAMES utf8mb4;

-- Organization tree.
SELECT
  org_code AS `组织编码`,
  org_name AS `组织名称`,
  parent_org_unit_id AS `上级组织ID`,
  org_level AS `层级`,
  sort_order AS `排序`,
  organization_path AS `组织路径`,
  organization_code_path AS `组织编码路径`
FROM v_org_unit_tree
ORDER BY sort_path;

-- Employees ordered by organization tree.
SELECT
  org_code AS `组织编码`,
  organization_name AS `所属组织`,
  organization_path AS `组织路径`,
  employee_no AS `人员编号`,
  employee_name AS `人员姓名`,
  department AS `部门`,
  position_name AS `岗位`,
  employment_status AS `人员状态`,
  office_devices AS `办公设备清单`
FROM v_employee_org_tree
ORDER BY tree_sort_key, employee_no;

-- Required computer table view.
SELECT
  device_name AS `设备名`,
  organization_name AS `所属组织`,
  organization_path AS `组织路径`,
  device_type AS `设备类型`,
  brand AS `设备品牌`,
  model AS `型号`,
  fixed_asset_code AS `固资编码`,
  purchase_date AS `购置日期`,
  registered_date AS `注册日期`,
  sn_st AS `SN_ST`,
  wifi_mac AS `Wifi_MAC`,
  ethernet_mac AS `网口_MAC`,
  location AS `位置`,
  department AS `部门`,
  position_name AS `岗位`,
  current_user_name AS `使用用户`,
  it_asset_status AS `IT资产状态`
FROM v_computer_asset_detail
ORDER BY organization_sort_path, device_name;

-- Detailed employee-to-device rows.
SELECT
  employee_no AS `人员编号`,
  employee_name AS `人员姓名`,
  organization_path AS `组织路径`,
  device_category AS `设备类别`,
  device_display_name AS `设备显示名称`,
  model AS `型号`,
  quantity AS `数量`
FROM v_employee_office_devices
ORDER BY organization_sort_path, employee_name, device_category, device_display_name;

-- One row per employee with a readable device list.
SELECT
  employee_no AS `人员编号`,
  employee_name AS `人员姓名`,
  organization_name AS `所属组织`,
  organization_path AS `组织路径`,
  department AS `部门`,
  position_name AS `岗位`,
  office_devices AS `办公设备清单`
FROM v_employee_office_device_summary
ORDER BY organization_sort_path, employee_name;
