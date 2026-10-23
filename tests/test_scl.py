"""Engine tests for the SCL constraints."""

import json
import tempfile
import unittest
from pathlib import Path

from scl.framework import classify_path, release_eligible
from scl.gap import potential_model_gap
from scl.gates import implemented_ids
from scl.interpreter import Boundary, failures
from scl.model import Loaded, load_model, structural_findings
from scl.questions import influence_findings
from scl.skills import verify_skills
from scl.slice import inferred_node, integrate_slice, propose_slice

ROOT = Path(__file__).resolve().parents[1]


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

    def test_recommendation_must_name_a_hot_question(self):
        questions = [{"ID": "OQ-001", "Risk Level": "High", "Status": "open"}]
        bad = influence_findings("Recommendation: ship it. This depends on an open question.", questions)
        self.assertTrue(bad)
        good = influence_findings(
            "Recommendation: wait. This depends on OQ-001 (Risk Level High). Results may change once resolved.",
            questions,
        )
        self.assertEqual(good, [])

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
        import subprocess
        import sys

        env = dict(**{**dict(__import__("os").environ), "PYTHONPATH": str(ROOT / "src" / "tooling")})
        completed = subprocess.run([sys.executable, "-m", "scl", "validate", "--strict"], cwd=ROOT, check=False, capture_output=True, text=True, env=env)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("VALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
