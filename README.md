# Frostclaw Software — Phase 2: Review-first content agent

A practical, zero-subscription workflow built for @frostclaw.software. **It does not publish posts automatically, use credentials or contact Instagram.** It prepares graphics and captions, and gives your connected ChatGPT Metricool assistant public links after you upload the static gallery.

## Already working

- Includes our **12 existing original posts** from the Frostclaw starter pack.
- Status file marks **01–04 as already scheduled in Metricool** (verified November 20, 2026).
- One command validates post structure, renders fresh 1080×1350 brand graphics, creates captions, a queue spreadsheet, and a public gallery.
- Optional local AI drafting via **Ollama**, with mandatory human review before accepting new posts.
- No Metricool API plan, OpenAI API key, Meta API token or paid AI subscription is required for this batch workflow.

## 1. Run locally

Install Python 3.10+ (Windows or Ubuntu), then open a terminal in this folder:

```bash
python -m pip install -r requirements.txt
python agent.py check
python agent.py build
```

Open `docs/index.html` in your browser to preview all graphics and descriptions. See `metricool_queue.csv` for the planned dates, filenames, and hosting URLs. Posts 01–04 are explicitly marked `ALREADY_SCHEDULED`; do not queue them again.

## 2. Host images as a free public informational gallery (GitHub Pages)

Use an existing GitHub account or create one. Our content is an educational tech-tips gallery, **not a store or an ecommerce checkout site**. Do not upload sensitive data or credentials.

1. Create a **public** GitHub repository named `frostclaw-tech-tips`.
2. Edit `config.json` and replace `DragArso` with your real GitHub username.
3. Run `python agent.py build` again.
4. Push the project to the repo:

```bash
git init
git add .
git commit -m "Initial Frostclaw educational content gallery"
git branch -M main
git remote add origin https://github.com/DragArso/frostclaw-tech-tips.git
git push -u origin main
```

If you already have a repository, do not reinitialize it; commit your changes as usual. Replace the placeholder in the remote URL. You must authenticate to GitHub using Git Credential Manager or GitHub CLI, not a password pasted into this chat.

5. In GitHub repo **Settings → Pages**, choose **Deploy from a branch** → `main` → `/docs` → Save.
6. Check that this site opens: `https://DragArso.github.io/frostclaw-tech-tips/`.
7. Open one direct PNG URL from `metricool_queue.csv` in a private/incognito browser. It must display the image without signing in before you schedule via ChatGPT.

The published gallery and its images are public. Never commit secrets, private customer content or unpublished confidential material. You can remove the page later, but public copies might be cached.

### If you don't want GitHub

You can host the prepared PNG images in publicly accessible Drive/Dropbox and provide their accessible file links. Metricool accepts public media URLs; the exact Google Drive/Dropbox link format varies. That route usually involves more manual uploads.

## 3. Schedule with ChatGPT + Metricool (free plan)

Return to the ChatGPT conversation with Metricool connected and say:

> I've published the Frostclaw tech-tips gallery at https://DragArso.github.io/frostclaw-tech-tips/. Please verify image links for posts 05–08, show me their captions and dates, and schedule them via Metricool only after I approve.

Our Metricool brand ID is already connected. The link lets the assistant find public images and schedule via the connected Metricool workflow. **Avoid scheduling 01–04 a second time.** After scheduling 05–08 and confirming them in Metricool, run `python agent.py mark-scheduled --ids 05 06 07 08` to protect against future duplicates.

This is **AI-assisted batch scheduling**, not a background service that runs forever. Metricool's **direct API** is not available on its Free plan. ChatGPT does not run unattended content generation by itself. If you later need zero-touch scheduling, it requires a supported higher-tier API plan or another authorized publishing solution.

## 4. Optional free local AI generator for fresh drafts

Ollama can generate post drafts on your own computer. It may be slow on CPU-only laptops and requires a model download.

Install Ollama from its official site, open Ollama, and then:

```bash
ollama pull llama3.2:3b
python agent.py draft --topic "What is equivalence partitioning?"
```

A draft goes into `drafts/13.json` (or another next ID). **Read it, check the actual technical facts, fix any mistakes, and check image claims before proceeding.** The local model is not a reliable independent fact-checker.

When satisfied:

```bash
python agent.py approve --id 13 --reviewed
python agent.py build
```

The new post appears in `docs/` and `metricool_queue.csv`. It will *not* publish or schedule itself. Rerun `git add . && git commit -m "New approved tip" && git push` to update public media before requesting scheduling.

If you prefer ChatGPT for generating new posts, edit or append the same JSON schema under `approved/` after review. See `content/posts.json` for examples. No paid model API is required.

## Quality and safety

The script validates required fields, text lengths, hashtags, duplicate titles, and a few risky phrases. It **cannot** independently guarantee the accuracy of technical claims, copyrights, licensing or suitability. Approval is intentionally required before a new AI-written draft enters the gallery. The hosted posts are **public** once pushed. Never embed account passwords or tokens in the repository.

The plan is to test educational value and audience response first, not to spam generic content or claim guaranteed income.

## References

- Metricool API access: https://help.metricool.com/plans-add-ons-and-api-access-explained-xux1u
- Metricool MCP free plan: https://help.metricool.com/mcp-limits-and-plan-requirements-h72jg
- Schedule with a direct image URL: https://help.metricool.com/how-to-schedule-a-post-at-different-times-on-each-network-using-metricools-mcp-8tmhd
- GitHub Pages /docs setup: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- Ollama generation API: https://docs.ollama.com/api/generate
