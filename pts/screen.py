"""专利初筛：把独立权利要求拆成技术特征，与「产品技术方案」逐项比对，按全面覆盖原则给出初筛等级。

注意：这是研发阶段的初筛工具，目的是让工程师尽早知道该重点看哪几件专利、哪几个特征；
结论必须由专利工程师 / 律师复核，不构成侵权判断或法律意见。

比对方法
1. 概念词典：注射器领域约 40 个技术概念（驱动弹簧、护针罩、电机、处理单元、无线通信……），每个概念有多种写法；
2. 每个技术特征抽出它涉及的概念；
3. 产品方案对每个概念标注「有 / 无 / 未定」；
4. 特征判定：涉及的概念产品都有 → 具备；有一个产品明确没有 → 不具备；其余 → 待确认；
5. 专利判定（全面覆盖原则）：任一特征不具备 → 低；全部具备 → 高（重点复核）；其余 → 中（有待确认特征）。
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONCEPTS = {
    "壳体": r"壳体|外壳|主体|机壳|本体",
    "注射器/针筒": r"注射器|针筒|预灌封|药筒|容器|储液",
    "针头": r"针头|注射针|针管|穿刺",
    "弹簧驱动": r"弹簧|弹性件|驱动弹|蓄能",
    "电机驱动": r"电机|马达|电动",
    "推杆/柱塞杆": r"推杆|柱塞杆|活塞杆|丝杆|螺杆|推进",
    "护针罩": r"护针罩|针罩|针头护套|防护罩|护罩|针护套|套管",
    "锁定": r"锁定|锁止|锁住|卡锁|锁闭",
    "触发/释放": r"触发|释放|启动|按钮|按压",
    "听觉提示": r"响筒|声音|咔嗒|提示音|发声|听觉|音频",
    "视觉指示": r"视窗|窗口|指示件|指示器|可视|显示",
    "剂量设定": r"剂量设定|设定剂量|剂量选择|调节剂量|剂量调节|旋钮|可调",
    "多剂量": r"多剂量|多次注射|可重复使用|重复使用",
    "处理单元": r"处理单元|处理器|控制器|控制单元|微控制|电路",
    "传感器": r"传感器|感应|检测器|编码器|霍尔|磁|光学",
    "无线通信": r"无线|蓝牙|通信模块|NFC|发射",
    "电池/电源": r"电池|电源|供电",
    "混合/双腔": r"混合|子室|双腔|两腔|冻干",
    "温度控制": r"温度|冷却|加热|冷藏",
    "倾注/姿态检测": r"倾|倒置|姿态|方向|重力",
    "卡扣/卡接": r"卡扣|卡夹|卡接|卡爪|卡合|弹性臂|弹臂",
    "贴片/穿戴": r"贴片|粘贴|皮肤贴|佩戴|穿戴",
    "制剂成分": r"抗体|蛋白质|制剂|赋形剂|缓冲|浓度|mg/mL|粘度降低",
    # 具体机构：示例方案默认「未定」，出现即进入待确认，避免只凭「壳体、针头」等通用词就判成全部具备
    "阻尼机构": r"阻尼",
    "扭簧/扭矩": r"扭簧|扭矩|扭转",
    "齿轮/齿条": r"齿轮|齿条|齿圈",
    "凸轮/导轨": r"凸轮|导轨|导槽|螺旋槽|斜面",
    "螺纹": r"螺纹",
    "棘轮/离合": r"棘轮|棘爪|离合",
    "阀/泵": r"阀|泵",
}
_RX = {k: re.compile(v) for k, v in CONCEPTS.items()}

DESIGNS = {
    "A": dict(name="方案 A：一次性弹簧驱动自动注射器（示例）",
              desc="1 mL 预灌封注射器；护针罩按压触发、注射后护针罩锁定；驱动弹簧推动推杆；注射开始与结束有咔嗒声，视窗变色指示完成；固定剂量、不可调；无电子元件。",
              has=["壳体", "注射器/针筒", "针头", "弹簧驱动", "推杆/柱塞杆", "护针罩", "锁定", "触发/释放", "听觉提示", "视觉指示", "卡扣/卡接"],
              not_=["电机驱动", "剂量设定", "多剂量", "处理单元", "传感器", "无线通信", "电池/电源", "混合/双腔", "温度控制", "倾注/姿态检测", "贴片/穿戴", "制剂成分"]),
    "B": dict(name="方案 B：胰岛素笔用智能注射记录模块（示例）",
              desc="套在可重复使用胰岛素笔尾部；磁传感器检测剂量旋钮转动，处理器记录剂量与时间，蓝牙同步到手机；纽扣电池供电；不改变注射笔本身的驱动结构。",
              has=["壳体", "传感器", "处理单元", "无线通信", "电池/电源", "剂量设定", "多剂量", "视觉指示"],
              not_=["弹簧驱动", "电机驱动", "护针罩", "混合/双腔", "温度控制", "贴片/穿戴", "制剂成分", "倾注/姿态检测"]),
}
NON_DEVICE = re.compile(r"制剂|抗体|蛋白质|冷却器|组合物")


def concepts_of(text):
    return [k for k, rx in _RX.items() if rx.search(text)]


def judge_feature(feat, has, not_):
    cs = concepts_of(feat)
    if not cs: return "待确认", cs, "没有识别出技术概念，需人工阅读"
    miss = [c for c in cs if c in not_]
    if miss: return "不具备", cs, "产品方案没有：" + "、".join(miss)
    unk = [c for c in cs if c not in has]
    if unk: return "待确认", cs, "方案里未说明：" + "、".join(unk)
    return "具备", cs, "涉及的概念方案都有"


def screen(patents, design):
    has, not_ = set(design["has"]), set(design["not_"])
    out = []
    for p in patents:
        if NON_DEVICE.search(p["title"]):
            out.append(dict(id=p["id"], level="不相关", reason="药物制剂 / 储运设备，不是注射器械结构专利", claims=[])); continue
        rows, levels = [], []
        for c in p["independent"]:
            fs = [dict(f, status=s, concepts=cs, why=w) for f in c["features"] for s, cs, w in [judge_feature(f["text"], has, not_)]]
            if "方法" in c["subject"]: lv = "中"          # 方法权利要求比对的是制造 / 使用过程，不能只看产品结构
            elif any(f["status"] == "不具备" for f in fs): lv = "低"
            elif fs and all(f["status"] == "具备" for f in fs): lv = "高"
            else: lv = "中"
            levels.append(lv); rows.append(dict(no=c["no"], subject=c["subject"], level=lv, method="方法" in c["subject"], features=fs))
        order = {"高": 0, "中": 1, "低": 2}
        best = min(levels, key=lambda x: order[x]) if levels else "中"
        out.append(dict(id=p["id"], level=best, claims=rows,
                        reason={"高": "某项独立权利要求的全部特征方案都具备，需重点复核", "中": "有待确认的特征，需工程师补充方案信息",
                                "低": "每项独立权利要求都至少有一个特征方案不具备"}[best]))
    return out


def main():
    P = json.load(open(ROOT / "data/clean/patents.json", encoding="utf-8"))
    res = {k: screen(P, d) for k, d in DESIGNS.items()}
    p = ROOT / "results"; p.mkdir(exist_ok=True)
    json.dump(res, open(p / "screening.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return res


if __name__ == "__main__":
    import collections
    res = main()
    P = {p["id"]: p for p in json.load(open(ROOT / "data/clean/patents.json", encoding="utf-8"))}
    for k, rows in res.items():
        print(k, dict(collections.Counter(r["level"] for r in rows)))
        for r in rows:
            if r["level"] in ("高", "中"): print("  ", r["level"], r["id"], P[r["id"]]["title"][:20], [c["level"] for c in r["claims"]])
