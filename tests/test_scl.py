"""Engine tests for the SCL constraints."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "tooling"))

from scl.export import generated_findings
from scl.framework import classify_path, digest_bytes, framework_findings, release_eligible
from scl.gap import potential_model_gap
from scl.gates import implemented_ids
from scl.interpreter import Boundary, failures
from scl.model import Loaded, _evidence_finding, contained_path, load_model, structural_findings
from scl.narrative import mermaid_sequence, render_role
from scl.questions import influence_findings
from scl.skills import verify_skills
from scl.slice import inferred_node, integrate_slice, proposal_findings, propose_slice


def rel(kind, source, target):
    return {
        "id": f"{source}-{kind}-{target}",
        "type": kind,
        "from": source,
        "to": target,
        "rationale": "This link is long enough to satisfy the rationale floor.",
    }


def mini_model():
    nodes = [
        {"id": "intent-a", "type": "Intent", "name": "A", "description": "Why the work exists.", "status": "planned", "metadata": {"basis": "stated"}},
        {"id": "outcome-a", "type": "Outcome", "name": "A", "description": "An observable change.", "status": "planned", "metadata": {"basis": "stated", "measure": "a count of 1"}},
        {"id": "model-a", "type": "Model", "name": "A", "description": "The interaction.", "status": "planned", "interaction": ["system-system"], "metadata": {"basis": "stated"}},
        {"id": "requirement-a", "type": "Requirement", "name": "A", "description": "The system shall record one reason.", "status": "planned", "metadata": {"basis": "stated", "acceptance": "Given 1, when checked, then 1 reason exists."}},
        {"id": "system-a", "type": "System", "name": "A", "description": "First system.", "metadata": {"basis": "stated"}},
        {"id": "system-b", "type": "System", "name": "B", "description": "Second system.", "metadata": {"basis": "stated"}},
        {"id": "project-a", "type": "Project", "name": "A", "description": "The project.", "metadata": {"basis": "stated"}},
    ]
    relationships = [
        rel("delivers", "outcome-a", "intent-a"),
        rel("serves", "model-a", "outcome-a"),
        rel("specifies", "requirement-a", "model-a"),
        rel("involves", "model-a", "system-a"),
        rel("involves", "model-a", "system-b"),
        rel("belongs_to", "intent-a", "project-a"),
    ]
    return Loaded(root=ROOT, nodes=nodes, relationships=relationships)


class StructuralTests(unittest.TestCase):
    def test_mini_chain_is_clean(self):
        self.assertEqual(structural_findings(mini_model()), [])

    def test_short_rationale_is_flagged(self):
        loaded = mini_model()
        loaded.relationships[0]["rationale"] = "too short"
        rules = {finding.rule for finding in structural_findings(loaded)}
        self.assertIn("rel.rationale", rules)

    def test_illegal_relationship_is_flagged(self):
        loaded = mini_model()
        loaded.relationships.append(rel("delivers", "requirement-a", "intent-a"))
        rules = {finding.rule for finding in structural_findings(loaded)}
        self.assertIn("rel.legality", rules)

    def test_deep_refines_and_vector_are_flagged(self):
        loaded = mini_model()
        for record_id, measure in (
            ("outcome-b", "check"),
            ("outcome-c", "vector"),
            ("outcome-d", "check"),
        ):
            loaded.nodes.append({
                "id": record_id,
                "type": "Outcome",
                "name": record_id,
                "description": "Another outcome.",
                "status": "planned",
                "metadata": {"basis": "stated", "measure": measure, "measurement": measure if measure == "vector" else "check"},
            })
            loaded.relationships.append(rel("delivers", record_id, "intent-a"))
            loaded.relationships.append(rel("serves", "model-a", record_id))
        loaded.relationships.append(rel("refines", "outcome-b", "outcome-a"))
        loaded.relationships.append(rel("refines", "outcome-d", "outcome-b"))
        loaded.relationships.append(rel("refines", "outcome-c", "outcome-a"))
        rules = [finding.rule for finding in structural_findings(loaded)]
        self.assertGreaterEqual(rules.count("refines.discipline"), 2)

    def test_missing_intent_link_is_flagged(self):
        loaded = mini_model()
        loaded.relationships = [item for item in loaded.relationships if item["type"] != "delivers"]
        rules = {finding.rule for finding in structural_findings(loaded)}
        self.assertIn("trace.reach-intent", rules)


class RuleTests(unittest.TestCase):
    def test_eligibility(self):
        self.assertEqual(classify_path("src/schemas/project-manifest.schema.json"), "consumer")
        self.assertEqual(classify_path("meta/open-questions.md"), "internal")
        self.assertTrue(release_eligible(["src/prompts/mode-1.md"]))
        self.assertFalse(release_eligible(["changelog/CHANGELOG.md", "meta/open-questions.md"]))
        self.assertFalse(release_eligible(["tests/test_scl.py"]))

    def test_unfamiliar_solution_passes_and_a_violation_fails(self):
        boundary = Boundary("requirement-no-expressiveness-penalty", "breaks_shall", True)
        self.assertEqual(failures({"novel_route": "new"}, [boundary]), [])
        self.assertEqual(failures({"novel_route": "new", "breaks_shall": True}, [boundary]), ["requirement-no-expressiveness-penalty"])

    def test_gap_challenge_does_not_look_like_a_record(self):
        text = potential_model_gap("obs", "concern", "possibilities", "question")
        self.assertIn("POTENTIAL MODEL GAP", text)
        self.assertNotIn('"type"', text)

    def test_recommendation_names_only_an_unresolved_hot_question(self):
        questions = [{"ID": "OQ-001", "Risk Level": "High", "Status": "open"}]
        unnamed = influence_findings("Recommendation: ship it. This depends on an open question.", questions)
        self.assertEqual(unnamed, [])
        named = influence_findings("Recommendation: ship it. This cites OQ-001.", questions)
        self.assertEqual([item.record_id for item in named], ["OQ-001"])
        good = influence_findings(
            "Recommendation: wait. This depends on OQ-001 (Risk Level High). Results may change once resolved.",
            questions,
        )
        self.assertEqual(good, [])
        resolved = influence_findings(
            "Recommendation: ship it. OQ-001 is cited.",
            [{"ID": "OQ-001", "Risk Level": "High", "Status": "resolved"}],
        )
        self.assertEqual(resolved, [])
        closed = influence_findings(
            "Recommendation: ship it. OQ-001 is cited.",
            [{"ID": "OQ-001", "Risk Level": "Critical", "Status": "closed"}],
        )
        self.assertEqual(closed, [])
        plain = influence_findings("Recommendation: this depends on Python 3.11.", [])
        self.assertEqual(plain, [])
        both = influence_findings(
            "Recommendation: see OQ-001 and OQ-009.",
            [
                {"ID": "OQ-001", "Risk Level": "High", "Status": "open"},
                {"ID": "OQ-009", "Risk Level": "Critical", "Status": "open"},
            ],
        )
        self.assertEqual({item.record_id for item in both}, {"OQ-001", "OQ-009"})

    def test_missing_critical_skill_halts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "meta").mkdir()
            (root / "meta" / "required-skills.md").write_text(
                "\n".join([
                    "## skill-intent-modelling",
                    "- ID: skill-intent-modelling",
                    "- Name: intent-modelling",
                    "- Purpose: cannot check the model",
                    "- Criticality: critical",
                    "- Verification: file:.kiro/skills/intent-modelling/SKILL.md",
                    "",
                ]),
                encoding="utf-8",
            )
            findings, halt = verify_skills(root)
            self.assertTrue(halt)
            self.assertIn("FAIL", findings[0].message)
            self.assertIn("intent-modelling", findings[0].message)

    def test_slice_stays_out_of_the_layer_until_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "meta" / "iomr-model"
            (model / "nodes").mkdir(parents=True)
            (model / "relationships").mkdir(parents=True)
            (root / "imk.json").write_text(json.dumps({"model": "meta/iomr-model"}), encoding="utf-8")
            records = model / "nodes" / "records.json"
            links = model / "relationships" / "links.json"
            records.write_text("[]\n", encoding="utf-8")
            links.write_text("[]\n", encoding="utf-8")
            node = inferred_node("requirement-new", "Requirement", "New", "A proposed rule.", "Inferred from the request.", "demo")
            propose_slice(root, "demo", [node], [])
            self.assertEqual(json.loads(records.read_text()), [])
            self.assertTrue((model / "nodes" / "slice-demo.json").is_file())
            integrate_slice(root, "demo")
            integrated = json.loads(records.read_text())
            self.assertEqual(integrated[0]["status"], "proposed")
            self.assertNotIn("slice", integrated[0]["metadata"])
            self.assertFalse((model / "nodes" / "slice-demo.json").exists())


class RepositoryTests(unittest.TestCase):
    def test_implemented_requirements_are_enforced_and_planned_are_not(self):
        loaded = load_model(ROOT)
        enforced = implemented_ids()
        implemented = {node["id"] for node in loaded.nodes if node["type"] == "Requirement" and node["status"] == "implemented"}
        planned = {node["id"] for node in loaded.nodes if node["type"] == "Requirement" and node["status"] == "planned"}
        self.assertEqual(implemented, enforced)
        self.assertTrue(planned.isdisjoint(enforced))

    def test_framework_script_reports_valid(self):
        import subprocess
        import sys

        completed = subprocess.run([sys.executable, str(ROOT / "validate-framework.py")], cwd=ROOT, check=False, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("VALID", completed.stdout)
        self.assertIn("errors: 0", completed.stdout)

    def test_strict_validate_reports_valid(self):
        completed = _run(["validate", "--strict"])
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("VALID", completed.stdout)
        self.assertIn("errors: 0", completed.stdout)


def _run(args):
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [str(ROOT / "imk"), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _outcome(record_id):
    return {
        "id": record_id,
        "type": "Outcome",
        "name": record_id,
        "description": "Another outcome.",
        "status": "planned",
        "metadata": {"basis": "stated", "measure": "a count of 1"},
    }


class ReviewTests(unittest.TestCase):
    def test_refines_depth_walks_every_parent(self):
        def flagged(order):
            loaded = mini_model()
            for record_id in ("outcome-b", "outcome-c"):
                loaded.nodes.append(_outcome(record_id))
                loaded.relationships.append(rel("delivers", record_id, "intent-a"))
                loaded.relationships.append(rel("serves", "model-a", record_id))
            for source, target in order:
                loaded.relationships.append(rel("refines", source, target))
            return {
                finding.record_id
                for finding in structural_findings(loaded)
                if finding.rule == "refines.discipline"
            }

        chain = [
            ("outcome-b", "outcome-a"),
            ("outcome-c", "outcome-b"),
            ("outcome-c", "outcome-a"),
        ]
        self.assertIn("outcome-c", flagged(chain))
        self.assertIn("outcome-c", flagged(list(reversed(chain))))

        shallow = mini_model()
        for record_id in ("outcome-b", "outcome-c"):
            shallow.nodes.append(_outcome(record_id))
            shallow.relationships.append(rel("delivers", record_id, "intent-a"))
            shallow.relationships.append(rel("serves", "model-a", record_id))
        shallow.relationships.append(rel("refines", "outcome-c", "outcome-a"))
        shallow.relationships.append(rel("refines", "outcome-c", "outcome-b"))
        deep = [finding for finding in structural_findings(shallow) if finding.rule == "refines.discipline"]
        self.assertEqual(deep, [])

    def test_refines_cycle_and_cross_type(self):
        loaded = mini_model()
        loaded.nodes.append(_outcome("outcome-b"))
        loaded.relationships.append(rel("delivers", "outcome-b", "intent-a"))
        loaded.relationships.append(rel("serves", "model-a", "outcome-b"))
        loaded.relationships.append(rel("refines", "outcome-b", "outcome-a"))
        loaded.relationships.append(rel("refines", "outcome-a", "outcome-b"))
        flagged = {
            finding.record_id
            for finding in structural_findings(loaded)
            if finding.rule == "refines.discipline"
        }
        self.assertIn("outcome-a", flagged)
        self.assertIn("outcome-b", flagged)

        crossed = mini_model()
        crossed.relationships.append(rel("refines", "requirement-a", "outcome-a"))
        rules = {finding.rule for finding in structural_findings(crossed)}
        self.assertIn("rel.legality", rules)

    def test_malformed_records_are_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "meta" / "iomr-model").mkdir(parents=True)
            (root / "imk.json").write_text(
                json.dumps({"metamodel": "nonexistent-metamodel", "metamodelVersion": "999.0.0"}),
                encoding="utf-8",
            )
            (root / "meta" / "iomr-model" / "metamodel.json").write_text(
                json.dumps({"name": "nonexistent-metamodel", "version": "999.0.0"}),
                encoding="utf-8",
            )
            loaded = mini_model()
            loaded.root = root
            rules = {finding.rule for finding in structural_findings(loaded)}
            self.assertIn("metamodel.identity", rules)

        telepathy = mini_model()
        for node in telepathy.nodes:
            if node["id"] == "model-a":
                node["interaction"] = ["telepathy"]
        self.assertIn("model.participants", {finding.rule for finding in structural_findings(telepathy)})

        blank = mini_model()
        for node in blank.nodes:
            if node["id"] == "requirement-a":
                node["metadata"]["acceptance"] = "  "
        self.assertIn("record.acceptance", {finding.rule for finding in structural_findings(blank)})

        nameless = mini_model()
        nameless.nodes.append({"type": "Requirement", "name": "Nameless"})
        findings = structural_findings(nameless)
        self.assertTrue(any(finding.rule == "record.shape" and "missing id" in finding.message for finding in findings))

    def test_evidence_paths_stay_inside_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            nested = root / "docs" / "nested"
            nested.mkdir(parents=True)
            (nested / "inside.txt").write_text("hello anchor\n", encoding="utf-8")
            outside = base / "outside.txt"
            outside.write_text("secret\n", encoding="utf-8")
            (root / "docs" / "escape.txt").symlink_to(outside)
            self.assertIsNotNone(contained_path(root, "docs/nested/inside.txt"))
            self.assertIsNone(contained_path(root, "docs/../../outside.txt"))
            self.assertIsNone(contained_path(root, "docs/escape.txt"))
            inside = {"spec": {"alias": "spec", "path": "docs/nested/inside.txt"}}
            self.assertIsNone(
                _evidence_finding(root, inside, "spec:docs/nested/inside.txt#hello anchor", "requirement-a")
            )
            linked = {"spec": {"alias": "spec", "path": "docs/escape.txt"}}
            escaped = _evidence_finding(root, linked, "spec:docs/escape.txt#secret", "requirement-a")
            self.assertEqual(escaped.rule, "context.external")
            parent = {"spec": {"alias": "spec", "path": "docs/../../outside.txt"}}
            climbed = _evidence_finding(root, parent, "spec:docs/../../outside.txt#secret", "requirement-a")
            self.assertEqual(climbed.rule, "context.external")

    def test_proposal_files_are_checked_without_merging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "meta" / "iomr-model"
            (model / "nodes").mkdir(parents=True)
            (model / "relationships").mkdir()
            (root / "imk.json").write_text(json.dumps({"model": "meta/iomr-model"}), encoding="utf-8")
            records = model / "nodes" / "records.json"
            records.write_text("[]\n", encoding="utf-8")
            (model / "relationships" / "links.json").write_text("[]\n", encoding="utf-8")
            bad = inferred_node("requirement-new", "Requirement", "New", "A proposed rule.", "   ", "bad")
            bad["type"] = "Widget"
            propose_slice(
                root,
                "bad",
                [bad],
                [rel("specifies", "requirement-new", "model-missing")],
            )
            findings = proposal_findings(root)
            self.assertTrue(any(item.rule == "slice.inference" and item.record_id == "requirement-new" for item in findings))
            self.assertTrue(any("unknown type" in item.message and "slice-bad.json" in item.message for item in findings))
            self.assertTrue(any(item.rule == "slice.endpoint" for item in findings))
            self.assertEqual(json.loads(records.read_text(encoding="utf-8")), [])
            self.assertNotIn("requirement-new", {node.get("id") for node in load_model(root).nodes})
            for stale in (model / "nodes" / "slice-bad.json", model / "relationships" / "slice-bad.json"):
                stale.unlink()

            valid_model = inferred_node("model-new", "Model", "New", "A proposed interaction.", "Inferred from the request text.", "demo")
            valid_req = inferred_node("requirement-new", "Requirement", "New", "A proposed rule.", "Inferred from the request text.", "demo")
            propose_slice(
                root,
                "demo",
                [valid_model, valid_req],
                [rel("specifies", "requirement-new", "model-new")],
            )
            self.assertEqual(proposal_findings(root), [])
            self.assertNotIn("model-new", {node.get("id") for node in load_model(root).nodes})
            included = load_model(root, include_slices=True)
            included_ids = {node.get("id") for node in included.nodes}
            self.assertIn("model-new", included_ids)
            self.assertIn("requirement-new", included_ids)
            self.assertIn("model-new", mermaid_sequence(included, "model-new"))
            with self.assertRaises(SystemExit):
                mermaid_sequence(load_model(root), "model-new")

    def test_discovery_failure_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            draft = root / "docs" / "REQUIREMENTS-developer.md"
            draft.write_text("untouched\n", encoding="utf-8")
            out = Path(tmp) / "out.md"
            completed = _run(["--root", str(root), "export", "markdown", "-o", str(out)])
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertIn("skill discovery failed", completed.stdout)
            self.assertNotIn("critical skill missing", completed.stdout)
            self.assertFalse(out.exists())
            self.assertEqual(draft.read_text(encoding="utf-8"), "untouched\n")
            plain = _run(["--root", str(root), "validate"])
            exported = _run(["--root", str(root), "export", "json", "-o", str(out)])
            self.assertEqual(plain.returncode, 2)
            self.assertEqual(exported.returncode, 2)
            self.assertIn("skill discovery failed", plain.stdout)
            self.assertFalse(out.exists())
            (root / "meta").mkdir()
            (root / "meta" / "required-skills.md").write_text("not a skill entry\n", encoding="utf-8")
            malformed = _run(["--root", str(root), "export", "markdown", "-o", str(out)])
            self.assertEqual(malformed.returncode, 2)
            self.assertIn("skill discovery failed", malformed.stdout)
            self.assertNotIn("critical skill missing", malformed.stdout)
            self.assertFalse(out.exists())
            gap = _run(
                [
                    "--root",
                    str(root),
                    "gap",
                    "--observation",
                    "obs",
                    "--concern",
                    "concern",
                    "--possibilities",
                    "possibilities",
                    "--question",
                    "question",
                ]
            )
            self.assertEqual(gap.returncode, 0, gap.stderr)
            self.assertIn("POTENTIAL MODEL GAP", gap.stdout)

    def test_export_writes_only_the_requested_destination(self):
        paths = [
            ROOT / "TRACEABILITY.md",
            ROOT / "docs" / "REQUIREMENTS-developer.md",
            ROOT / "docs" / "REQUIREMENTS-tester.md",
            ROOT / "docs" / "REQUIREMENTS-power-user.md",
        ]
        before = {path: path.read_bytes() for path in paths}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "TRACEABILITY.md"
                role_out = Path(tmp) / "tester.md"
                exported = _run(["export", "markdown", "-o", str(out)])
                self.assertEqual(exported.returncode, 0, exported.stderr)
                printed = _run(["export", "markdown"])
                self.assertEqual(printed.returncode, 0, printed.stderr)
                self.assertEqual(printed.stdout, out.read_text(encoding="utf-8"))
                role = _run(["export", "narrative", "--role", "tester", "-o", str(role_out)])
                self.assertEqual(role.returncode, 0, role.stderr)
                self.assertIn("**Reader:** tester.", role_out.read_text(encoding="utf-8"))
                self.assertEqual({path: path.read_bytes() for path in paths}, before)
                touched = ROOT / "TRACEABILITY.md"
                touched.write_text(before[touched].decode() + "\nedited\n", encoding="utf-8")
                self.assertTrue(generated_findings(ROOT, load_model(ROOT)))
                regenerated = _run(["regenerate"])
                self.assertEqual(regenerated.returncode, 0, regenerated.stdout + regenerated.stderr)
                self.assertEqual(touched.read_bytes(), before[touched])
                self.assertEqual(generated_findings(ROOT, load_model(ROOT)), [])
        finally:
            for path, data in before.items():
                path.write_bytes(data)

    def test_narrative_keeps_status_gaps_and_refined_requirements(self):
        developer, _appendix = render_role(load_model(ROOT), "developer")
        self.assertIn("Model status: partial.", developer)
        self.assertIn(
            "Known gap: The boundary check is implemented. There is no full execution runtime, and the vector threshold in OQ-001 is unresolved.",
            developer,
        )

        loaded = Loaded(root=ROOT, nodes=[], relationships=[])
        loaded.nodes.extend(
            [
                {
                    "id": "intent-a",
                    "type": "Intent",
                    "name": "A",
                    "description": "Why.",
                    "status": "planned",
                    "metadata": {"basis": "stated"},
                },
                {
                    "id": "outcome-a",
                    "type": "Outcome",
                    "name": "A",
                    "description": "What changed.",
                    "status": "planned",
                    "metadata": {"basis": "stated", "measure": "a count of 1", "evaluation": "automated"},
                },
                {
                    "id": "model-big",
                    "type": "Model",
                    "name": "Big",
                    "description": "Nine constraints live here.",
                    "status": "implemented",
                    "metadata": {"basis": "stated", "order": 1},
                },
                {
                    "id": "model-other",
                    "type": "Model",
                    "name": "Other",
                    "description": "The specifying child stays on its own model.",
                    "status": "implemented",
                    "metadata": {"basis": "stated", "order": 2},
                },
            ]
        )
        def add_requirement(record_id, acceptance):
            loaded.nodes.append(
                {
                    "id": record_id,
                    "type": "Requirement",
                    "name": record_id,
                    "description": f"The system shall keep {record_id}.",
                    "status": "implemented",
                    "metadata": {"basis": "stated", "acceptance": acceptance, "category": "functional"},
                }
            )

        for index in range(9):
            add_requirement(f"requirement-n{index}", f"Given {index}, when read, then {index} is present.")
            loaded.relationships.append(rel("specifies", f"requirement-n{index}", "model-big"))
        add_requirement("requirement-parent", "Given parent, when read, then it specifies the model.")
        add_requirement("requirement-child", "Given child, when read, then it refines the parent.")
        add_requirement("requirement-owned", "Given owned, when read, then it specifies its own model.")
        loaded.relationships.extend(
            [
                rel("specifies", "requirement-parent", "model-big"),
                rel("refines", "requirement-child", "requirement-parent"),
                rel("specifies", "requirement-owned", "model-other"),
                rel("refines", "requirement-owned", "requirement-parent"),
            ]
        )
        main, appendix = render_role(loaded, "developer")
        self.assertIsNotNone(appendix)
        self.assertIn("`model-big` is implemented", main)
        self.assertIn("`model-big` is implemented", appendix)
        self.assertNotIn("planned verification", main + appendix)
        self.assertIn("`requirement-child`", appendix)
        self.assertNotIn("`requirement-child`", main)
        self.assertIn("`requirement-owned`", main)
        self.assertNotIn("`requirement-owned`", appendix)
        tester_main, tester_appendix = render_role(loaded, "tester")
        self.assertIn("`requirement-child`", tester_appendix)
        self.assertNotIn("`requirement-owned`", tester_appendix)

    def test_release_snapshot_is_independent_of_later_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _seed_release_root(Path(tmp))
            original = b"old\n"
            (root / "src" / "schemas" / "project-manifest.schema.json").write_bytes(original)
            first = _write_release(root, "0.1.0", {"src/schemas/project-manifest.schema.json": original})
            (root / "src" / "schemas" / "project-manifest.schema.json").write_bytes(b"new\n")
            self.assertEqual(framework_findings(root), [])
            second_files = {
                "src/schemas/project-manifest.schema.json": b"new\n",
                "src/framework/consume.py": b"print('consume')\n",
            }
            second = _write_release(
                root,
                "0.2.0",
                second_files,
                upgrade_from="v0.1.0",
                checklist="Run python3 iomr-kit/src/framework/consume.py manifest example.json\n",
            )
            self.assertEqual(framework_findings(root), [])
            changed = first / "iomr-kit" / "src" / "schemas" / "project-manifest.schema.json"
            changed.write_bytes(b"corrupted\n")
            self.assertTrue(
                any(
                    finding.record_id == "v0.1.0" and "differs from the release snapshot" in finding.message
                    for finding in framework_findings(root)
                )
            )
            changed.write_bytes(original)
            (second / "iomr-kit" / "src" / "framework" / "consume.py").write_bytes(b"nope\n")
            self.assertTrue(
                any(
                    finding.record_id == "v0.2.0" and "differs from the release snapshot" in finding.message
                    for finding in framework_findings(root)
                )
            )
            (second / "iomr-kit" / "src" / "framework" / "consume.py").write_bytes(second_files["src/framework/consume.py"])
            digest = (first / "iomr-kit" / "MANIFEST.sha256").read_text(encoding="utf-8")
            (first / "iomr-kit" / "unlisted.py").write_text("extra\n", encoding="utf-8")
            extra = framework_findings(root)
            self.assertTrue(any("unlisted.py" in finding.message and finding.record_id == "v0.1.0" for finding in extra))
            self.assertEqual((first / "iomr-kit" / "MANIFEST.sha256").read_text(encoding="utf-8"), digest)

    def test_consumer_impact_no_and_internal_changes_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _seed_release_root(Path(tmp))
            _write_release(root, "0.1.0", {"src/schemas/project-manifest.schema.json": b"{}\n"}, impact="NO")
            messages = [finding.message for finding in framework_findings(root)]
            self.assertTrue(any("no first-release exception" in message for message in messages))

        with tempfile.TemporaryDirectory() as tmp:
            root = _seed_release_root(Path(tmp))
            _write_release(
                root,
                "0.1.0",
                {"src/schemas/project-manifest.schema.json": b"{}\n"},
                difference="too short",
            )
            self.assertTrue(
                any("at least 20 characters" in finding.message for finding in framework_findings(root))
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = _seed_release_root(Path(tmp))
            (root / "meta" / "notes.md").write_text("internal\n", encoding="utf-8")
            _write_release(
                root,
                "0.1.0",
                {"src/schemas/project-manifest.schema.json": b"{}\n"},
                changes=["meta/notes.md"],
            )
            self.assertTrue(
                any(finding.rule == "framework.release-eligibility" for finding in framework_findings(root))
            )

    def test_copied_release_validates_without_the_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "v0.2.0"
            shutil.copytree(ROOT / "releases" / "v0.2.0", dest)
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            for args in (
                ["manifest", "iomr-kit/src/examples/project-manifest.json"],
                ["model", "iomr-kit/src/examples/consumer-model.json"],
            ):
                completed = subprocess.run(
                    [sys.executable, "iomr-kit/src/framework/consume.py", *args],
                    cwd=dest,
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertIn("VALID", completed.stdout)
            invalid = dest / "invalid.json"
            invalid.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {"id": "requirement-x", "type": "Requirement", "metadata": {}},
                            {"id": "model-x", "type": "Model", "interaction": ["telepathy"]},
                        ],
                        "relationships": [],
                    }
                ),
                encoding="utf-8",
            )
            rejected = subprocess.run(
                [sys.executable, "iomr-kit/src/framework/consume.py", "model", str(invalid)],
                cwd=dest,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(rejected.returncode, 1, rejected.stdout)
            self.assertIn("metadata.acceptance", rejected.stdout)
            self.assertIn("telepathy", rejected.stdout)

    def test_strict_validate_reads_real_proposal_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "repo"
            shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
            records = dest / "meta" / "iomr-model" / "nodes" / "records.json"
            before = records.read_bytes()
            node = inferred_node("requirement-new", "Requirement", "New", "A proposed rule.", "   ", "bad")
            propose_slice(dest, "bad", [node], [])
            completed = _run(["--root", str(dest), "validate", "--strict"])
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertIn("slice.inference", completed.stdout)
            self.assertIn("requirement-new", completed.stdout)
            self.assertIn("slice-bad.json", completed.stdout)
            self.assertEqual(records.read_bytes(), before)
            loaded_ids = {item.get("id") for item in load_model(dest).nodes}
            self.assertNotIn("requirement-new", loaded_ids)
            sliced_ids = {item.get("id") for item in load_model(dest, include_slices=True).nodes}
            self.assertIn("requirement-new", sliced_ids)


def _seed_release_root(root: Path) -> Path:
    for relative in ("src/framework", "src/schemas", "releases", "meta/iomr-model", "changelog", "docs"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    (root / "iomr-manifest.json").write_text("{}\n", encoding="utf-8")
    (root / "validate-framework.py").write_text("print('VALID')\n", encoding="utf-8")
    (root / "src" / "framework" / "kit-files.txt").write_text("src/schemas/project-manifest.schema.json\n", encoding="utf-8")
    (root / "src" / "schemas" / "project-manifest.schema.json").write_text("{}\n", encoding="utf-8")
    (root / "docs" / "install.md").write_text("install\n", encoding="utf-8")
    return root


def _write_release(root, version, files, impact="YES", difference="A project can validate an IOMR model today.", changes=None, checklist="Run the checks.\n", upgrade_from=None):
    folder = root / "releases" / f"v{version}"
    kit = folder / "iomr-kit"
    folder.mkdir(parents=True)
    (folder / "iomr-manifest.json").write_text(json.dumps({"version": version}) + "\n", encoding="utf-8")
    (folder / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (folder / "VALIDATION_CHECKLIST.md").write_text(checklist, encoding="utf-8")
    lines = [
        "1. Meta-model is a release candidate.",
        "2. Downstream artifacts were generated from the model.",
        "3. AI-test passed",
        "imk validate --strict",
        "validate-framework.py",
        "Green light: tester",
        f"Consumer impact: {impact}",
    ]
    if impact == "YES":
        lines.append(f"Behavioural difference: {difference}")
    (folder / "RELEASE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    change_list = ["src/schemas/project-manifest.schema.json"] if changes is None else changes
    (folder / "changes.txt").write_text("\n".join(change_list) + "\n", encoding="utf-8")
    if upgrade_from:
        (folder / f"UPGRADE_FROM_{upgrade_from}.md").write_text("Copy the new folder and read this note.\n", encoding="utf-8")
    pairs = []
    for relative, data in files.items():
        dest = kit / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        pairs.append((relative, data))
    snapshot = {"files": {relative: hashlib.sha256(data).hexdigest() for relative, data in pairs}}
    (folder / "source-snapshot.json").write_text(json.dumps(snapshot) + "\n", encoding="utf-8")
    (kit / "MANIFEST.sha256").write_text(digest_bytes(pairs) + "\n", encoding="utf-8")
    return folder


if __name__ == "__main__":
    unittest.main()
