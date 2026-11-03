# CitePath 前后端对接说明

本文说明当前前端如何连接后端、哪些功能已经实现，以及后续各模块应在哪里接入。

核对日期：2026 年 11 月 3 日。

“已经接入”表示前端已有请求代码，后端已有对应接口，不代表已经在所有本地环境中完成数据库、向量库和模型的端到端验收。

## 一、整体架构

当前系统的主要调用关系为：

```text
浏览器中的 React 前端
        │
        │ 请求 /api/...
        ▼
Vite 开发服务器
        │
        │ 将 /api 请求代理到 127.0.0.1:8000
        ▼
FastAPI 后端
        ├── MySQL：用户、会话、课程、文档页、问答记录
        ├── Milvus：讲义内容向量检索
        ├── PDF 解析：提取页面内容和页码
        └── 模型调用：通过 LangChain 连接 HKU 模型接口
```

前端不直接连接 MySQL、Milvus 或模型服务，也不在浏览器中保存模型密钥。

### 本地开发地址

| 服务 | 地址 |
| --- | --- |
| 前端 | `http://127.0.0.1:5173` |
| 后端 | `http://127.0.0.1:8000` |
| 后端接口文档 | `http://127.0.0.1:8000/docs` |
| MySQL | `127.0.0.1:3306` |
| Milvus | `127.0.0.1:19530` |

MySQL 和 Milvus 等基础服务由项目根目录的 Docker Compose 配置启动。

## 二、目前已经实现的功能

### 1. 已有真实接口调用的功能

| 功能 | 前端实现 | 后端实现 |
| --- | --- | --- |
| 注册 | 输入校验、确认密码、提交及错误展示 | 创建用户并建立会话 |
| 登录 | 输入校验、提交、成功跳转 | 校验用户并建立会话 |
| 登录状态检查 | 应用启动时获取当前用户 | 从 Cookie 读取并验证会话 |
| 退出登录 | 调用退出接口并清除当前页面状态 | 关闭会话并删除 Cookie |
| 课程列表 | 课程卡片、截止时间排序、侧栏课程列表 | 查询当前用户的课程 |
| 创建课程 | 填写课程配置、保存、继续上传资料 | 保存课程及学生说明 |
| 课程详情 | 展示课程设置和资料列表 | 返回课程及文档信息 |
| PDF 上传 | 多文件选择、逐个上传、等待与错误提示 | 解析 PDF、保存页面并写入向量库 |
| 删除资料 | 删除确认、请求及列表刷新 | 删除资料记录并尝试清理向量 |
| 独立问答 | 提问、展示回答、拒答和引用 | 检索该课程资料、调用模型并保存问答 |

### 2. 已有界面，但真实业务尚未接入的功能

| 功能 | 当前表现 |
| --- | --- |
| 修改真实课程的名称、期限等设置 | 可以读取并展示，保存修改被禁用 |
| 自动生成学习计划 | 真实课程显示等待规划服务接入 |
| 自动估算总学习时间 | 真实课程暂不提供生成结果 |
| 自动重新规划 | 真实课程尚未接入 |
| 学习日历中的真实任务 | 等待真实学习计划数据 |
| 真实章节练习 | 等待 B 的原定模块接口 |
| 真实判分和章节报告 | 等待 B 的原定模块接口 |
| 跨设备恢复真实练习 | 等待服务端保存和恢复接口 |
| 查看或下载原 PDF | 当前没有对应接口 |
| 读取历史问答 | 后端保存记录，但没有历史查询接口 |

后端目前存在 `study_plans` 表，创建课程时也会插入一条 `draft` 记录。

这条记录不代表已经生成了章节、任务、预计时间或日历安排。当前后端仍然没有提供完整学习计划的生成和读取接口。

### 3. 可以完整操作的界面演示

左侧的“界面演示”入口在页面中显示为 `Interface demo`。

它包含：

- 样例课程规划。
- 学习任务和时间估算展示。
- 月历及右侧当日概览。
- 阅读、练习、复习任务。
- 固定选择题和简答题。
- 第一轮结果、复习及第二轮。
- 章节报告。
- 本地保存与恢复。
- 修改样例设置后的重新排期。

这些数据是固定演示，不调用模型，也不解析用户上传的 PDF。

演示数据不会写入真实课程数据库。

## 三、前端请求如何组织

### 1. 统一请求入口

文件：

```text
src/shared/request.ts
```

所有业务接口通过：

```ts
request<T>(path, options)
```

发起。

该文件负责：

- 调用浏览器 `fetch`。
- 自动携带 Cookie。
- 解析 JSON 响应。
- 将后端错误转换为英文提示。
- 区分网络错误和接口错误。
- 业务接口返回 401 时通知应用退出当前登录状态。

页面不应各自重复编写不同的 Cookie 和错误处理逻辑。

### 2. 开发代理

文件：

```text
vite.config.ts
```

当前配置将：

```text
/api
```

代理到：

```text
http://127.0.0.1:8000
```

因此，前端请求应写成：

```ts
request('/api/courses')
```

无需在每个文件中写完整的后端地址。

该代理属于 Vite 开发服务器。部署生产环境时，需要由实际服务器配置 `/api` 转发，不能认为生产构建会自动携带开发代理。

### 3. 登录方式

后端使用：

```text
citepath_session
```

作为会话 Cookie 名称。

登录或注册成功后，后端设置 HttpOnly Cookie。浏览器负责保存和发送，前端不读取 Cookie 中的令牌。

请求中保留：

```ts
credentials: 'include'
```

当前代码不使用 JWT，也不把登录令牌存入 `localStorage`。

## 四、现有真实接口清单

| 方法 | 接口 | 功能 | 前端调用文件 |
| --- | --- | --- | --- |
| GET | `/api/me` | 获取当前用户 | `src/shared/session.ts` |
| POST | `/api/register` | 注册 | `src/unLogin/register/api.ts` |
| POST | `/api/login` | 登录 | `src/unLogin/login/api.ts` |
| POST | `/api/logout` | 退出登录 | `src/shared/session.ts` |
| GET | `/api/courses` | 获取课程列表 | `src/pages/courses/api.ts` |
| POST | `/api/courses` | 创建课程 | `src/pages/courseEditor/api.ts` |
| GET | `/api/courses/{course_id}` | 获取课程详情 | `src/pages/course/api.ts` |
| POST | `/api/courses/{course_id}/documents` | 上传 PDF | `src/pages/course/api.ts` |
| DELETE | `/api/courses/{course_id}/documents/{document_id}` | 删除资料 | `src/pages/course/api.ts` |
| POST | `/api/courses/{course_id}/questions` | 独立问答 | `src/pages/course/api.ts` |

后端还提供两个辅助接口：

| 方法 | 接口 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 检查 FastAPI 是否能够响应 |
| GET | `/api/agent/ping` | 检查模型调用链路 |

主页面没有自动调用模型测试接口。

健康接口返回成功，只说明 API 可以响应，不能证明数据库、向量检索和模型都正常。

## 五、各功能的具体对接方式

### 1. 注册和登录

请求体：

```json
{
  "username": "student",
  "password": "your-password"
}
```

成功响应示例：

```json
{
  "id": 1,
  "username": "student"
}
```

注册成功后，后端已经建立会话，不需要再调用一次登录接口。

前端成功后进入：

```text
/courses
```

应用启动时调用 `/api/me`：

- 返回用户：进入业务页面。
- 返回 401：进入登录页面。
- 网络或服务器异常：显示连接失败及重试入口。

首次打开页面时，未登录用户的 `/api/me` 返回 401 属于正常情况。

登录接口的 401 表示用户名或密码错误，应显示表单错误；业务接口的 401 则表示当前登录状态不可用。

### 2. 查询课程列表

响应结构：

```ts
{
  courses: {
    id: number
    name: string
    student_brief: string
    created_at: string
    document_count: number
  }[]
}
```

前端 `getCourses()` 会提取其中的 `courses` 数组。

当前 `document_count` 统计的是后端状态为 `complete` 的文档数量，不是任意状态的全部文档数量。

### 3. 创建课程

当前后端只接受：

```ts
{
  name: string
  student_brief: string
}
```

为了在不修改后端源代码的情况下保存额外设置，前端把以下对象转换为 JSON 字符串，放入 `student_brief`：

```json
{
  "schema": "citepath-course-v1",
  "deadline": "2026-12-01",
  "weeklyHours": 6,
  "earlyDays": 2,
  "note": "学生填写的原始目标、基础及重要日期。"
}
```

相关文件：

```text
src/pages/courseEditor/brief.ts
```

其中：

- `encodeBrief()`：编码课程设置。
- `decodeBrief()`：读取课程设置。
- 旧课程如果保存的是普通文本，就把它作为原始备注展示。

后端目前只是保存该字符串，不会自动解释其中字段或生成学习计划。

后续 C 的规划模块需要识别这个格式，并读取原始 `note`。

创建成功返回完整课程详情，前端会保留返回的课程编号，继续上传资料。

### 4. 上传 PDF

请求格式：

```text
multipart/form-data
```

文件字段名：

```text
file
```

前端使用：

```ts
const body = new FormData()
body.append('file', file)
```

不要手动添加 JSON 的 `Content-Type`，也不要手动拼接 multipart boundary。

后端当前每次接收一个文件。前端的多文件上传通过逐个调用接口完成。

成功响应结构：

```ts
{
  document_id: number
  filename: string
  page_count: number
  usable_page_count: number
  milvus_segments: number
}
```

处理流程：

```text
接收 PDF
→ 解析页面
→ 保存文档与页面记录
→ 将有效内容写入向量库
→ 返回处理结果
```

当前请求包含同步处理过程，没有上传解析任务的进度查询接口。因此，前端只显示正在处理，不生成虚假的完成百分比。

#### 上传失败后的处理

课程创建成功但上传失败时：

- 保留已经创建的课程编号。
- 不重新创建课程。
- 已收到成功响应的文件在重试时跳过。
- 对结果不确定的文件，先检查资料列表再手动重试。

当前后端没有上传幂等键。网络中断不一定代表服务端没有保存文件，因此不能承诺任何重试都绝不产生重复文档。

另外，当前 `backend/db/uploads.py` 先提交 MySQL，再执行向量写入；数据库状态与向量库并非一个原子事务。联调时不能仅凭资料显示 `Ready` 就断定检索一定正常，还需要验证检索链路。

### 5. 获取课程详情

响应结构：

```ts
{
  id: number
  name: string
  student_brief: string
  created_at: string
  documents: {
    id: number
    filename: string
    ingest_status: string
    page_count: number
    usable_page_count: number
  }[]
}
```

前端根据 `student_brief` 展示课程配置，根据 `documents` 展示资料列表。

### 6. 删除资料

请求成功后返回：

```json
{
  "ok": true
}
```

前端随后刷新：

- 当前课程详情。
- 课程列表中的文档数量。

当前后端先删除数据库记录，再尝试删除向量；向量删除异常会被捕获。因此，接口成功并不等于已经提供严格的跨存储原子删除保证。

真实学习计划尚未接入。后续如果计划引用被删除的资料，需要通过原定的规划流程处理失效引用和重新规划。

### 7. 独立问答

请求体：

```json
{
  "question": "请描述想询问的课程内容。"
}
```

响应结构：

```ts
{
  qa_id: number
  course_id: number
  course_name: string
  question: string
  answer: string
  cited_pages: {
    document_id: number
    filename: string
    page_number: number
  }[]
  refused: boolean
}
```

当前后端会：

1. 检查课程所属用户。
2. 获取该课程可用资料。
3. 检索相关页面。
4. 根据检索结果生成回答。
5. 校验引用范围。
6. 在证据不足时返回明确说明。
7. 保存问答记录。

前端展示：

- 用户问题。
- 回答或证据不足说明。
- 文档编号、文件名和 PDF 页码。

问答不会修改练习成绩。

后端虽然保存问答记录，但目前没有读取历史记录的接口。因此，刷新页面或离开问答标签后，当前前端不会自动恢复完整对话。

来源弹窗只展示引用信息，不提供原 PDF 在线查看功能。

## 六、后续模块在哪里接入

### 1. C 的学习规划模块

主要接入位置：

```text
src/shared/StudyProvider.tsx
src/pages/course/CoursePlan.tsx
src/pages/calendar/CalendarPage.tsx
src/pages/courses/CourseCard.tsx
src/pages/courseEditor/AnalysisDialog.tsx
```

建议接入顺序：

1. 确认真实计划的请求和响应格式。
2. 在页面目录增加相应请求函数。
3. 在 `StudyProvider` 中保存按课程区分的真实计划。
4. 替换 `CoursePlan` 中的未接入分支。
5. 让课程卡片和月历读取同一份计划。
6. 将分析弹窗连接到真实执行状态。
7. 仅在返回有效计划后跳转到日历。
8. 根据 B 返回的成绩和薄弱概念调整后续安排。

真实计划至少需要：

- 课程编号。
- 稳定的章节编号和任务编号。
- 章节与概念。
- 任务类型、日期、顺序。
- 预计分钟数和状态。
- 文档编号、文件名及页码。
- 计划版本和调整原因。
- 对应练习入口所需标识。

当前样例任务和部分链接固定使用 `demo`。接入多门真实课程时，需要补充所属课程身份，并统一替换数据来源和链接生成逻辑，不能只替换 URL。

### 2. B 的练习模块

主要接入位置：

```text
src/pages/practice/PracticePage.tsx
src/pages/practice/PracticeSessionPage.tsx
src/pages/practice/PracticeResult.tsx
src/pages/practice/ChapterReportPage.tsx
```

按照 B 原来约定的接口合同接入，不提前编造接口地址。

以下内容继续由 B 原有模块负责：

- 题组、标准答案、得分点和来源。
- 选择题与简答题判分。
- 等权计分和通过判断。
- 最多两轮的状态流转。
- 错题解释与薄弱概念。
- 保存、恢复和重复提交保护。
- 章节报告。

前端负责输入、展示和发起请求，正式成绩以服务端结果为准。

`demoQuestions()`、`submitDemo()`、`nextDemoRound()` 仅用于固定界面演示，不用于正式判分。

### 3. D 的现有范围

D 原有的入库、检索、问答、API 集成及异常处理分工保持不变。

本文记录当前能力和接口缺口，没有把课程更新、PDF 查看或新增统计服务额外分配给 D。

课程更新接口等缺口，需要团队根据已有分工协调确定。

## 七、英文输出约定

所有系统固定界面文案使用英文：

- 导航。
- 按钮。
- 状态。
- 表单校验。
- 错误提示。

当前 `backend/agent/qa.py` 的 `ANSWER_SYSTEM` 已要求有依据的回答使用英文。

后续规划和练习模块应统一原定的英文输出配置。

用户自己的课程名称、备注、文件名和讲义原文会保留，不由前端擅自翻译。

## 八、本地连接步骤

以下步骤适用于已经完成依赖安装和数据库初始化的本地环境。

### 1. 启动基础服务

在项目根目录运行：

```bash
docker compose up -d
```

Docker Desktop 必须处于运行状态。

首次使用环境时，还需要按照项目说明初始化 `backend/db/schema.sql`。只启动容器不会自动代表全部数据表已经建立。

### 2. 启动后端

打开一个终端：

```bash
cd /Users/junyingshi/VsCodeProjects/CitePath/backend
source .venv/bin/activate
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

模型配置由后端读取，相关名称包括：

```text
HKU_API_KEY
HKU_DEPLOYMENT
HKU_API_VERSION
```

具体填写方式以 `backend/.env.example` 和 `backend/agent/llm.py` 为准。

本次检查时发现 `backend/.venv` 存在，未发现 `backend/.env` 文件。如果密钥没有通过进程环境提供，应先按示例建立后端配置。

不要把模型密钥放进前端代码或前端环境变量。

### 3. 启动前端

再打开一个终端：

```bash
cd /Users/junyingshi/VsCodeProjects/CitePath/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### 4. 打开页面

```text
http://127.0.0.1:5173/
```

开发过程中建议保持同一主机名，不在 `localhost` 和 `127.0.0.1` 之间来回切换，以免混淆 Cookie 所属站点。

## 九、联调顺序和常见问题

### 推荐联调顺序

1. 确认后端健康接口能够响应。
2. 注册或登录。
3. 获取课程列表。
4. 创建课程并保存配置。
5. 上传一个可读取的 PDF。
6. 查看文档页数和可用页数。
7. 对课程资料提问并检查引用。
8. 测试删除资料。
9. 单独检查演示日历和练习流程。
10. 原定真实规划和练习模块接入后，再进行完整端到端验收。

### 前端能打开，但出现 ECONNREFUSED

如果提示无法连接 `127.0.0.1:8000`，说明代理目标没有正常响应。

检查后端是否启动、是否退出、端口是否一致。前端成功启动不代表后端已经启动。

### 课程已经创建，但上传失败

先进入课程资料页面检查，不要重复创建课程。

### PDF 显示有页数，但不能问答

检查可用页数、向量写入、检索服务和模型配置。存在页面记录不代表完整问答链路已经正常。

### 创建课程后没有自动生成计划

这是当前真实规划接口尚未接入的状态，不是前端已经完成了模型分析却没有展示。

### 没有找到前端自动化测试命令

当前项目没有 `test` 脚本，也没有前端测试目录。

之前独立交付目录中的测试，不代表已经存在于当前仓库。当前可以执行构建、lint 和人工联调检查。