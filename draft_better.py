#!/usr/bin/env python3
"""Frostclaw: review-first Ollama draft generator with validation retries.

Place beside existing agent.py and render_posts.py. Does not publish, approve,
run git, or send data outside the local Ollama service on 127.0.0.1.

Usage:
    python draft_better.py --topic "Equivalence partitioning in software testing"
    python draft_better.py --topic "Bug severity vs priority" --attempts 3
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

import agent

GUIDANCE = {
    "equivalence": (
        "Equivalence partitioning groups inputs expected to be processed similarly. "
        "Select representative values from valid and invalid classes; it does NOT "
        "mean testing every possible value. Distinguish boundary value analysis "
        "(testing class edges) from equivalence partitioning (sampling classes). "
        "Example for allowed integer quantity 1-10: valid class 1..10 (pick 5), "
        "too low (pick 0), too high (pick 12), non-integer (pick 2.5)."
    ),
    "boundary": (
        "Boundary value analysis focuses on edges of allowed ranges and values "
        "just inside and outside each edge. For a 3-20 character field, test "
        "2, 3, 20, 21; include other risk-based tests as needed."
    ),
    "severity": (
        "Bug severity concerns impact on the system/user; priority concerns "
        "how urgently the team should fix it. These can differ. Avoid asserting "
        "a fixed universal ranking or company-specific definitions."
    ),
    "regression": (
        "Regression testing looks for unintended breakage of existing functionality "
        "after change. Retesting confirms that a specific defect was fixed; "
        "smoke testing is a quick critical-functionality check on a build."
    ),
    "http": (
        "HTTP 400 generally means a bad request; 401 unauthenticated; "
        "403 forbidden; 404 not found; 429 rate limited; 500 server error; "
        "502 bad gateway; 503 service unavailable. Do not claim the exact "
        "cause of an error without evidence."
    ),
    "sql": (
        "SQL queries and database behavior depend on the engine and schema. "
        "Avoid unspecified claims about default ordering, NULL handling or "
        "transaction isolation levels."
    ),
    "api": (
        "Explain API behavior in terms of contract, status codes, payload "
        "validation and authentication. Do not imply all APIs behave identically."
    ),
}

EXAMPLE = {
  "id": "99",
  "pillar": "QA BASICS",
  "title": "A clearer bug report in 4 steps",
  "hook": "Make the issue easy for someone else to reproduce.",
  "steps": [
    {"label": "Set the context", "detail": "Name the app version and environment."},
    {"label": "Reproduce the issue", "detail": "List exact actions and test inputs."},
    {"label": "Compare outcomes", "detail": "Record expected and actual behavior."},
    {"label": "Attach evidence", "detail": "Add a screenshot when it helps."}
  ],
  "takeaway": "Specific steps save debugging time.",
  "caption": "Clear bug reports make collaboration easier. Include the environment, reproduction steps, expected result and actual result. Add evidence when helpful. What makes a bug report useful for your team?",
  "hashtags": ["#SoftwareTesting", "#BugReporting", "#QATesting", "#QualityAssurance"],
  "date": "2026-12-08"
}


def topic_guidance(topic: str) -> str:
    selected = [v for key, v in GUIDANCE.items() if key in topic.lower()]
    return "\n".join(selected) or (
        "Use only well-established, accurately stated technical guidance. "
        "If a claim depends on requirements or context, say so."
    )


def draft_prompt(topic: str, number: str, publication_date: str, existing: list) -> str:
    titles = "; ".join(p["title"] for p in existing[-14:])
    exemplar = dict(EXAMPLE, id=number, date=publication_date)
    return f"""You write original educational Instagram infographics for Frostclaw Software.
TOPIC: {topic}
AUDIENCE: beginner and junior QA testers.
FACTUAL REFERENCE FOR THIS TOPIC (follow it):
{topic_guidance(topic)}

CRITICAL: Output exactly one JSON object, with no Markdown, explanation or code fence.
Follow this exact JSON shape (the topic/content must be different):
{json.dumps(exemplar, ensure_ascii=False, indent=2)}

STRICT FORMAT RULES:
- id MUST be {json.dumps(number)}; date MUST be {json.dumps(publication_date)}.
- pillar MUST be exactly one of: QA BASICS, WORKFLOW, SPREADSHEETS.
- title: 8-64 characters; hook: 8-110; takeaway: 8-95; caption: 80-450.
- steps: exactly FOUR objects, each with label 2-35 characters and detail 4-100 characters.
- Step labels must NOT start with 'Step 1:', etc. Keep labels concise.
- hashtags: EXACTLY FOUR strings; each starts with '#' and contains ONLY letters, numbers or underscores (NO spaces).
- Prefer one concrete example with realistic values and expected results.
- Explain the requested TOPIC, not an adjacent technique. Avoid absolute guarantees.
- NO fake data, fake statistics, private information, paid-product pitch, or copied passages.
- Avoid duplicate topics/titles, including: {titles}.
- This is educational content, not a sales promotion.
Return only the finished JSON object."""


def call_ollama(prompt: str, model: str, timeout: int) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 1600},
    }
    req = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout) as response:
        body = json.load(response)
    raw = body.get("response", "")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Ollama returned a non-object JSON value")
    return result


def structural_problems(post: dict, existing: list) -> list[str]:
    # Reuse production validation; extra checks guard against shallow samples.
    problems = agent.validate_post(post, existing)
    if not problems:
        if len(post["caption"]) < 80:
            problems.append("caption must contain at least 80 characters")
        if len(post["hashtags"]) != 4:
            problems.append("use exactly four hashtags")
    return problems


def choose_id_date() -> tuple[str, str, list[dict]]:
    existing = agent.calendar_posts()
    agent.DRAFTS.mkdir(exist_ok=True)
    max_id = max([int(p["id"]) for p in existing] + [int(p.stem) for p in agent.DRAFTS.glob("*.json") if p.stem.isdigit()] + [0])
    number = f"{max_id+1:02}"
    pending = []
    for path in agent.DRAFTS.glob("*.json"):
        try:
            obj = agent.read_json(path)
            if isinstance(obj, dict):
                pending.append(obj)
        except (OSError, ValueError):
            print(f"Warning: unreadable draft ignored: {path}", file=sys.stderr)
    new_date = agent.next_day(existing + pending).isoformat()
    return number, new_date, existing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True, help="Technical subject for the infographic")
    parser.add_argument("--model", default=None, help="Ollama model; defaults to config.json")
    parser.add_argument("--attempts", type=int, default=3, help="Maximum generations, including retries (1-5)")
    parser.add_argument("--timeout", type=int, default=240, help="Seconds allowed per Ollama request")
    args = parser.parse_args()
    if not 1 <= args.attempts <= 5:
        parser.error("--attempts must be 1..5")
    if not 10 <= args.timeout <= 900:
        parser.error("--timeout must be between 10 and 900 seconds")

    number, new_date, existing = choose_id_date()
    model = args.model or agent.config().get("default_model", "llama3.2:3b")
    prompt = draft_prompt(args.topic, number, new_date, existing)
    best = None
    best_problems = ["No successful Ollama generation"]
    for attempt in range(1, args.attempts+1):
        print(f"Generating post {number} ({attempt}/{args.attempts}) with {model}...", flush=True)
        try:
            draft = call_ollama(prompt, model, args.timeout)
        except Exception as exc:
            print(f"Ollama generation failed: {exc}", file=sys.stderr)
            if attempt == args.attempts:
                return 2
            continue

        # The agent controls ID and date; never trust those fields from model output.
        draft["id"] = number
        draft["date"] = new_date
        problems = structural_problems(draft, existing)
        if not problems:
            best, best_problems = draft, []
            print("All structural checks passed.")
            break
        print("Validation warnings: " + "; ".join(problems))
        if best is None or len(problems) < len(best_problems):
            best, best_problems = draft, problems
        # Ask the model to revise its exact output, without quietly truncating fields.
        prompt = (
            "Correct the following JSON Instagram infographic draft. Return ONLY the "
            "complete valid JSON object. Keep the original topic and technical meaning. "
            "Preserve id and date. Make only the changes needed for strict formatting; "
            "do not claim guarantees or confuse adjacent QA concepts.\n"
            + "Topic: " + args.topic + "\nTechnical guidance: " + topic_guidance(args.topic)
            + "\nErrors to fix: " + json.dumps(problems, ensure_ascii=False)
            + "\nRules: title 8-64 chars, hook 8-110, takeaway 8-95, caption 80-450, "
            "4 steps with label 2-35 and detail 4-100 characters, exactly 4 hashtags "
            "matching #LettersNumbers_Underscores with no spaces.\n"
            + "Current draft: " + json.dumps(draft, ensure_ascii=False)
        )

    if best is None:
        print("No draft saved. Check that Ollama is running and your model is available.", file=sys.stderr)
        return 2
    target = agent.DRAFTS / f"{number}.json"
    if target.exists():
        print(f"File exists, refusing to overwrite: {target}", file=sys.stderr)
        return 2
    target.write_text(json.dumps(best, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Draft saved: {target}")
    if best_problems:
        print("Still needs manual formatting fixes before approval:")
        for issue in best_problems:
            print(" - " + issue)
        return 1
    print("Structural checks passed. IMPORTANT: factual accuracy still needs human review.")
    print(f"Review with: Get-Content .\\drafts\\{number}.json -Raw")
    print("Only then approve with: python agent.py approve --id " + number + " --reviewed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
