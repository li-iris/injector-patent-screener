import json, unittest
from pathlib import Path
from pts.parse import claims_of, features
from pts.screen import judge_feature, screen, DESIGNS

ROOT = Path(__file__).resolve().parents[1]
P = json.load(open(ROOT / "data/clean/patents.json", encoding="utf-8"))


class TestParse(unittest.TestCase):
    def test_independent_detection(self):
        cl = claims_of("Claims (3)\n1.一种自动注射器，包括：壳体；驱动弹簧。\n2.根据权利要求1所述的自动注射器，其特征在于，还包括护针罩。\n3.一种注射方法，包括：按压。")
        self.assertEqual([c["independent"] for c in cl], [True, False, True])

    def test_feature_split(self):
        subj, fs = features("一种自动注射器，包括：壳体；驱动弹簧，用于推动推杆；其特征在于，还包括护针罩，所述护针罩注射后锁定。")
        self.assertEqual(len(fs), 3)

    def test_every_patent_has_independent_claim(self):
        self.assertTrue(all(p["independent"] for p in P))


class TestJudge(unittest.TestCase):
    A = DESIGNS["A"]

    def test_absent_concept_excludes(self):
        s, cs, _ = judge_feature("电机驱动机构，用于推动柱塞杆", set(self.A["has"]), set(self.A["not_"]))
        self.assertEqual(s, "不具备")

    def test_unknown_mechanism_needs_review(self):
        s, cs, _ = judge_feature("阻尼器机构可操作地联接至驱动组件", set(self.A["has"]), set(self.A["not_"]))
        self.assertEqual(s, "待确认")

    def test_all_present(self):
        s, cs, _ = judge_feature("驱动弹簧推动推杆", set(self.A["has"]), set(self.A["not_"]))
        self.assertEqual(s, "具备")

    def test_method_claims_never_high(self):
        for r in screen(P, self.A):
            for c in r["claims"]:
                if c["method"]: self.assertEqual(c["level"], "中")

    def test_formulations_marked_irrelevant(self):
        ids = {r["id"] for r in screen(P, self.A) if r["level"] == "不相关"}
        self.assertIn("CN110709062B", ids)


if __name__ == "__main__":
    unittest.main()
