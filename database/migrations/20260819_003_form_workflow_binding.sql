-- Bind a service form to its executable approval workflow.
ALTER TABLE service_form
  ADD COLUMN workflow_id BIGINT UNSIGNED NULL AFTER workflow_json,
  ADD KEY idx_service_form_workflow (workflow_id),
  ADD CONSTRAINT fk_service_form_workflow
    FOREIGN KEY (workflow_id) REFERENCES service_workflow (workflow_id)
    ON DELETE SET NULL ON UPDATE CASCADE;
