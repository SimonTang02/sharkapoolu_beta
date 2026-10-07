# 完全手动维护资料与投递数据库

不使用扫描或自动填表，也可以手工编辑资料JSON和CSV，再导入SQLite。
图形工具可打开本机库查看，但SSH共享库只在主机存在；不要拿客户端另建的
SQLite文件作为主库。正式数据库文件不是Excel表格，不能直接用Excel覆盖。
完整带列注释的SQL参考为 `examples/database_template.sql`。

## 个人信息不需要写SQL

联系信息/教育/项目/技能/许可答案手工编辑私有
`profiles/application_profile.json`；技能证据和关键词另有JSON模板及schema。
[初始化指南](candidate-onboarding.md)解释信息如何分工。它们是答案来源，
`applications.answers_json`是某一次投递的记录，不能拿一岗法律答案通用化。
用 `jobbot-private check`检查类型；未知值遵守各文件schema。

## 使用两张CSV表

`jobbot-private init`仅创建缺失的 `database/manual/jobs.csv` 与
`database/manual/applications.csv`，已有文件不覆盖。直接打开、填写并另存为
**UTF-8 CSV**（Excel可选CSV UTF-8）；不要改首行列名或顺序。
逗号和换行由CSV双引号包围，不是修改列结构。空白表示未知/未提供；
job的role_kind未知须明确填 `unknown`。日期避免Excel自动变成数字或本地格式。

### jobs.csv：岗位

| 列 | 必填 | 填写说明 |
| --- | --- | --- |
| company | 是 | 正式公司名 |
| title | 是 | 官网职位标题，不是自己概括的方向 |
| url | 是 | 稳定HTTPS岗位官网URL；按URL去重；职位编号写external_id |
| location | 否 | 官网工作地点；不是本人地址；未知留空 |
| platform | 否 | ATS标识，如workday/greenhouse；空白按manual登记 |
| role_kind | 是 | internship、full_time、unknown三选一 |
| description | 否 | 官网JD全文及资格条件，未获取留空并待核实 |
| external_id | 否 | 官网职位编号，保留字母和前导零 |
| recruitment_category | 否 | 官方招聘项目/配额类别，不凭猜测填校招 |
| published_at | 否 | ISO日期或带时区时间；未知留空 |

岗位ID、公司ID、哈希、首次/末次收录时间、分数由程序生成。
相同URL已存在时保留整条旧岗位，不会用空白CSV覆盖已抓取JD或改原状态。
不存在的URL才新增；不同URL同一岗位须由Agent先核对，不自行合并目标。

### applications.csv：本人投递记录

| 列 | 必填 | 填写说明 |
| --- | --- | --- |
| job_url | 是 | 与jobs.url完全一致的正式URL，岗位必须已入库或随本次岗位表导入 |
| status | 是 | queued待准备 / draft草稿 / manual_required需本人处理 / submitted成功提交 |
| confirmed_success | 条件 | submitted必须为true，表示本人明确确认成功；其他状态留空或false |
| confirmation_number | 否 | 正式收件编号；没有编号留空，不编造 |
| submitted_at | 否 | 实际提交时间，带时区ISO如2026-10-06T18:30:00Z；未知留空 |
| confirmation_evidence | 条件 | submitted必须有真实回执路径/来源或本人明确成功确认的具体记录；不能填“已打开页面” |
| notes | 否 | 新申请的业务备注，不放密码/cookie/token |

首次导入可创建申请。已有唯一申请时，仅允许有明确证据的submitted升级；
其他状态保留旧记录。同岗位多条申请时中止，由Agent按application_id核对。
已提交记录绝不因再次导入被降级；不会改变批次顺序、替换目标或重置进度。
未知提交时间以登记时间写库，事件中标为recording_time，不能冒充官方回执时间。

## 先预览，再写主库

```bash
applybot import-manual --jobs <private-jobs.csv> --applications <private-applications.csv>
```

默认只校验CSV、计算拟用分数并写私有JSON预览，不打开或初始化数据库。
执行时才连接既有主库，检查重复/关联，并在一个事务中写入；任何一行关联
错误会回滚本次业务写入。CSV预览不是对主库当前状态的完整查询。

```bash
applybot import-manual --jobs <private-jobs.csv> --applications <private-applications.csv> --execute
```

含submitted记录时还需本人实际确认成功，并显式增加：

```bash
applybot import-manual --applications <private-applications.csv> --confirm-submissions --execute
```

可以用 `--config`指定现有私有运行配置；共享模式通过既有SSH连接操作主库。
本命令不会操作浏览器或提交到雇主。新增/保留/确认登记数和审计事件记录在
私有outputs内。个人事实、CSV和数据库均不得提交GitHub。

## 查库时三个编号不要混用

- jobs.id：岗位内部ID；external_id才是官网职位编号。
- applications.id：一次申请内部ID，供填写/审查/成功登记命令使用。
- application_campaign_jobs.rank：批次原序号，导入器不调整它。

申请成功以applications.status为准，岗位的jobs.status是发现/处理状态。
scan_runs.status为running/ok/error；campaign.status为planned等批次状态，
它们都不能填submitted来伪造投递数。只有真实回执或本人确认支持申请submitted。
