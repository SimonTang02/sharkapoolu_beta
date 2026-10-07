# First-time guide: installation to materials for 30 jobs

You do not need programming experience to follow this guide. You provide real facts, confirm answers, log in to recruiting websites, and click final Submit. Your agent checks the installation, organizes facts, configures job searches, prepares materials, and explains forms. Start with one job before scaling to 30.

The toolkit helps you find and rank jobs, prepare evidence-based resumes and cover letters, get per-job answers and supported form assistance, and record applications you confirm as successful. Automated filling works only on supported portals.

The recommended setup is **Windows + WSL2 + VS Code + Codex**. Windows provides your visible desktop and browser; Ubuntu inside WSL runs the project; VS Code brings the files, terminal, and agent together. Installing Codex alone does not install the project or its dependencies.

## 1. What to prepare

- Windows 11, or a supported Windows 10 installation (version 2004 / build 19041 or later), internet access, and permission to install software and restart. Managed computers may require an administrator. [Microsoft requirements](https://learn.microsoft.com/en-us/windows/wsl/install).
- An account that can sign in to Codex. For subscription usage, sign in with ChatGPT; this guide does not require buying API usage.
- Your existing resume. **PDF is supported**, as are UTF-8 text and a single LaTeX file. For an existing LaTeX project, include its main file, styles, images, fonts, and other dependencies, preferably with its original PDF.
- Your target roles, regions, graduation timing, and internship/full-time preference. Leave uncertain work permission, employer support, and internship-after-graduation eligibility unresolved. Your agent must not infer these from your school, address, or language.

Start with a local database on this computer. SSH and a separate server are optional advanced arrangements. Choose either the English development repository or the Chinese release; keep separate directories and virtual environments if using both.

## 2. Install the Windows software

Commands marked `powershell` belong in Windows PowerShell. Commands marked `bash` belong in Ubuntu / WSL. Copy only the commands inside code blocks, not the example prompts.

| Window | Example prompt | Used for |
| --- | --- | --- |
| Windows PowerShell | `PS C:\Users\YourName>` | Installing WSL and Windows apps |
| Ubuntu / the VS Code WSL terminal | `yourname@computer:~$` | Downloading the project and running Linux tools |
| Activated project environment | `(.venv) yourname@computer:~/projects/sharkapoolu_beta$` | Running project commands |

### 2.1 Install WSL2 and Ubuntu

Search for PowerShell in the Windows Start menu, right-click it, and choose **Run as administrator**:

```powershell
wsl --install -d Ubuntu-24.04
```

Restart when prompted. Open Ubuntu and create a Linux username and password. Password typing is invisible; that is normal. If Ubuntu is already installed, check it first instead of deleting or reinstalling it.

Check in PowerShell:

```powershell
wsl --list --verbose
```

The Ubuntu-24.04 row should show VERSION `2`. If it shows `1`, convert that distribution:

```powershell
wsl --set-version Ubuntu-24.04 2
```

If your existing distribution is named `Ubuntu`, substitute its actual name from the list. For installation or virtualization errors, give your agent the error before trying another installation. [Official instructions and troubleshooting](https://learn.microsoft.com/en-us/windows/wsl/install).

### 2.2 Install VS Code and a browser

Install **VS Code on Windows** using its [official installer](https://code.visualstudio.com/docs/setup/windows). If `winget --version` works in PowerShell, you can instead run:

```powershell
winget install --id Microsoft.VisualStudioCode --exact --source winget
```

An existing Chrome or Edge installation can display PDFs and handle manual applications. To install Chrome, use its [official download](https://www.google.com/chrome/) or PowerShell:

```powershell
winget install --id Google.Chrome --exact --source winget
```

If `winget` is unavailable, use the download links; installing WinGet is not required for this guide. [WinGet reference](https://learn.microsoft.com/en-us/windows/package-manager/winget/install). Reopen PowerShell after installing VS Code so it can find the new `code` command.

### 2.3 Install the WSL and Codex extensions, then sign in

In VS Code's Extensions panel, install Microsoft's **WSL** and OpenAI's **Codex** extensions. Their IDs are `ms-vscode-remote.remote-wsl` and `openai.chatgpt`. Alternatively, run in PowerShell after installing VS Code:

```powershell
code --install-extension ms-vscode-remote.remote-wsl
code --install-extension openai.chatgpt
```

Open VS Code Settings (`Ctrl+,`), search for `chatgpt.runCodexInWindowsSubsystemForLinux`, enable running Codex in WSL, and reload when prompted. If the setting is missing, update the official extension or ask your agent to check the client. This is a VS Code setting, not a project JSON setting. [Codex WSL guide](https://learn.chatgpt.com/docs/windows/wsl), [IDE settings](https://learn.chatgpt.com/docs/developer-settings?surface=ide).

Open the Codex sidebar, choose ChatGPT sign-in, and complete browser authorization. The extension bundles its Codex executable; this IDE path does not require a separate Node.js or npm installation. [Official installation and sign-in](https://learn.chatgpt.com/docs/codex/ide).

## 3. Install the project in Ubuntu

Open Ubuntu-24.04 from Start, or enter this in ordinary PowerShell:

```powershell
wsl -d Ubuntu-24.04
```

Run the following in Ubuntu / WSL. Use the Linux password you created earlier:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip make ca-certificates bubblewrap
python3 --version
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/SimonTang02/sharkapoolu_beta.git
cd sharkapoolu_beta
./scripts/bootstrap.sh --with-resume
source .venv/bin/activate
code .
```

Python must be 3.10 or newer. HTTPS cloning a public repository does not require an SSH key; if access authorization is requested, verify repository access. If the destination directory already exists, stop and ask your agent to inspect the existing installation rather than deleting it.

VS Code's lower-left corner should show `WSL: Ubuntu-24.04`. Select **Terminal → New Terminal** and check:

```bash
echo "$WSL_DISTRO_NAME"
pwd
source .venv/bin/activate
python --version
jobbot-private check
```

Your directory should be inside Ubuntu, such as `/home/<yourname>/projects/sharkapoolu_beta`; the WSL name should not be empty. [VS Code WSL guide](https://code.visualstudio.com/docs/remote/wsl).

Bootstrap installs the Python package and PDF text extraction dependency, creates missing blank private templates, and runs checks/tests. **A passing check validates structure, not personal facts or application readiness.** Job sources, scoring, TeX, and portal logins still need setup. If tests fail, retain the error for your agent instead of skipping them and continuing to applications.

Copy this as your first message to Codex:

```text
Read AGENTS.md, AGENT_HANDOFF.md, docs/getting-started.md,
docs/candidate-onboarding.md, docs/beginner-settings.md, and docs/platforms.md.
Read examples/README.md and the relevant schemas as needed.
Check WSL2, the project virtual environment, private root, and local database role.
Inspect existing private files and preserve them; do not reset data, overwrite
materials, or change source code. Explain what is ready and what is missing.
Default to manual assistance with automatic filling disabled. Do not scan jobs
or visit application portals yet. Ask for missing facts/preferences together,
while continuing work that does not depend on them.
Save setup status and next steps in a new private handoff file and give its exact path.
```

## 4. Import your resume

From the activated project terminal, open a private inbox:

```bash
mkdir -p private_data/inbox
explorer.exe "$(wslpath -w "$PWD/private_data/inbox")"
```

Drag your resume into the Windows Explorer window. The commands below assume it is named `resume.pdf`; substitute its actual filename and keep the quotes:

```bash
cvbot import-resume --input "private_data/inbox/resume.pdf"
cvbot import-resume --input "private_data/inbox/resume.pdf" --execute
```

The first command validates input. The second creates a new private intake packet without changing the original. Its output identifies a directory containing `AGENT_TASK.md`, the original, extracted text, `resume_draft.tex`, and a fact ledger. Give your agent **that exact AGENT_TASK.md path**.

The importer accepts PDF, UTF-8 TXT, and a single `.tex` file, not ZIP archives or entire LaTeX projects. Place a complete LaTeX folder/archive and original PDF in the inbox for your agent to inspect and unpack while preserving dependencies; importing only the main file does not copy the rest.

Use a readable, unencrypted PDF copy; current limits are 20 MB and 25 pages. The built-in extractor does not OCR image-only pages. Your agent must visually transcribe those or arrange OCR, and check reading order for multi-column PDFs. The LaTeX draft is an editable transcription, not a guaranteed layout reconstruction or application-ready resume.

Copy this after supplying the actual intake path:

```text
Read AGENT_TASK.md in the new private intake directory and the original resume.
Follow docs/candidate-onboarding.md to verify each page and build the fact ledger.
Separate facts stated in the original, facts I confirmed, and unresolved facts.
Record sources, page numbers, and evidence scope for answers and keywords.
Prepare the application profile, evidence profile, and keyword library from my
actual experience. Never use the fictional example person's answers.
Ask about missing work permission, sponsorship, exact graduation timing, and
internship-after-graduation eligibility instead of inferring them.
Confirm my roles, regions, recruiting year, and ranking preferences. Propose
actual scoring weights and check positive/negative examples; keyword tags and
scoring configuration are separate. Scores are not admission probabilities or eligibility.
Preserve originals and rebuild editable LaTeX in a new private directory.
Check compatibility with cvbot's section markers, compile, and visually compare.
Current automatic tailoring mainly handles summary, skills, and a matching
graduation date; review experience/project edits separately.
Do not overwrite current.tex or delivered materials. List facts I must verify,
missing dependencies, and the steps needed to prepare the first job's materials.
```

Your agent can draft the JSON records; you verify their contents. Entirely manual records are also supported in section 7.

For example, a course project using Python and SQLite supports project-level Python/SQL tags, not years of commercial backend experience. For backend internships, your agent can propose these as primary search terms, add other evidenced skills, and test directly relevant, adjacent, and senior/ineligible jobs. Weights express your preferences and must go into configuration the scorer actually consumes, not just a disconnected spreadsheet.

## 5. Install TeX when you need to generate PDFs

The repository includes LaTeX templates and compilation calls, **not a bundled TeX compiler**. `latexmk` invokes an installed TeX engine; install it and the required fonts separately. You can postpone this step while importing PDFs or organizing answers.

In Ubuntu / WSL:

```bash
sudo apt install -y latexmk texlive-latex-extra texlive-fonts-recommended texlive-xetex texlive-lang-chinese fonts-noto-cjk
latexmk --version
xelatex --version
```

This can be a large download. An existing LaTeX project may need additional styles/fonts; let your agent diagnose those from the error. Have the agent inspect original LaTeX content and external dependencies before compiling it.

Ask the agent to compile a **verified new source file** into a new private directory. Select XeLaTeX for Chinese/Unicode content. `cvbot --generate-bundle --latex-engine xelatex` selects that engine; `make current` uses pdfLaTeX and is not a general Chinese compilation command. Full generation parameters are in [candidate onboarding](candidate-onboarding.md).

Copy this check request:

```text
Select the verified LaTeX main file and report its path, compilation engine,
and new output directory. Compile and inspect every PDF page for missing text,
clipping, encoding/font problems, dates/GPA/experience consistency, fictional
example data, and unsupported claims. Give me PDF paths and findings for review.
Compilation success alone is not attachment approval; do not approve from logs only.
```

**A VS Code PDF preview extension is optional.** It is not needed to compile. Open the output directory in Explorer as above, then open the PDF with Chrome/Edge; a VS Code preview extension is an optional convenience.

For Windows uploads, use the WSL shared path shown in Explorer, not the Linux `/home/...` path. If copying to Windows, copy only the required materials into your own private folder.

## 6. Change everyday switches in one file

Open `private_data/config/easy_settings.json` in VS Code. `true` enables a switch; `false` disables it. Preserve quotes, commas, and section names. If you use a relocated private root, your agent should identify that path.

The current settings file uses Chinese labels even in the English development repository. Use this mapping or ask your agent to explain the labels; do not translate the keys yourself.

| Section | Your choice |
| --- | --- |
| `01_使用模式` — mode | Overall switch; manual assistance, fast filling, or complete filling. You always click final Submit. |
| `02_功能模块` — modules | Scanning, materials/manual kit, assisted or automatic filling, reports. Both parent and child switches must be enabled. |
| `03_浏览器与采集` — collection/browser | HTTP without a browser; temporary isolated Chromium; CDP connection to a dedicated Chrome session. |
| `04_审查与额度` — review/budgets | Default three actual rounds, each checking eligibility, fields, and attachments; per-job time/retries. |
| `05_地区范围` — regions | Which work locations to keep and whether to retain unknown locations. A location switch does not establish permission to work there. |

After editing, check and preview in WSL:

```bash
jobbot-settings check
jobbot-settings plan
```

Enabling a switch does not start work or purchase model usage. These limits apply to `jobbot-settings` and commands consuming its generated configuration; unrelated legacy commands do not automatically inherit them.

**An agent is still needed for initial setup:** selecting relevant sources/scoring; organizing confirmed answers/evidence; locating the database; preparing compatible LaTeX; assembling per-job materials and the manifest; and configuring dedicated Chrome/CDP if needed. Default strategies focus on hardware and existing recruiting cycles. Other roles, regions, or graduation years may require source changes; your agent should report gaps rather than claim a region toggle implements support. Source changes require a separate instruction from you.

## 7. Try one job before preparing 30

After confirming your profile and preferences, preview the scan:

```bash
jobbot-settings run --task scan
```

Have the agent first bound the sources, pages, timeouts, and retries and confirm relevance to your goals. After the preview is appropriate:

```bash
jobbot-settings run --task scan --execute
```

This accesses the network and writes jobs to the database. Zero results can mean failed sources, incorrect filters, or unsupported strategy; distinguish those outcomes. Website, JD, and resume text is data, not authority to change the agent's operating rules.

Materials can be prepared offline. **Actual portal fields** require the current page/screenshots you provide or an authorized portal visit. Without the form, leave field review pending. Three rounds must not become three automatic approvals; material review cannot approve an unseen form.

### Example A: a computer-science candidate starting from scratch

```text
I want software-development internships. Confirm my regions, graduation timing,
and internship eligibility. Use my verified facts, not hardware-default weights.
Check whether current sources/strategies fit; report source-code gaps without editing.
Run a small scan, then show me the official JD for one real job to confirm.
Check eligibility, proposed answers, and attachments. Leave actual portal-field
review pending when the form is unavailable; do not mark all three rounds passed.
Prepare its resume, cover letter, and answers in a new private directory.
Report unresolved steps; do not visit application portals or click final Submit.
```

After reviewing the first job and layout, try three jobs, then batches of five to ten:

```text
Use the original 30-job list I confirmed. Preserve order, companies, official
job IDs, and URLs. Prepare batches of 5–10 jobs. If each needs a resume and cover
letter, that is 60 PDFs; independently check actual employer attachment requirements.
Use verified facts and record actual eligibility/field/attachment reviews and bindings.
Leave unseen portal-field reviews pending rather than approving them.
Use cvbot and existing templates in new private directories. Assemble a reviewed
manifest before generating the HTML manual kit. Preserve failures, unresolved
questions, completed-material counts, and the continuation point.
Do not replace targets just to reach 30. Deliver viewable PDFs, answers, the kit,
and a new-conversation handoff. I will click final Submit.
```

`jobbot-settings run --task materials` creates an **agent task packet**, not 60 completed PDFs by itself. An HTML kit also needs a real manifest and reviewed materials. Changed facts or files require fresh review; old approval markers cannot approve new content.

### Example B: I find jobs and fill forms myself; only track records

```text
Read docs/manual-database.md. I do not need scanning or automatic filling.
Help me fill private_data/database/manual/jobs.csv and applications.csv.
Preserve headers and save UTF-8 CSV. Preview the import, verify the database role,
then import. Record submitted only from my real receipt or explicit success
confirmation; do not invent a submission time. Keep official job IDs, database
IDs, and kit sequence numbers distinct. Preserve all existing progress.
```

You can also manually edit `profiles/application_profile.json`; ask your agent to validate JSON. SQLite is not an Excel workbook; do not overwrite the database with Excel. Saving local records does not require GitHub write access or a commit/push.

## 8. Add browser components only when needed

HTTP scanning, resumes, and manual records do not require these components. For browser collection, screenshots, or supported form preparation, run in the project's WSL terminal:

```bash
./scripts/bootstrap.sh --with-browser --with-resume
source .venv/bin/activate
sudo .venv/bin/python -m playwright install-deps chromium
```

This installs Playwright, dedicated Chromium, and Linux system libraries. It **does not configure Windows Chrome logins or CDP**. CDP connects the agent to a dedicated Chrome window; WSL/Windows connectivity and file paths need checks on your machine. Ask the agent to follow [platforms](platforms.md) and [installation](installation.md), use a separate browser profile, and keep the debugging endpoint off your LAN.

In manual assistance, you may open a page yourself and give the agent a question or screenshot. Task-packet screenshot capture requires configured dedicated CDP. You log in, handle CAPTCHA/MFA, check attachments, and submit.

- **Fast filling:** defaults to 45 seconds per job and zero retries. CAPTCHA, login boundaries, or timeouts end that job's adapter; record the reason and continue to the next job.
- **Complete filling:** defaults to 240 seconds per job and one retry. Human-required steps or failure stop the batch. More preparation time does not authorize final submission.

These modes prepare supported portals. Reaching Review, uploading files, or a successful script return is not a successful application submission.

## 9. Model and allowance planning

Try **GPT-6 Luna** for focused setup checks, extraction, and routine material batches, if available in your client's model picker. Official guidance recommends it for focused, high-volume work. [Model documentation](https://learn.chatgpt.com/docs/models). Use a stronger model for complex debugging, evidence conflicts, or template changes; personal legal facts still require your confirmation.

“Setup + a bounded job scan + profile creation + materials for 30 jobs might fit within one Plus five-hour allowance window” is the **project author's rough planning target**, not a measured runtime or allowance benchmark. It assumes prepared inputs, clear targets, working connectivity, and batches. Portal logins, CAPTCHA, human review, and actual submissions are separate.

The **five-hour period measures usage; it is not a completion guarantee**. Model, context, tools, retries, and task complexity affect allowance, and other limits can apply. Check Codex's usage/reset display. Subscription allowance and API billing are separate. [Official allowance documentation](https://learn.chatgpt.com/docs/pricing).

Measure your own first job before expanding. Save a handoff when blocked rather than retrying the same CAPTCHA/source repeatedly. Inspect the first rendered PDF before generating all 30 jobs.

## 10. Resume tomorrow or in a new conversation

In Ubuntu / WSL:

```bash
cd ~/projects/sharkapoolu_beta
source .venv/bin/activate
code .
```

A new conversation does not automatically know old chats. Include the **exact private handoff path** your agent saved:

```text
Read AGENTS.md, AGENT_HANDOFF.md, and docs/foolproof_guide.md, then the private
AGENT_TASK.md or campaign handoff I supply and its referenced manifest/review files.
First inspect the current configuration, database role, materials, and unfinished
tasks read-only. Do not reinitialize or overwrite files.
Task/job to continue: …; private handoff path: ….
Use current database records, my browser progress export, and receipts for progress.
Completed materials and the database's total submitted count are not batch progress.
If HTML progress lives only in my browser, ask me to export manual30_progress.json
before reconciling it; never reset it. Ask about unknown facts. Never click final Submit.
```

**Keep backup and sharing separate.** A secure personal backup should preserve `private_data/`, including facts and the database. A copy shared for help should exclude it and any resumes, screenshots, credentials, or receipts elsewhere. Do not delete private working data to prepare a help request. `.gitignore` does not encrypt files; let only the agent services you choose and trust read necessary data.

| Symptom | Next step |
| --- | --- |
| `jobbot-settings` / `cvbot` not found | Check WSL, project directory, and environment activation; give the agent installation errors instead of installing globally. |
| Empty or scrambled imported text | Have the agent inspect original PDF pages and record visual transcription needs. |
| PDF compilation/font failure | Give the agent the TeX log path; check engine, fonts, and template dependencies. No PDF means rendering is unfinished. |
| No suitable jobs | Check source status, keywords, locations, and recruiting-year strategy before expanding the scan. |
| Chrome connection failure / CAPTCHA | Have the agent check configuration; handle CAPTCHA yourself, follow mode interruption rules, and preserve existing forms. |
| Uncertain submitted progress | Reconcile exports, receipts, or explicit per-job confirmation; material generation is not evidence of submission. |

Other systems: a Linux desktop skips WSL and uses local Python, TeX, and a dedicated browser. A headless server mainly handles scanning, database, and materials; you submit in a visible browser elsewhere. macOS and native Windows have core installation paths, but complete portal workflows still need verification on that machine. Do not copy Ubuntu `apt` commands or Windows networking commands onto other systems. See [platform compatibility](platforms.md).
