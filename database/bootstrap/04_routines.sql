USE office_asset_mgmt;

SET NAMES utf8mb4;

DROP PROCEDURE IF EXISTS sp_assign_computer;
DROP PROCEDURE IF EXISTS sp_return_computer;
DROP PROCEDURE IF EXISTS sp_set_non_asset_quantity;
DROP PROCEDURE IF EXISTS sp_set_monitor_usage;

DELIMITER $$

CREATE PROCEDURE sp_assign_computer (
  IN p_computer_id BIGINT UNSIGNED,
  IN p_employee_id BIGINT UNSIGNED,
  IN p_assigned_at DATETIME,
  IN p_notes VARCHAR(500)
)
SQL SECURITY INVOKER
MODIFIES SQL DATA
BEGIN
  DECLARE v_computer_count INT DEFAULT 0;
  DECLARE v_employee_count INT DEFAULT 0;
  DECLARE v_active_assignment_count INT DEFAULT 0;
  DECLARE v_effective_assigned_at DATETIME;

  SET v_effective_assigned_at = COALESCE(p_assigned_at, CURRENT_TIMESTAMP);

  SELECT COUNT(*)
    INTO v_computer_count
    FROM computer_asset
   WHERE computer_id = p_computer_id
     AND it_asset_status NOT IN ('retired', 'lost');

  IF v_computer_count = 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Computer does not exist or cannot be assigned';
  END IF;

  SELECT COUNT(*)
    INTO v_employee_count
    FROM employee
   WHERE employee_id = p_employee_id
     AND employment_status = 'active';

  IF v_employee_count = 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Employee does not exist or is not active';
  END IF;

  SELECT COUNT(*)
    INTO v_active_assignment_count
    FROM computer_assignment
   WHERE computer_id = p_computer_id
     AND returned_at IS NULL
     AND assignment_status = 'active';

  IF v_active_assignment_count > 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Computer already has an active assignment';
  END IF;

  INSERT INTO computer_assignment (
    computer_id,
    employee_id,
    assigned_at,
    returned_at,
    assignment_status,
    notes
  )
  VALUES (
    p_computer_id,
    p_employee_id,
    v_effective_assigned_at,
    NULL,
    'active',
    p_notes
  );

  UPDATE computer_asset
     SET it_asset_status = 'in_use'
   WHERE computer_id = p_computer_id;
END$$

CREATE PROCEDURE sp_return_computer (
  IN p_computer_id BIGINT UNSIGNED,
  IN p_returned_at DATETIME
)
SQL SECURITY INVOKER
MODIFIES SQL DATA
BEGIN
  DECLARE v_assignment_id BIGINT UNSIGNED DEFAULT NULL;
  DECLARE v_assigned_at DATETIME DEFAULT NULL;
  DECLARE v_effective_returned_at DATETIME;

  SET v_effective_returned_at = COALESCE(p_returned_at, CURRENT_TIMESTAMP);

  SELECT assignment_id, assigned_at
    INTO v_assignment_id, v_assigned_at
    FROM computer_assignment
   WHERE computer_id = p_computer_id
     AND returned_at IS NULL
     AND assignment_status = 'active'
   LIMIT 1;

  IF v_assignment_id IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Computer has no active assignment';
  END IF;

  IF v_effective_returned_at < v_assigned_at THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Return time cannot be earlier than assignment time';
  END IF;

  UPDATE computer_assignment
     SET returned_at = v_effective_returned_at,
         assignment_status = 'returned'
   WHERE assignment_id = v_assignment_id;

  UPDATE computer_asset
     SET it_asset_status = 'idle'
   WHERE computer_id = p_computer_id;
END$$

CREATE PROCEDURE sp_set_non_asset_quantity (
  IN p_employee_id BIGINT UNSIGNED,
  IN p_non_asset_type_id BIGINT UNSIGNED,
  IN p_quantity INT UNSIGNED,
  IN p_last_counted_date DATE,
  IN p_notes VARCHAR(500)
)
SQL SECURITY INVOKER
MODIFIES SQL DATA
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM employee
     WHERE employee_id = p_employee_id
       AND employment_status = 'active'
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Employee does not exist or is not active';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM non_asset_type
     WHERE non_asset_type_id = p_non_asset_type_id
       AND is_active = 1
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Non-asset type does not exist or is inactive';
  END IF;

  IF COALESCE(p_quantity, 0) = 0 THEN
    DELETE FROM employee_non_asset_usage
     WHERE employee_id = p_employee_id
       AND non_asset_type_id = p_non_asset_type_id;
  ELSE
    INSERT INTO employee_non_asset_usage (
      employee_id,
      non_asset_type_id,
      quantity,
      last_counted_date,
      notes
    )
    VALUES (
      p_employee_id,
      p_non_asset_type_id,
      p_quantity,
      p_last_counted_date,
      p_notes
    )
    ON DUPLICATE KEY UPDATE
      quantity = VALUES(quantity),
      last_counted_date = VALUES(last_counted_date),
      notes = VALUES(notes),
      updated_at = CURRENT_TIMESTAMP;
  END IF;
END$$

CREATE PROCEDURE sp_set_monitor_usage (
  IN p_employee_id BIGINT UNSIGNED,
  IN p_display_name VARCHAR(128),
  IN p_model VARCHAR(128),
  IN p_quantity INT UNSIGNED,
  IN p_last_counted_date DATE,
  IN p_notes VARCHAR(500)
)
SQL SECURITY INVOKER
MODIFIES SQL DATA
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM employee
     WHERE employee_id = p_employee_id
       AND employment_status = 'active'
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Employee does not exist or is not active';
  END IF;

  IF COALESCE(TRIM(p_display_name), '') = '' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Display name is required';
  END IF;

  IF COALESCE(p_quantity, 0) = 0 THEN
    DELETE FROM employee_monitor_usage
     WHERE employee_id = p_employee_id
       AND display_name = p_display_name
       AND model = COALESCE(p_model, '');
  ELSE
    INSERT INTO employee_monitor_usage (
      employee_id,
      display_name,
      model,
      quantity,
      last_counted_date,
      notes
    )
    VALUES (
      p_employee_id,
      p_display_name,
      COALESCE(p_model, ''),
      p_quantity,
      p_last_counted_date,
      p_notes
    )
    ON DUPLICATE KEY UPDATE
      quantity = VALUES(quantity),
      last_counted_date = VALUES(last_counted_date),
      notes = VALUES(notes),
      updated_at = CURRENT_TIMESTAMP;
  END IF;
END$$

DELIMITER ;
