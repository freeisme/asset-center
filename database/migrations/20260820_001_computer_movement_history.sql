-- Store the actor responsible for each device assignment and return.
ALTER TABLE computer_assignment_history
  ADD COLUMN assigned_by BIGINT UNSIGNED NULL AFTER notes,
  ADD COLUMN returned_by BIGINT UNSIGNED NULL AFTER assigned_by,
  ADD KEY idx_computer_assignment_history_assigned_by (assigned_by),
  ADD KEY idx_computer_assignment_history_returned_by (returned_by),
  ADD CONSTRAINT fk_computer_assignment_history_assigned_by
    FOREIGN KEY (assigned_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT fk_computer_assignment_history_returned_by
    FOREIGN KEY (returned_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE;
