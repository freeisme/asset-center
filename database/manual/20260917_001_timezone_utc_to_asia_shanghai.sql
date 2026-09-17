-- 时区迁移：把历史时间从 UTC 平移到 UTC+8（Asia/Shanghai）
--
-- 背景
--   系统长期运行在 UTC：宿主机、应用容器、MySQL 都是 UTC。库中所有时间列都是
--   DATETIME（没有一个 TIMESTAMP），MySQL 不会做时区换算，前端也只按字符串裁剪显示，
--   因此用户看到的时间比北京时间少 8 小时。
--   本脚本与容器 TZ=Asia/Shanghai 的切换配套使用，把历史值整体后移 8 小时。
--
-- 执行前提
--   1. 已完成全库备份并确认可恢复。
--   2. 应用容器已停止，切换期间没有新的写入。
--   3. 与应用容器时区切换同时执行；只跑脚本不改时区，会让历史数据超前 8 小时。
--   4. 必须按「表」一次性平移同一行的所有时间列：像 ck_assignment_dates
--      （returned_at >= assigned_at）这类行内 CHECK 约束，逐列平移会在中途被违反。
--
-- 处理规则
--   * 默认：所有 DATETIME 列整体 +8 小时（这些值由服务器 UTC 时钟写入）。
--   * 例外 1：inventory_movement_log.occurred_at 与 left_employee_archive.archived_at
--     存在浏览器按本地时间写入的历史值，只平移与同行 created_at 一致的记录，
--     已经是本地时间的记录保持不变。
--   * 例外 2：itil_change.planned_start_at / planned_end_at 由用户手填，语义本来就是
--     本地时间，不做平移。
--
-- 幂等与回滚
--   * 重复执行会在标记表主键冲突处报错并回滚，不会二次平移。
--   * 回滚方式一：删除 data_migration_marker 对应行，把脚本里的 INTERVAL 8 HOUR
--     改成 INTERVAL -8 HOUR 重跑（例外列的判定条件是对称的，仍然成立）。
--   * 回滚方式二：直接恢复执行前的备份。
--
-- 用法（在数据库容器内执行，mysql 客户端负责解释 DELIMITER）：
--   mysql -uroot -p -D <数据库名> < 20260917_001_timezone_utc_to_asia_shanghai.sql

SET SESSION group_concat_max_len = 1000000;

CREATE TABLE IF NOT EXISTS data_migration_marker (
  marker_key VARCHAR(64) NOT NULL,
  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note VARCHAR(255) NOT NULL DEFAULT '',
  PRIMARY KEY (marker_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP PROCEDURE IF EXISTS shift_utc_datetimes;

DELIMITER //
CREATE PROCEDURE shift_utc_datetimes()
BEGIN
  DECLARE done INT DEFAULT 0;
  DECLARE target_table VARCHAR(64);
  DECLARE table_cursor CURSOR FOR
    SELECT DISTINCT column_row.table_name
    FROM information_schema.columns AS column_row
    WHERE column_row.table_schema = DATABASE()
      AND column_row.data_type = 'datetime'
      AND NOT (column_row.table_name = 'inventory_movement_log'
               AND column_row.column_name = 'occurred_at')
      AND NOT (column_row.table_name = 'left_employee_archive'
               AND column_row.column_name = 'archived_at')
      AND NOT (column_row.table_name = 'itil_change'
               AND column_row.column_name IN ('planned_start_at', 'planned_end_at'))
      AND column_row.table_name <> 'data_migration_marker'
    ORDER BY column_row.table_name;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

  OPEN table_cursor;
  shift_loop: LOOP
    FETCH table_cursor INTO target_table;
    IF done = 1 THEN
      LEAVE shift_loop;
    END IF;

    -- 同一张表的所有时间列在一条 UPDATE 里一起平移，保证行内约束始终成立。
    SET @set_clause = NULL;
    SELECT GROUP_CONCAT(
             CONCAT('`', column_row.column_name, '` = DATE_ADD(`',
                    column_row.column_name, '`, INTERVAL 8 HOUR)')
             SEPARATOR ', '
           )
    INTO @set_clause
    FROM information_schema.columns AS column_row
    WHERE column_row.table_schema = DATABASE()
      AND column_row.data_type = 'datetime'
      AND column_row.table_name = target_table
      AND NOT (column_row.table_name = 'inventory_movement_log'
               AND column_row.column_name = 'occurred_at')
      AND NOT (column_row.table_name = 'left_employee_archive'
               AND column_row.column_name = 'archived_at')
      AND NOT (column_row.table_name = 'itil_change'
               AND column_row.column_name IN ('planned_start_at', 'planned_end_at'));

    SET @shift_statement = CONCAT(
      'UPDATE `', target_table, '` SET ', @set_clause
    );
    PREPARE shift_prepared FROM @shift_statement;
    EXECUTE shift_prepared;
    DEALLOCATE PREPARE shift_prepared;
  END LOOP;
  CLOSE table_cursor;
END //
DELIMITER ;

START TRANSACTION;

-- 幂等闸门：重复执行时这里因主键冲突报错，后续语句不会执行，事务回滚。
INSERT INTO data_migration_marker (marker_key, note)
VALUES ('20260917_timezone_utc_to_utc8', 'shift DATETIME values from UTC wall clock to UTC+8');

-- 浏览器按本地时间写入的两列：只平移与同行 created_at 一致的记录。
-- 注意：这两张表的 updated_at 是 ON UPDATE CURRENT_TIMESTAMP，必须显式赋值成自身，
-- 否则这条 UPDATE 改动行时会把它刷成当前时间，随后整表平移再多加 8 小时。
UPDATE `inventory_movement_log`
SET `occurred_at` = DATE_ADD(`occurred_at`, INTERVAL 8 HOUR),
    `updated_at` = `updated_at`
WHERE `occurred_at` IS NOT NULL
  AND ABS(TIMESTAMPDIFF(MINUTE, `created_at`, `occurred_at`)) <= 5;

UPDATE `left_employee_archive`
SET `archived_at` = DATE_ADD(`archived_at`, INTERVAL 8 HOUR),
    `updated_at` = `updated_at`
WHERE `archived_at` IS NOT NULL
  AND ABS(TIMESTAMPDIFF(MINUTE, `created_at`, `archived_at`)) <= 5;

-- 其余时间列整体平移。
CALL shift_utc_datetimes();

COMMIT;

DROP PROCEDURE IF EXISTS shift_utc_datetimes;
