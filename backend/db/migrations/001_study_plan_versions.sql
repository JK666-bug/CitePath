CREATE TABLE IF NOT EXISTS study_plan_versions (
    plan_id INT NOT NULL,
    version_no INT UNSIGNED NOT NULL,
    plan_data JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (plan_id, version_no),
    CONSTRAINT fk_study_plan_versions_plan
        FOREIGN KEY (plan_id) REFERENCES study_plans (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;