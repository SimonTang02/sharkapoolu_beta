# 给第一次使用的朋友：只改一份功能配置

首次资料初始化先看 [candidate-onboarding.md](candidate-onboarding.md)，
平台选择看 [platforms.md](platforms.md)。安装后，日常只编辑 `private_data/config/easy_settings.json`。设置了
`JOBBOT_PRIVATE_DIR` 时，文件位于该私有根目录的 `config/` 内。
公开示例是 `examples/easy_settings_template.json`，说明文字已经写进文件。
`true` 表示开启，`false` 表示关闭；保留引号、逗号和区域名称。
修改后执行 `jobbot-settings check`；检查通过后执行 `jobbot-settings plan`。
无需编辑自动生成的 `easy_runtime.generated.json`。

## 五个区域

| 区域 | 调整内容 | 实际效果 |
| --- | --- | --- |
| 01 使用模式 | 总开关、手动辅助 / 快速填写 / 完整填写 | 总开关关闭时所有执行任务被拒绝。模式控制自动准备的时间、重试和中断策略。最终提交固定由本人执行。 |
| 02 功能模块 | job_bot、application_bot 及各子模块 | 父模块和对应子开关都开启才可执行。扫描和报告属于 job_bot；填写、材料、投递包、登录检查属于 application_bot。 |
| 03 浏览器与采集 | HTTP、内置浏览器、CDP、并发、网络重试 | HTTP不开浏览器。内置为临时独立 Chromium，用于采集，退出即清理。CDP连接本人已有的专用Chrome，适合需要保留登录、截图和表单的任务。选择项确定实际使用哪种浏览器，所选开关也必须开启。 |
| 04 审查与额度 | 审查轮数、每岗秒数、适配器重试、截图 | 每轮同时核对资格、字段、附件。默认3轮，实际记录不足或文件哈希改变会拦截自动填写。时间与重试控制工作量，不是模型费用的精确上限。 |
| 05 地区范围 | 美国、香港、中国大陆、新加坡、欧洲、其他、未知地点 | 按职位地点过滤新扫描结果和日报，也拦截不符地区的任务包和填写。不会把原库旧职位停用，不代表当地已有完整职位源、评分策略或工作许可。无法可靠识别的地点按“保留未知地点”处理。 |

`生成简历材料` 开关允许生成交给Agent的材料任务包；不会直接启动付费模型
或未经审阅的批量生成。`生成手动投递包` 使用已完成的Manifest和已审阅PDF；
不指定输入时只生成组装任务。`辅助手动填写` 会提供数据库、个人答案、技能
证据、目标编号与可选专用标签页截图的路径，图片理解由当前Agent完成。

## 三种模式怎么选

- **手动辅助（默认）**：Agent读取任务包，逐项解释或给出答案，本人在浏览器填写、上传、提交。生成任务包不会自行填写网页。
- **快速填写**：开启“自动填写”，使用专用CDP浏览器和支持的适配器。每岗默认45秒、0次重试；已注册投递页出现验证码、MFA、登录边界或超时就终止该岗适配器，继续下一岗。
- **完整填写**：默认每岗240秒、1次重试；遇到需要本人处理的步骤或适配器失败停止整批。提供更多准备时间，仍不绕过验证、不推断法律答案、不代点最终提交。

门户支持范围与原适配器一致；成功返回表示准备脚本结束，不保证每个字段都
已填写。最终Review页仍须本人检查。页面未被登记为对应投递标签页时，应由
Agent先登记，再运行自动填写；无法连接监控浏览器时不会执行适配器。
脚本中断会保留外部Chrome和已填写的标签页，不会登记“submitted”。
自动填写和截图只使用CDP，避免临时内置浏览器退出时丢失表单。

## 最少需要记住的命令

先在项目目录激活安装时创建的环境：`source .venv/bin/activate`。
未安装命令入口时可将 `jobbot-settings` 换为 `python3 -m job_bot.easy_cli`。

```bash
jobbot-settings init                    # 仅创建缺失配置，保留现有文件
jobbot-settings check                   # 检查类型、开关、范围与运行配置
jobbot-settings plan                    # 只读预览生效开关和启用来源数量
jobbot-settings run --task scan         # 预览扫描命令
jobbot-settings run --task scan --execute
jobbot-settings run --task report --execute
```

单岗辅助：下面的 `123` 是示例投递记录ID，须由Agent从主库查到真实ID。
它不是手动投递包的序号，不应把两者混用。

```bash
jobbot-settings run --task assist --application-id 123 --execute
jobbot-settings run --task materials --application-id 123 --execute
```

将输出的 `AGENT_TASK.md` 路径交给新对话。它会引导Agent读取公开操作契约、
当前配置、真实目标、私人答案和审查记录，不需要旧聊天历史。
未知事实仍须本人确认；任务包不会把旧审查记录覆盖为通过。

自动准备须先在第一区选择快速或完整模式，在第二区开启“自动填写”，
在第三区开启CDP并把“浏览器选择”设为“CDP”。Agent先完成实际审查：

```bash
jobbot-settings run --task fill --application-id 123       # 预览
jobbot-settings run --task fill --application-id 123 --execute
```

可重复 `--application-id` 指定多个目标。运行记录保存在私有outputs中。
填写被阻止、超时或部分完成会返回非零状态，不能理解为已投成功。
审查记录还绑定当前岗位URL/JD、个人答案与技能证据文件、逐岗档案和其实际
使用的简历/求职信。只审查另一份PDF不能通过附件检查；这些内容变化后须重新审阅。

生成HTML投递包时使用已经审阅的私有Manifest和一个尚不存在的输出目录：

```bash
jobbot-settings run --task manual_kit --manifest <private-manifest.json> \
  --output <new-private-output-folder> --execute
```

## Agent第一次安装仍要协助哪些事

这份文件负责日常功能选择。首次使用还需要Agent或熟悉系统的人完成：

1. 安装Python/虚拟环境、可选Playwright/浏览器依赖；材料渲染另需TeX。
2. 按本人确认的事实填写个人档案、证据、毕业日期、许可与目标偏好。地区开关不能生成这些事实。
3. 选择适合朋友的真实职位源、评分和招聘年份。当前策略主要覆盖硬件方向及中国/香港校招、美国新毕业与暑期实习；其他方向需适配。
4. 建立专用Chrome和本机CDP地址。凭证留在 `passport.env` 或环境变量；入口只接受本机地址，远端需SSH端口映射。用户亲自登录、处理验证码和MFA。
5. 核实主库位置与SSH主客机角色，检查材料绑定、门户答案和首个真实表单。不得拿演示人物的答案直接投递。
6. 组装已审阅的Manifest、PDF及逐岗审查记录；核对真实毕业日期与材料模块，详见 `candidate-onboarding.md`。

`easy_runtime.generated.json` 从现有私有 `job_bot.local.json`（存在时）或公开
默认配置派生。可以用 `--base-config` 指定另一个既有配置。个人资料和
密码另存于各自私有文件，日常无需修改它们。邮件保持dry-run。

这套开关仅作用于 `jobbot-settings` 入口及使用其生成运行配置的下游命令；
旧命令若仍传入其他配置，不会自动受它控制。没有后台监听器、定时调度器或
自动投递守护进程。不要一边运行一边修改配置：结束当前任务再重新预览。
已有手动投递包、Windows浏览器进度和主库状态不会因为创建配置被重置。
