-- Prevent duplicate decisions for the same approval step under concurrent requests.
ALTER TABLE service_approval_decision
  ADD UNIQUE KEY uq_service_approval_decision_step (approval_id, step_order);
