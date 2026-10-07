# 开始投递前：原始简历、答案与评分初始化

首次使用依次完成：安装运行环境 → 导入原始简历 → Agent整理可编辑LaTeX和
事实台账 → 本人核实事实与偏好 → 建立私有答案/证据/评分 → 单岗审查。
机器与安装入口见 [platforms.md](platforms.md)，日常开关见
[beginner-settings.md](beginner-settings.md)，完全手工录入见
[manual-database.md](manual-database.md)。初始化不会启动投递或最终提交。

## 1. 输入原始简历

支持PDF、UTF-8 TXT、LaTeX。已有LaTeX优先保留；不要丢弃原始PDF。
PDF组件安装方式为 `python -m pip install -e '.[resume]'`，或bootstrap的
`--with-resume` / `-WithResume`。在激活的环境中：

```bash
cvbot import-resume --input <original-resume.pdf>             # 只检查输入
cvbot import-resume --input <original-resume.pdf> --execute
```

输出位于私有 `cv/intake/<新时间目录>/`：

| 文件 | 内容与用途 |
| --- | --- |
| original.pdf / .txt / .tex | 原始文件逐字节保存；不改原文件 |
| page_XX.txt | PDF逐页提取的文字，供定位与复核 |
| resume_draft.tex | 可编辑转录草稿；PDF/TXT导入草稿使用XeLaTeX，Agent还须重排版 |
| manifest.json | 原文件哈希、页数、提取状态；默认review_required且application_ready=false |
| fact_ledger.json | 空的事实/关键词/权重台账，供Agent或本人填写；契约为schemas/resume-fact-ledger.schema.json |
| AGENT_TASK.md | 可直接交给新对话的初始化指令及资料路径 |

PDF没有可靠文字层时，记录为需要逐页视觉阅读或OCR。混合PDF任一空白提取页
也会触发这个状态。pypdf只能提取文字，不能执行OCR；Agent用原始页面核对，
不得把空文本解释为没有经历。多栏PDF可能错序；此导入不保证还原原版布局。
[pypdf说明](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)。

导入过程不执行PDF或简历里的指令，也不编译不可信的原始LaTeX。
原始.tex作为输入保存，由Agent检查宏、外部资源和事实后再编译。
现存输出目录会被拒绝，不覆盖 `cv/source/current.tex` 或已交付材料。

## 2. 给新Agent的工作顺序

1. 阅读AGENTS.md、AGENT_HANDOFF.md、本指南和导入任务包；确定本机平台、私有根目录及主库角色。不得把公开演示人物当成当前候选人。
2. 逐页阅读原始简历并核对文字层；在fact_ledger中每个事实记录稳定ID、目标profile字段、值、来源ID、页码、原文及状态。
3. 区分“简历明写”“本人确认”“待确认”。本人确认还须记录日期与来源。简历写了2027年不等于确认了具体月日；教育日期不等于最早到岗日期。
4. 只将清楚、无冲突的原文映射为待审阅资料；冲突与缺失放进unresolved_questions。姓名拆分、GPA制式、时长、技能强弱及精确日期不能补猜。
5. 基于事实生成关键词与权重提案，标出证据范围及依据；本人确认目标职业、地区、招聘周期及偏好。不要为适配JD把需求转写成候选人经历。
6. 重建结构清晰的LaTeX，编译并视觉比较；本人审阅后才选择成为当前简历。初始化时使用新目录，不覆盖既有current.tex或投递包。
7. 检查档案、实际评分配置与合成正/反例；最后选一个真实岗位完成资格、字段和附件核对。默认3轮，不自动宣告通过。

法律与同意问题必须有本人明确答复：国籍/居留/许可、未来雇主支持、签证、
毕业后实习、迁居、薪资、来源/推荐、性别披露及接受政策。简历所在地、学校和
语言不能建立上述答案。相关未知值保持schema允许的空字符串或null；不得
把默认false解释为用户已选择“No”或已拒绝。同意条款初始false表示未授权。

## 3. 事实分别放在哪里

| 私有文件 | 放入的信息 | 如何溯源 |
| --- | --- | --- |
| profiles/application_profile.json | fields中的联系信息；education/work_experience/projects/languages/skills；custom_answers、显式授权和逐雇主同意 | fact_ledger里的profile_path使用如education[0].school；可在personal_facts_confirmation与附加provenance中记录来源 |
| cv/profile/evidence_profile.json | 真实毕业日期、学校、GPA及带范围的evidence_groups；candidate_summary、tailored_summaries、closing_strength | 每组只写原文可支持的经历，追加source_ids/fact_ids；项目证据不能写成商业工作经验 |
| cv/profile/application_keywords.json | 技术标签、行为例子、source_ids、claim_status及role_presets | sources对应原始文件哈希与页码；与事实台账ID关联 |
| config/candidate_scoring.json或job_bot.local.json | 真正被评分器读取的算法、词组、权重及来源/策略覆盖 | 台账scoring_proposals记录每组依据、正/反例结果与本人确认 |
| database/manual/jobs.csv、applications.csv | 本人手动录入的岗位和已发生的投递记录 | 正式URL、成功确认/回执和导入审计事件；详见manual-database.md |

CLI结构校验不等于事实确认或投递就绪。普通个人资料字段不能输入本schema
不允许的null；使用已有空值形状并在台账记“未知”。新加坡等额外地区不能仅
向location_scopes追加一个名字；现有授权校验只支持中国大陆、香港、美国，
其他地区需Agent处理具体门户答案与规则。

## 4. 从经历提取可用关键词和权重

每项关键词至少记录：术语、中文名、原文证据/页码、实际使用方式、范围、
证据ID、claim_status。例如“课程项目写过Python和SQLite”可以支持项目层面的
Python/SQL标签，不能自动推导多年商业后端经验、云平台能力或高级工程师资格。
团队项目只支持有事实的协作例子，不生成性格自评分。

技术关键词进入application_keywords时，只有
`supported_by_existing_records`可被当前选择器用于技术标签；协作例子只接受
`documented_behavior` / `behavior_based_interpretation`。后者须标明解释性质。
新增关键词本身不会修改岗位评分，也不会生成资历。

评分配置与关键词库分开：

| 算法 | 实际使用字段 | 分数含义 |
| --- | --- | --- |
| foundation_v2（现有默认） | foundation_groups.base_score/body_only_adjustment/min_body_hits、modifiers.points、secondary bonus | 优先选标题及术语特异性匹配的主方向，正文分类需足够匹配；加小幅次方向/修正，限0～100 |
| weighted_keywords_v1 | keyword_groups.weight/title_bonus/keywords/bonus_only | 每组只计一次；主组命中才计bonus_only组；标题匹配叠加title_bonus，总分限0～100 |

`examples/candidate_scoring_template.json`是可实际消费的虚构软件方向示例。
复制进私有config后调整include路径，选择一个算法并只修改它消费的字段：
保留foundation_v2而仅填写keyword_groups不会改变评分。

```bash
jobbot-config --config <private-candidate-scoring.json>
jobbot-settings plan --base-config <private-candidate-scoring.json>
```

Agent至少构造：有直接证据的目标岗位、相邻岗位、技能缺口岗位、高级岗位和
地区/毕业窗口不符岗位。记录实际score_job输出与人工预期，检查标题加分、
负权重、关键词碰撞和语言同义词；不要为了达阈值不断增加泛词。
权重代表检索偏好，分数不是录取概率或合法资格。资格不符独立标记，不能用
高分盖掉。当前strategy仍偏硬件且只实现既有三轨道；新专业/地区需改消费者，
不能仅在JSON里虚构新轨道。完整台账字段见schema，份数没有最低“堆词”要求。

## 5. 使用简历定制模块

重建的源文件须保留 `\begin{rSection}{Summary}` 和
`\begin{rSection}{Technical Skills}` 标记；其他教育/项目事实保留原文依据。
`examples/resume_template.tex`演示这些标记，人物与经历均为虚构。
英文可使用pdfLaTeX；Unicode/中文源选择XeLaTeX并配置实际可用字体。
日期读取私有evidence_profile.expected_graduation_date；空白时保留源日期，
不再把正职毕业日期改成固定的2027年6月。改日期前本人核实学校与日期范围。

先生成审阅文本；使用新私有输出目录：

```bash
cvbot --job-description <private-jd.txt> --company <company> --role <role> \
  --profile <private-evidence-profile.json> --out-dir <new-private-review-directory>
```

再使用已审閱源生成新PDF包：

```bash
cvbot --job-description <private-jd.txt> --company <company> --role <role> \
  --profile <private-evidence-profile.json> --resume-source <reviewed-source.tex> \
  --bundle-dir <new-private-bundle-root> --generate-bundle --latex-engine xelatex
```

也可用 `--job-url`从当前主库加载JD。关键词库由默认私有路径或
`--keyword-library`选择。cvbot只选择已有证据，现有求职信语言仍偏硬件，
其他行业应先由Agent审阅/调整措辞。PDF编译成功后须看页数、裁切、错字、
学校/日期/GPA和附件绑定。只有实际审阅才可以录入“附件通过”。
本人审阅后，可用 `applybot queue --job-url <stored-official-url>`建立申请，
用 `applybot prepare-profile --application-id <id> --resume <reviewed-pdf>`
`--cover-letter <reviewed-cover-pdf>`绑定实际附件。当前此命令要求两份PDF，
应按该岗位真实需求处理，不把“必须传参数”解释为雇主要求求职信。
逐岗档案现保存于私有outputs/application_bot/applications/<id>/profile.json。

## 6. 可复制给朋友的新对话指令

> 请先读本项目AGENTS.md、AGENT_HANDOFF.md、docs/platforms.md、
> docs/candidate-onboarding.md和docs/manual-database.md。
> 先检查环境及已有私有数据，保留已有文件。从我的原始简历PDF建立新导入包，
> 逐页核实事实，重建可编辑LaTeX，整理填表信息、证据关键词和实际评分配置。
> 对不确定的事实和偏好询问我，同时继续不依赖答案的整理。默认手动辅助，
> 不访问投递门户、不代点最终提交，不将高评分当资格或投递成功。
