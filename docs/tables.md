# 数据

MySQL 保存讲义页、学习计划、题目、作答、分数和出处页。Milvus 保存带页码的讲义片段，只用于检索。两者由 Docker Compose 在本机启动。表结构以本文为准。

时间使用 MySQL `DATETIME`。比例使用 `DECIMAL(5,4)`，例如 `0.8000` 表示 80%。

```text
documents 1 ──< pages
documents 1 ──< study_plans 1 ──< plan_chapters 1 ──< concept_status
plan_chapters 1 ──< question_sets 1 ──< questions 1 ── responses
plan_chapters 1 ── chapter_reports
plan_chapters 1 ── sessions >── question_sets
documents 1 ──< qa_records

Milvus lecture_segments：document_id + page_number + chapter + text
```

练习开始前，对应 `documents.ingest_status` 必须是 `complete`。

## documents

一份上传的讲义 PDF。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | 文档编号。引用时使用这个值 |
| filename | VARCHAR(255) | 非空 | 原始文件名 |
| ingest_status | VARCHAR(16) | 非空，默认 `pending` | `pending` 入库中，`complete` 页已写入，`failed` 解析失败 |
| created_at | DATETIME | 非空 | 上传时间 |

## pages

讲义中的一页。页码是 PDF 原始页码。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| document_id | INT | 非空，引用 `documents.id` | |
| page_number | INT | 非空 | PDF 原始页码 |
| chapter | VARCHAR(255) | 非空 | 这一页所属章节 |
| body | TEXT | 可空 | 抽出的正文。不可用页留空 |
| usable | TINYINT(1) | 非空 | `1` 可引用，`0` 抽不出文字 |

同一文档的 `page_number` 不可重复。

## study_plans

一次学习计划。上传时只保存学生的一段原话，不在这里拆开目标或日期。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| document_id | INT | 非空，引用 `documents.id` | |
| student_brief | TEXT | 非空 | 学生写下的学习目标、日期和其他要求，原样保存 |
| status | VARCHAR(16) | 非空，默认 `draft` | `draft` 原话已保存，尚未生成章节任务；`active` 任务已生成；`adjusted` 已按练习结果调整过 |
| created_at | DATETIME | 非空 | |

上传这一步只创建 `documents`、`pages`、`study_plans`。`plan_chapters` 及后面的表在生成学习任务和练习时再建。生成任务时读取 `student_brief` 和 `pages.body`，由 agent API 分析原话。

## plan_chapters

计划中的一章，按 `position` 从 1 开始排列。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| plan_id | INT | 非空，引用 `study_plans.id` | |
| position | INT | 非空 | 阅读顺序。同一计划内不可重复 |
| chapter | VARCHAR(255) | 非空 | 章节名 |
| concepts | TEXT | 非空 | 本章概念，JSON 字符串数组 |
| page_start | INT | 非空 | 阅读起始页 |
| page_end | INT | 非空 | 阅读结束页 |
| estimated_minutes | INT | 非空 | 预计用时 |
| status | VARCHAR(16) | 非空，默认 `pending` | `pending` 未开始，`in_progress` 练习中，`passed` 达到通过线，`ended` 两轮后结束 |

## concept_status

某一章里一个概念的掌握情况。某题答错时，该题的概念改为 `weak`。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| plan_chapter_id | INT | 非空，引用 `plan_chapters.id` | |
| concept | VARCHAR(255) | 非空 | 与题目上的概念同名 |
| status | VARCHAR(16) | 非空，默认 `unseen` | `unseen` 尚未考到，`weak` 答错过，`ok` 答对 |

同一章的概念名不可重复。

## question_sets

某一章的一套题。`round_number` 只能是 1 或 2。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| plan_chapter_id | INT | 非空，引用 `plan_chapters.id` | |
| round_number | TINYINT | 非空 | `1` 或 `2`。同一章每个轮次只有一套 |
| status | VARCHAR(16) | 非空，默认 `in_progress` | `in_progress` 可继续作答，`submitted` 已交卷 |

## questions

一道题。出处用文档编号和 PDF 原始页码。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| set_id | INT | 非空，引用 `question_sets.id` | |
| concept | VARCHAR(255) | 非空 | 考查的概念 |
| question_type | VARCHAR(16) | 非空 | `mc` 选择题，`short` 简答题 |
| prompt | TEXT | 非空 | 题干 |
| options_json | TEXT | 可空 | 选择题选项，JSON 数组。简答题留空 |
| standard_answer | TEXT | 非空 | 选择题为标准选项。简答题为参考答案 |
| rubric_json | TEXT | 可空 | 简答题得分点，JSON 字符串数组，等权。选择题留空 |
| source_document_id | INT | 非空，引用 `documents.id` | |
| source_page | INT | 非空 | PDF 原始页码 |

## responses

一次有效计分。同一道题只有一行，用来防止重复计分。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| question_id | INT | 非空，唯一，引用 `questions.id` | |
| answer | TEXT | 非空 | 学生答案 |
| is_correct | TINYINT(1) | 非空 | 选择题与标准选项一致为对。简答题得分点命中率达到 80% 为对 |
| match_ratio | DECIMAL(5,4) | 非空 | 选择题为 `1.0000` 或 `0.0000`。简答题为得分点命中率 |
| explanation | TEXT | 可空 | 只有答错时填写 |
| explanation_page | INT | 可空 | 解释所依据的页码。只有答错时填写 |
| submitted_at | DATETIME | 非空 | |

## chapter_reports

某一章的报告。通过时写入第一轮正确率。第二轮结束后两轮正确率都要有。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| plan_chapter_id | INT | 非空，唯一，引用 `plan_chapters.id` | 一章一份报告 |
| round1_correct_ratio | DECIMAL(5,4) | 非空 | 第一轮正确率 |
| round2_correct_ratio | DECIMAL(5,4) | 可空 | 未进入第二轮时留空 |
| status | VARCHAR(16) | 非空 | `passed` 达到通过线，`ended` 两轮后结束 |
| created_at | DATETIME | 非空 | |

## sessions

学生当前停在哪一套题上。再次进入时读取 `active_set_id`，继续同一套题。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| plan_chapter_id | INT | 非空，唯一，引用 `plan_chapters.id` | 一章一条会话 |
| active_set_id | INT | 非空，引用 `question_sets.id` | 当前题组 |
| status | VARCHAR(16) | 非空，默认 `active` | `active` 可恢复，`closed` 本章已出报告 |
| updated_at | DATETIME | 非空 | |

## qa_records

一次独立提问。讲义中没有依据时 `refused` 为 1，`cited_pages` 留空。独立提问不修改 `responses`。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | INT | 主键，自增 | |
| document_id | INT | 非空，引用 `documents.id` | |
| question | TEXT | 非空 | |
| answer | TEXT | 非空 | 拒绝时说明讲义中没有依据 |
| cited_pages | VARCHAR(255) | 可空 | 引用的 PDF 页码，逗号分隔 |
| refused | TINYINT(1) | 非空 | `1` 表示讲义不足以回答 |
| created_at | DATETIME | 非空 | |

## Milvus：lecture_segments

集合名 `lecture_segments`。一条记录是一个讲义片段。

| 字段 | 说明 |
| --- | --- |
| id | 片段主键 |
| vector | 片段向量 |
| document_id | 对应 `documents.id` |
| page_number | PDF 原始页码 |
| chapter | 章节名 |
| text | 片段正文，与同一 `document_id`、`page_number` 的 `pages.body` 相同 |
| chunk_index | 从 0 开始。一页正文过长时拆成多条，按此顺序拼回原文 |

检索结果必须能回到 `document_id` 和 `page_number`。不可用页不写入本集合。同一页的全部分段拼起来等于 MySQL 里该页的 `body`。

## 建库时先验证的例子

插入并读回下面三条，即算 MySQL 和 Milvus 的表结构可用。

文档：

| id | filename | ingest_status |
| --- | --- | --- |
| 1 | lecture2.pdf | complete |

页：

| id | document_id | page_number | chapter | usable |
| --- | --- | --- | --- | --- |
| 1 | 1 | 1 | Data Structures | 1 |

片段：

| document_id | page_number | chapter | text |
| --- | --- | --- | --- |
| 1 | 1 | Data Structures | Arrays store items in contiguous memory. |

读回时，MySQL 能按文档编号拿到第 1 页正文，Milvus 用这句话能查回文档 `1`、页码 `1`。
