import contextlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/jev/scripts"))
import jev


SCENARIOS = (
    "jev-triage", "jev-documents", "jev-act", "jev-eval",
)


class SkillCatalogTests(unittest.TestCase):
    def test_five_entrypoints_cover_former_workflow_modes(self):
        # Public navigation contract, not an assertion about automatic model routing.
        modes = (
            ('jev', 'SKILL.md', 'assets/checkpoint.json'),
            ('jev', 'references/setup.md', None),
            ('jev', 'references/routing.md', 'assets/routing.json'),
            ('jev', 'references/context.md', 'assets/context.json'),
            ('jev-triage', 'SKILL.md', 'assets/example.json'),
            ('jev-documents', 'SKILL.md', 'assets/example.json'),
            ('jev-documents', 'references/find-code.md', 'assets/find-code.json'),
            ('jev-eval', 'references/code-review.md', 'assets/code-review.json'),
            ('jev-eval', 'references/workflows.md', 'assets/example.json'),
            ('jev-act', 'references/ui.md', 'assets/example.json'),
            ('jev-act', 'references/world.md', 'assets/world.json'),
        )
        for name, guide, example in modes:
            with self.subTest(skill=name, mode=guide):
                folder = ROOT / 'skills' / name
                entry = (folder / 'SKILL.md').read_text()
                self.assertTrue((folder / guide).is_file())
                if guide != 'SKILL.md':
                    self.assertIn(f']({guide})', entry)
                if example:
                    self.assertTrue((folder / example).is_file())
                    jev.validate_request(json.loads((folder / example).read_text()))

    def test_copied_collection_links_and_examples_in_three_host_layouts(self):
        environment = {k: v for k, v in os.environ.items()
                       if k not in {'OPENROUTER_API_KEY', 'TYPESAFE_API_KEY', 'JEV_MODEL'}}
        for host in ('.agents', '.claude', '.opencode'):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as tmp:
                destination = Path(tmp) / host / 'skills'
                shutil.copytree(ROOT / 'skills', destination,
                                ignore=shutil.ignore_patterns('__pycache__'))
                self.assertEqual({p.parent.name for p in destination.rglob('SKILL.md')},
                                 {'jev', *SCENARIOS})
                for doc in destination.rglob('*.md'):
                    text = re.sub(r'```.*?```', '', doc.read_text(), flags=re.S)
                    for link in re.findall(r'\]\(([^)\s]+)\)', text):
                        url = urlsplit(link)
                        if not url.scheme and url.path:
                            self.assertTrue((doc.parent / unquote(url.path)).is_file(),
                                            f'{doc}: {link}')
                examples = [(name, 'example.json') for name in SCENARIOS]
                examples += [('jev', 'checkpoint.json'), ('jev', 'routing.json'),
                             ('jev', 'context.json'), ('jev-documents', 'find-code.json'),
                             ('jev-eval', 'code-review.json'), ('jev-act', 'world.json')]
                for name, example in examples:
                    path = destination / name / 'assets' / example
                    run = subprocess.run([sys.executable,
                        str(destination / 'jev/scripts/jev.py'), 'decide', str(path), '--dry-run'],
                        cwd=tmp, env=environment, capture_output=True, text=True, check=True)
                    self.assertEqual(json.loads(run.stdout), json.loads(path.read_text()))
                builder = subprocess.run([sys.executable,
                    str(destination / 'jev-eval/scripts/prepare.py'),
                    str(destination / 'jev-eval/assets/transcripts.jsonl'),
                    '--out-dir', str(Path(tmp) / 'prepared')], cwd=tmp,
                    env=environment, capture_output=True, text=True, check=True)
                self.assertFalse(json.loads(builder.stdout)['jev_called'])
                self.assertFalse(json.loads(builder.stdout)['target_called'])

    def test_migration_and_release_guidance_do_not_keep_alias_skills(self):
        guide = (ROOT / 'docs/skill-migration.md').read_text()
        for name in ('jev-setup', 'jev-route', 'jev-context', 'jev-find-code',
                     'jev-code-review', 'jev-redteam', 'jev-ui', 'jev-simulation'):
            self.assertIn(f'`{name}`', guide)
            self.assertFalse((ROOT / 'skills' / name / 'SKILL.md').exists())
        for term in ('symlink', 'approval', 'backup', 'outside', 'verification fails'):
            self.assertIn(term, guide)
        for name in ('docs/install.md', 'docs/installation.md'):
            text = (ROOT / name).read_text()
            self.assertIn('v0.2.0', text)
            self.assertIn('eleven', text)
            self.assertIn('reviewed', text)
            self.assertIn('skill-migration.md', text)

    def test_agent_first_update_entrypoint_and_safety_contract(self):
        url = "https://raw.githubusercontent.com/wuyoscar/jev-skill/main/docs/update.md"
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            update = text.split('<a id="update"></a>', 1)[1].split('<a id="usage"></a>', 1)[0]
            self.assertIn(url, update)
            self.assertIn("```text", update)
            self.assertIn("](docs/update.md)", update)
        for filename in ("docs/install.md", "docs/installation.md"):
            self.assertIn("](update.md)", (ROOT / filename).read_text())
        guide = (ROOT / "docs/update.md").read_text()
        for term in ("exact commit", "stays pinned", "local edits", "symlinks",
                     "outside all host skill-discovery", "simulation mode",
                     "same reviewed source", "--reinstall", "rollback failure",
                     "target-only names", "concurrent user work",
                     "against the installed", "No API calls", "no-op"):
            self.assertIn(term, guide)
        setup = (ROOT / "skills/jev/references/setup.md").read_text()
        self.assertIn("/blob/main/docs/update.md", setup)

    def test_setup_and_all_skills_keep_explicit_modes(self):
        folders = list((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual({p.parent.name for p in folders}, {"jev", *SCENARIOS})
        for path in folders:
            text = path.read_text()
            for term in ("OPENROUTER_API_KEY", "TYPESAFE_API_KEY", "agent_simulation",
                         "model_simulation", "jev_called", "DeepSeek"):
                self.assertIn(term, text, str(path))
        self.assertTrue((ROOT / "skills/jev/references/simulation.md").is_file())

    def test_new_collection_covers_all_supplied_roundups(self):
        ledger = (ROOT / "skills/jev/references/intake-2026-09-21.md").read_text()
        rows = re.findall(r"^\| (\d+) \|", ledger, re.M)
        self.assertEqual(len(rows), 39 + 15 + 22)
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            section = text.split('<a id="projects"></a>', 1)[1].split('<a id="skills"></a>', 1)[0]
            self.assertEqual(len(re.findall(r"^\| [^|]+ \| \[", section, re.M)), 61)
            self.assertEqual(len(re.findall(r"^#### \d+\.", text, re.M)), 108)

    def test_overview_links_to_the_three_sections(self):
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            top = text.split('<a id="projects"></a>', 1)[0]
            for anchor in ('projects', 'skills', 'catalog'):
                self.assertIn(f"](#{anchor})", top)
                self.assertEqual(text.count(f'<a id="{anchor}"></a>'), 1)
            self.assertIn("docs/updates/README.md", top)

    def test_agent_first_installation_entrypoint(self):
        guide_url = "https://raw.githubusercontent.com/wuyoscar/jev-skill/main/docs/install.md"
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            first_block = re.search(r"```(\w*)\n(.*?)\n```", text, re.S)
            self.assertEqual(first_block.group(1), "text")
            self.assertIn(guide_url, first_block.group(2))
            self.assertLess(text.index(guide_url), text.index('id="agent"'))
        guide = (ROOT / "docs/install.md").read_text()
        for name in ("jev", *SCENARIOS):
            self.assertIn(f"`{name}`", guide)
        for requirement in ("OPENROUTER_API_KEY", "--dry-run", "v0.2.0"):
            self.assertIn(requirement, guide)

    def test_all_skills_teach_context_and_parallelism(self):
        for name in ("jev", *SCENARIOS):
            with self.subTest(skill=name):
                text = " ".join((ROOT / "skills" / name / "SKILL.md").read_text().lower().split())
                for requirement in ("context", "does not inherit", "independent",
                                    "bounded concurrency", "same request"):
                    self.assertIn(requirement, text)

    def test_readme_usage_explains_agent_prompts_and_manual_calls(self):
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            self.assertTrue('<a id="usage"></a>' in text, filename)
            usage = text.split('<a id="usage"></a>', 1)[1].split('<a id="context-tips"></a>', 1)[0]
            self.assertEqual(len(re.findall(r"```text\n", usage)), 5)
            self.assertIn("smoke_test=true", usage)
            for name in ("jev", *SCENARIOS):
                self.assertIn(f"`{name}`", usage)
            for command in ("jev-decide decide request.json --dry-run",
                            "jev-decide decide request.json > result.json"):
                self.assertIn(command, usage)
            for field in ("OPENROUTER_API_KEY", "state", "questions", "criteria",
                          "choice", "noul", "score"):
                self.assertIn(field, usage)

    def test_readme_input_can_be_saved_and_dry_run_as_documented(self):
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            match = re.search(r"<!-- request: .*? -->\s*```json\n(.*?)\n```", text, re.S)
            with tempfile.TemporaryDirectory() as tmp:
                request = Path(tmp) / "request.json"
                request.write_text(match.group(1))
                output = io.StringIO()
                with patch.dict("os.environ", {}, clear=True), \
                        patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
                        contextlib.redirect_stdout(output):
                    status = jev.main(["decide", str(request), "--dry-run"])
                self.assertEqual(status, 0)
                self.assertEqual(json.loads(output.getvalue()), json.loads(match.group(1)))

    def test_batch_example_scopes_each_independent_question(self):
        payload = json.loads((ROOT / "skills/jev/assets/batch-triage.json").read_text())
        jev.validate_request(payload)
        records = payload["state"]["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual(len(payload["questions"]), 6)
        for record_id, record in records.items():
            self.assertGreater(len(record["thread"]), 1)
            scoped = {key: value for key, value in payload["questions"].items()
                      if key.startswith(record_id + "_")}
            self.assertEqual({value["type"] for value in scoped.values()},
                             {"choice", "noul", "score"})
            for question in scoped.values():
                self.assertIn(f"state.records.{record_id}", question["instructions"])
                self.assertIn("state.policy", question["instructions"])

    def test_copied_general_skill_batch_example_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "jev"
            shutil.copytree(ROOT / "skills/jev", folder)
            output = io.StringIO()
            with patch.dict("os.environ", {}, clear=True), \
                    patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
                    contextlib.redirect_stdout(output):
                status = jev.main(["decide", str(folder / "assets/batch-triage.json"), "--dry-run"])
            self.assertEqual(status, 0)
            self.assertEqual(len(json.loads(output.getvalue())["questions"]), 6)
            self.assertTrue((folder / "references/context-and-throughput.md").is_file())

    def test_scenario_entrypoints_and_examples(self):
        for name in SCENARIOS:
            with self.subTest(skill=name):
                folder = ROOT / "skills" / name
                text = (folder / "SKILL.md").read_text()
                self.assertIn(f"name: {name}\n", text)
                self.assertIn("description:", text)
                self.assertIn("jev-decide", text)
                self.assertIn("OPENROUTER_API_KEY", text)
                self.assertIn("assets/example.json", text)
                payload = json.loads((folder / "assets/example.json").read_text())
                jev.validate_request(payload)

    def test_installed_scenarios_dry_run_without_sibling_skill(self):
        for name in SCENARIOS:
            with self.subTest(skill=name), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / name
                shutil.copytree(ROOT / "skills" / name, folder)
                output = io.StringIO()
                with patch.dict("os.environ", {}, clear=True), \
                        patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
                        contextlib.redirect_stdout(output):
                    status = jev.main(["decide", str(folder / "assets/example.json"), "--dry-run"])
                self.assertEqual(status, 0)
                self.assertIn("questions", output.getvalue())

    def test_readmes_expose_each_scenario(self):
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            for name in SCENARIOS:
                with self.subTest(readme=filename, skill=name):
                    self.assertIn(f"skills/{name}/SKILL.md", text)
                    self.assertIn(f"skills/{name}/assets/example.json", text)

    def test_readmes_cover_the_full_researched_catalog(self):
        references = ROOT / "skills/jev/references"
        recipe_ids = set()
        for filename in ("agent-recipes.md", "human-recipes.md"):
            recipe_ids.update(re.findall(r"\*\*([AH]\d{2}) ·", (references / filename).read_text()))
        pattern_ids = {
            f"M{int(number):02d}" for number in re.findall(
                r"^## (\d+)\.", (references / "implementation-patterns.md").read_text(), re.M
            )
        }
        social_ids = {f"X{number:02d}" for number in range(1, 8)}
        readmes = [(ROOT / name).read_text() for name in ("README.md", "README.zh.md")]
        for text in readmes:
            coverage = re.findall(r"<!-- covers: (.*?) -->", text)
            covered = set(" ".join(coverage).split())
            self.assertTrue(recipe_ids | pattern_ids | social_ids <= covered)
            anchors = re.findall(r'<a id="(sc-[^"]+)"', text)
            self.assertEqual(len(anchors), len(set(anchors)))
            self.assertEqual(len(anchors), len(coverage))
            self.assertEqual(len(anchors), len(re.findall(r"^#### \d+\.", text, re.M)))
        self.assertEqual(
            re.findall(r"<!-- covers: (.*?) -->", readmes[0]),
            re.findall(r"<!-- covers: (.*?) -->", readmes[1]),
        )

    def test_readme_counts_and_numbering_match_the_catalog(self):
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            numbers = [int(n) for n in re.findall(r"^#### (\d+)\.", text, re.M)]
            self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
            badge = re.search(r"/badge/scenarios-(\d+)-", text)
            self.assertEqual(int(badge.group(1)), len(numbers))
            skill_badge = re.search(r"/badge/skills-(\d+)-", text)
            self.assertEqual(int(skill_badge.group(1)), 5)
            counts = re.findall(r"<br />(\d+) (?:recipes|个用法)", text)
            self.assertEqual(len(counts), 10)
            self.assertEqual(sum(map(int, counts)), len(numbers))

    def test_showcase_has_attributed_previews_and_existing_local_media(self):
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            gallery = text.split('<a id="showcase"></a>', 1)[1].split(
                '<a id="install"></a>', 1
            )[0]
            previews = re.findall(r'<a href="https://[^"]+"><img src="([^"]+)"', gallery)
            self.assertEqual(len(previews), 6)
            for source in previews:
                if not source.startswith("https://"):
                    self.assertTrue((ROOT / source).is_file(), source)
            self.assertIn("docs/media/README.md", gallery)
            credits = (ROOT / "docs/media/README.md").read_text()
            for repo, revision in (
                ("devagrawal09/jev-review", "31f89602797fb7bea007f8a480bf368bf564954e"),
                ("davila7/jev-explained", "5cbe35e04609112be77b1bd447bd79b3bde7980b"),
            ):
                self.assertIn(f"{repo}/{revision}/", credits)
                self.assertIn(f"{repo}/tree/{revision}", credits)
            self.assertIn("docs/updates/2026-09-20.md", gallery)
        self.assertTrue((ROOT / "docs/media/README.md").is_file())
        self.assertTrue((ROOT / "docs/updates/2026-09-20.md").is_file())

    def test_daily_additions_are_visible_in_both_languages(self):
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            for number in range(1, 6):
                self.assertIn(f"<!-- covers: D{number:02d} -->", text)
            for anchor in ("sc-semantic-find", "sc-sponsor-skip", "sc-story-sensors",
                           "sc-midi", "sc-local-comparison"):
                self.assertIn(f'<a id="{anchor}"></a>', text)

    def test_readme_inputs_match_saved_requests_and_pair_with_outputs(self):
        expected = {}
        for filename in ("examples-2026-09-20.json", "scenario-smoke-2026-09-20.json"):
            receipt = json.loads((ROOT / "evals/results" / filename).read_text())
            for result in receipt["results"]:
                expected[f"{filename}#{result['example']}"] = result["request"]
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            shown = re.findall(
                r"<!-- request: (.*?) -->\s*```json\n(.*?)\n```", text, re.S
            )
            self.assertEqual(len(shown), len(expected))
            self.assertEqual({key for key, _ in shown}, set(expected))
            markers = re.findall(r"<!-- (request|receipt): (.*?) -->", text)
            self.assertEqual(len(markers), 2 * len(expected))
            for index in range(0, len(markers), 2):
                self.assertEqual(markers[index][0], "request")
                self.assertEqual(markers[index + 1], ("receipt", markers[index][1]))
            for key, payload in shown:
                with self.subTest(readme=filename, request=key):
                    self.assertEqual(json.loads(payload), expected[key])

    def test_readme_outputs_match_all_saved_example_receipts(self):
        expected = {}
        for filename in ("examples-2026-09-20.json", "scenario-smoke-2026-09-20.json"):
            receipt = json.loads((ROOT / "evals/results" / filename).read_text())
            for result in receipt["results"]:
                expected[f"{filename}#{result['example']}"] = {
                    question: {key: value for key, value in decision.items() if key != "levels"}
                    for question, decision in result["decisions"].items()
                }
        for filename in ("README.md", "README.zh.md"):
            text = (ROOT / filename).read_text()
            shown = re.findall(
                r"<!-- receipt: (.*?) -->\s*```json\n(.*?)\n```", text, re.S
            )
            self.assertEqual(len(shown), len(expected))
            self.assertEqual({key for key, _ in shown}, set(expected))
            for key, output in shown:
                with self.subTest(readme=filename, receipt=key):
                    self.assertEqual(json.loads(output), expected[key])


if __name__ == "__main__":
    unittest.main()
