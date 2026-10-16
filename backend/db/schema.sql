CREATE TABLE IF NOT EXISTS documents (
  id INT PRIMARY KEY AUTO_INCREMENT,
  filename VARCHAR(255) NOT NULL,
  ingest_status VARCHAR(16) NOT NULL DEFAULT 'pending',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pages (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT NOT NULL,
  page_number INT NOT NULL,
  chapter VARCHAR(255) NOT NULL,
  body TEXT NULL,
  usable TINYINT(1) NOT NULL,
  UNIQUE KEY uq_document_page (document_id, page_number),
  CONSTRAINT fk_pages_document FOREIGN KEY (document_id) REFERENCES documents (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS study_plans (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT NOT NULL,
  student_brief TEXT NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'draft',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_plans_document FOREIGN KEY (document_id) REFERENCES documents (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
