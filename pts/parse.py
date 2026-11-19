"""解析专利页面文本：标题、申请人、申请日、独立权利要求，并把独立权利要求拆成技术特征。"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DEP = re.compile(r"(根据|如|按照)?权利要求\s*\d+")


def claims_of(text):
    parts = re.split(r"\n(?=\d{1,3}[\.．、]\s*\S)", text)
    out = []
    for x in parts:
        m = re.match(r"(\d{1,3})[\.．、]\s*", x)
        if not m: continue
        body = re.sub(r"\s*\n\s*", "", x[m.end():]).strip()
        out.append(dict(no=int(m.group(1)), text=body, independent=not DEP.search(body[:60])))
    return out


def features(claim):
    """独立权利要求 → 技术特征。前序部分按「，包括：」后的分号切；特征部分按「其特征在于」后的分号切。"""
    t = claim
    pre, _, char = t.partition("其特征在于")
    head = re.split(r"[，,]?\s*(包括|包含|具有)[：:]?", pre, maxsplit=1)
    subject = head[0][:40]
    rest = (head[2] if len(head) > 2 else "") + ("；" + char if char else "")
    feats = [f.strip("，,。；;：: ") for f in re.split(r"[；;]", rest)]
    feats = [f for f in feats if len(f) >= 2]   # 「壳体」这类两字特征也是技术特征，不能丢
    return subject, [dict(i=i + 1, text=f, part="特征部分" if char and f in char else "前序部分") for i, f in enumerate(feats)]


def main():
    raw = json.load(open(ROOT / "data/raw/patents.json", encoding="utf-8"))
    out = []
    for pid, p in raw.items():
        m = p["meta"]
        a = re.search(r"Current Assignee\s*(.+)", m)
        f = re.search(r"Application filed by[^\n]*\n(\d{4}-\d{2}-\d{2})", m)
        cl = claims_of(p["claims"])
        ind = [c for c in cl if c["independent"]]
        for c in ind:
            c["subject"], c["features"] = features(c["text"])
        out.append(dict(id=pid, title=p["title"].split(" - ")[1].strip(), assignee=a.group(1).strip() if a else "", filed=f.group(1) if f else "",
                        abstract=re.sub(r"\s+", "", p["abstract"].replace("Abstract", "", 1))[:400], n_claims=len(cl), independent=ind,
                        url=f"https://patents.google.com/patent/{pid}/zh"))
    p = ROOT / "data/clean/patents.json"; p.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return out


if __name__ == "__main__":
    for x in main(): print(x["id"], x["title"][:16], len(x["independent"]), [len(c["features"]) for c in x["independent"]])
