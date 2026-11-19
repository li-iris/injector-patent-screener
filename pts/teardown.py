"""竞品重构：从专利说明书里自动还原产品结构。

专利说明书为了充分公开，会给每个零件编号（如「旋钮130」「护针罩（2）」），并描述装配关系和工作过程。
本模块只读正文（附图标记说明那一段单独拿出来当「标准答案」用于评测），输出：
  1. 零件清单：编号 → 名称（按编号聚合所有出现位置，取最长公共后缀，自动去掉「所述」「上述」等前缀）
  2. 装配关系：同一句里出现两个零件 + 关系动词（套设 / 卡接 / 啮合 / 抵接 / 带动 ...）
  3. 动作时序：具体实施方式里描述工作过程的句子，按出现顺序
  4. 对标维度：驱动方式、剂量方式、提示方式、防护方式、发明目的
"""
import json, re, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CJK = r"一-龥"
PREFIX = re.compile(r"^(所述|上述|该|此|其|各|两个|两|一个|第[一二三四五六七八九十]+(?=[" + CJK + "]{2}))+")
REFSEC = re.compile(r"附图标记(说明|的含义为|含义)[：:]")
REL = ["内套于", "外套于", "套设于", "套设", "套接", "穿过", "卡接", "卡合", "卡扣", "啮合", "抵接", "相抵", "抵靠", "螺纹连接", "连接", "固定于", "固定", "铰接", "带动", "驱动", "推动", "锁定", "限位"]
ACT = re.compile(r"按压|按下|旋转|转动|释放|推动|弹出|伸出|缩回|锁定|解锁|触发|注射|穿刺|复位|储能|拧|发出|移动")
SEQ = re.compile(r"^(首先|然后|接着|随后|此时|之后|最后|当|在注射|使用时|注射时|注射完成|调节剂量时|按压)")
STOPNAME = re.compile(r"^(图|为图|如图|参见|步骤|实施例|方向|位置|角度|距离|时间|例如|约|大约)")


def split_ref_section(desc):
    m = REFSEC.search(desc)
    if not m: return desc, ""
    end = desc.find("\n具体实施方式", m.end())
    end = end if end > 0 else m.end() + 3000
    return desc[:m.start()] + desc[end:], desc[m.end():end]


def gold_parts(ref):
    """附图标记说明 → {编号: 名称}。两种写法：「护针罩2，」或「2-护针罩、」"""
    out = {}
    for name, num in re.findall(r"([" + CJK + r"]{1,12})(\d{1,5}[a-z]?)(?=[，,；;。\s])", ref):
        out[num] = name
    for num, name in re.findall(r"(\d{1,5}[a-z]?)-([" + CJK + r"]{1,12})", ref):
        out[num] = name
    return out


def extract_parts(text):
    """正文里「名称+编号」出现多次时，取同一编号前面字符的最长公共后缀。"""
    occ = collections.defaultdict(list)
    for m in re.finditer(r"([" + CJK + r"]{1,14})\s*[（(]?(\d{1,5}[a-z]?)[）)]?(?![\d.%])", text):
        num = m.group(2)
        if len(num) > 1 and num.startswith("0"): continue
        occ[num].append(m.group(1))
    parts = {}
    for num, names in occ.items():
        if len(names) < 2 and len(num) < 2: continue
        best = ""
        for L in range(2, 13):
            sufs = collections.Counter(n[-L:] for n in names if len(n) >= L)
            if not sufs: break
            s, c = sufs.most_common(1)[0]
            if c / len(names) >= 0.6: best = s
            else: break
        if "的" in best: best = best.rsplit("的", 1)[1]        # 「有一个或多个向内指向的脊」→「脊」（太短会被下面过滤掉）
        name = PREFIX.sub("", best)
        if len(name) >= 2 and not STOPNAME.match(name) and not re.search(r"[的了是在为与和或及]$", name):
            parts[num] = name
    return parts


def relations(text, parts):
    names = sorted(set(parts.values()), key=len, reverse=True)
    out = []
    for s in re.split(r"[。；]", text):
        s = re.sub(r"\s", "", s)
        found = []
        for n in names:
            i = s.find(n)
            if i >= 0 and not any(n in f for _, f in found): found.append((i, n))
        if len(found) < 2: continue
        rel = next((r for r in REL if r in s), None)
        if not rel: continue
        found.sort()
        out.append(dict(a=found[0][1], rel=rel, b=found[1][1], sent=s[:160]))
    seen, uniq = set(), []
    for r in out:
        k = (r["a"], r["rel"], r["b"])
        if k not in seen: seen.add(k); uniq.append(r)
    return uniq


def sequence(text, parts, n=10):
    body = text[text.find("具体实施方式"):] if "具体实施方式" in text else text
    names = set(parts.values())
    out = []
    for s in re.split(r"(?<=[。])", body):
        s = re.sub(r"\s", "", s)
        if 15 < len(s) < 220 and ACT.search(s) and (SEQ.search(s) or "时，" in s[:30]) and sum(1 for x in names if x in s) >= 1:
            out.append(s)
    return out[:n]


def profile(t, title=""):
    def has(*ws): return any(w in t for w in ws)
    drive = "扭簧" if has("扭簧", "扭转弹簧") else "压缩弹簧" if has("驱动弹簧", "驱动弹性件", "压缩弹簧", "弹簧") else "电机" if has("电机", "马达") else "手动推注"
    # 先看标题（最可靠），再看正文关键词
    if "预定" in title and "剂量" in title: dose = "多个预定剂量"
    elif "可调" in title or "剂量调节" in title: dose = "可调剂量"
    elif "自动注射器" in title: dose = "固定单剂量"
    else: dose = "可调剂量" if has("剂量拨盘", "剂量调节", "调节剂量", "剂量设定") else "固定单剂量"
    cue = "、".join(x for x, ws in [("声音提示", ("咔嗒", "响筒", "声音", "提示音")), ("视窗显示", ("显示窗口", "观察窗", "刻度", "视窗")), ("电子显示", ("电子显示", "显示器"))] if has(*ws)) or "未提及"
    guard = "、".join(x for x, ws in [("护针罩", ("护针罩", "针罩", "针护套")), ("注射后锁定", ("锁定",)), ("防止过量", ("剂量限制", "防止过量", "最大剂量"))] if has(*ws)) or "未提及"
    m = re.search(r"(本申请|本发明|本公开)?的?目的(是|在于)[^。]{5,120}。", t)
    return dict(drive=drive, dose=dose, cue=cue, guard=guard, goal=re.sub(r"\s", "", m.group(0)) if m else "")


def main():
    raw = json.load(open(ROOT / "data/raw/teardown.json", encoding="utf-8"))
    res, ev = [], []
    for pid, p in raw["td"].items():
        body, ref = split_ref_section(p["desc"])
        parts = extract_parts(body)
        gold = gold_parts(ref) if ref else {}
        rec = dict(id=pid, title=p["title"].split(" - ")[1].strip(), assignee=p["assignee"], parts=parts,
                   relations=relations(body, parts), sequence=sequence(body, parts), profile=profile(p["desc"] + p["claims"], p["title"]),
                   url=f"https://patents.google.com/patent/{pid}/zh")
        if gold:
            tp = sum(1 for k, v in parts.items() if gold.get(k) and (gold[k] == v or gold[k].endswith(v) or v.endswith(gold[k])))
            rec["eval"] = dict(gold=len(gold), found=len(parts), correct=tp,
                               recall=round(tp / len(gold), 3), precision=round(tp / max(1, len(parts)), 3),
                               missed=[f"{k}{v}" for k, v in gold.items() if k not in parts][:15],
                               wrong=[f"{k}:{v}≠{gold[k]}" for k, v in parts.items() if k in gold and not (gold[k] == v or gold[k].endswith(v) or v.endswith(gold[k]))][:10])
            ev.append(rec["eval"] | {"id": pid})
        res.append(rec)
    out = ROOT / "results"; out.mkdir(exist_ok=True)
    json.dump(dict(products=res, eval=ev), open(out / "teardown.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return res, ev


if __name__ == "__main__":
    res, ev = main()
    for r in res:
        print(r["id"], r["title"][:16], "零件", len(r["parts"]), "关系", len(r["relations"]), "时序", len(r["sequence"]), r["profile"]["drive"], r["profile"]["dose"])
    for e in ev: print("EVAL", e["id"], {k: e[k] for k in ("gold", "found", "correct", "recall", "precision")}, e["missed"][:8], e["wrong"][:5])
