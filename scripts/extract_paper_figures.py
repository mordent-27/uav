"""論文 PDF の図 1〜3 はベクタ図なので、描画データから数値を読み取る。

    python3 scripts/extract_paper_figures.py ../2609.40201v1.pdf --out-dir data

必要なもの: Python 標準ライブラリと poppler の `pdftocairo`。
出力: `paper_fig1_fig2.json`（領域・タスク・解の頂点・充電区間・時点数の推定・
再訪間条件の検査）と `paper_fig3.csv`（3 手法 × 900 点）。標準出力に要約を出す。

読み取り値は図の描画精度（位置で約 1e-3 km）に限られる。軸の目盛りの数値
（図1: -6, 0, 6 km、図2a: 0〜2 h と 0〜1、図3: 対数・線形の目盛り）は図の表示から
人が読んだ対応で、下の定数に固定している。
"""
import argparse
import collections
import json
import math
import re
import statistics
import subprocess
import tempfile
from pathlib import Path

V_D, V_C, KAPPA, ZETA = 36.0, 10.8, 4.625, 2.5  # 論文 IV-A の値（km, h）

NUM = r"(-?\d+(?:\.\d+)?)"


def svg_paths(pdf: Path, page: int):
    """ページ内の <path> を (属性の辞書, d 文字列) の列にする。文字のグリフ定義は除く。"""
    with tempfile.TemporaryDirectory() as tmp:
        svg = Path(tmp) / "page.svg"
        subprocess.run(["pdftocairo", "-svg", "-f", str(page), "-l", str(page), str(pdf), str(svg)],
                       check=True)
        text = svg.read_text()
    body = text[text.find("</defs>"):]
    out = []
    for tag in re.findall(r"<path[^>]*?/>", body):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        out.append((attrs, attrs.pop("d")))
    return out


def points(d: str):
    return [(float(a), float(b)) for a, b in re.findall(NUM + " " + NUM, d)]


def center(d: str):
    p = points(d)
    xs, ys = [q[0] for q in p], [q[1] for q in p]
    return ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2)


# ---------------------------------------------------------------- 図1

FIG1_T = "matrix(0.086, 0, 0, -0.086, 363.781, 210.065)"
FIG1_TICKS_KM = (-6.0, 0.0, 6.0)


def fig1(pdf: Path):
    paths = svg_paths(pdf, 6)
    local = [(a, d) for a, d in paths if a.get("transform") == FIG1_T]
    # 目盛り: 下枠から上へ伸びる短い縦線（3 本）と、左枠から右へ伸びる短い横線（3 本）。
    xt, yt = set(), set()
    for a, d in local:
        if a.get("stroke-width") != "4.99495" or d.count("L") != 1:
            continue
        (x0, y0), (x1, y1) = points(d)
        if x0 == x1 and 0 < y1 - y0 < 30:
            xt.add(x0)
        if y0 == y1 and 0 < x1 - x0 < 30:
            yt.add(y0)
    xt, yt = sorted(xt), sorted(yt)
    assert len(xt) == 3 and len(yt) == 3, (xt, yt)
    unit = (xt[2] - xt[0]) / (FIG1_TICKS_KM[2] - FIG1_TICKS_KM[0])
    assert abs(unit - (yt[2] - yt[0]) / 12.0) < 1e-6

    def km(x, y):
        return ((x - xt[1]) / unit, (y - yt[1]) / unit)

    def page_km(px, py):
        return km((px - 363.781) / 0.086, (210.065 - py) / 0.086)

    regions = []
    for a, d in paths:
        if a.get("fill", "").startswith("rgb(87.3"):
            for sub in d.split("M"):
                p = [page_km(*q) for q in points(sub)]
                if len(p) < 10:
                    continue
                cx = (max(q[0] for q in p) + min(q[0] for q in p)) / 2
                cy = (max(q[1] for q in p) + min(q[1] for q in p)) / 2
                r = statistics.mean(math.hypot(q[0] - cx, q[1] - cy) for q in p)
                regions.append({"o": [round(cx, 3), round(cy, 3)], "rho": round(r, 3)})
    legs = [[km(*q) for q in points(d)] for a, d in local
            if a.get("stroke") == "rgb(0%, 0%, 0%)" and a.get("stroke-width") == "9.9899"]
    tasks = []
    for a, d in local:
        if a.get("stroke") == "rgb(100%, 0%, 0%)":
            p = points(d)
            tasks.append(km(p[0][0], (p[0][1] + p[1][1]) / 2))
    vertices = [q for leg in legs for q in leg]
    return {
        "regions": regions,
        "tasks": [[round(v, 4) for v in t] for t in tasks],
        "r0": [round(v, 3) for v in vertices[0]],
        "rf": [round(v, 3) for v in vertices[-1]],
        # 黒の折れ線 5 本の頂点をつないだもの。折れ線の切れ目が充電区間。
        "flight_legs": [[[round(v, 4) for v in q] for q in leg] for leg in legs],
        "vertices": [[round(v, 4) for v in q] for q in vertices],
    }


# ---------------------------------------------------------------- 図2a

FIG2A_T = "matrix(1, 0, 0, -1, 85.186, 128.092)"


def fig2a(pdf: Path):
    paths = svg_paths(pdf, 7)
    local = [(a, d) for a, d in paths if a.get("transform") == FIG2A_T]
    frame = next(points(d) for a, d in local if a.get("stroke-width") == "0.3985" and "Z" in d)
    x0, x1 = min(p[0] for p in frame), max(p[0] for p in frame)
    y0 = min(p[1] for p in frame)
    curve = next(points(d) for a, d in local if a.get("stroke-width") == "1.19553")
    y_one = curve[0][1]  # 初期電池 1（式(11)）

    def hours(x):
        return (x - x0) / (x1 - x0) * 2.0

    def level(y):
        return (y - y0) / (y_one - y0)

    t = [hours(p[0]) for p in curve]
    e = [level(p[1]) for p in curve]
    # 灰色の帯（ページ座標）。図2a の縦範囲にあるものだけを取る。
    boxes = []
    for a, d in paths:
        if a.get("fill") == "rgb(50%, 50%, 50%)" and "transform" not in a:
            p = points(d)
            if max(q[1] for q in p) < 130:
                xs = [q[0] - 85.186 for q in p]
                boxes.append((hours(min(xs)), hours(max(xs))))
    boxes.sort()
    marks = sorted(hours(points(d)[0][0]) for a, d in local if a.get("stroke") == "rgb(100%, 0%, 0%)")
    return {"t": t, "e": e, "charge_boxes": boxes, "task_times": marks}


def infer_stamps(f2):
    """各行程（タスク訪問か充電の開始・終了で区切った区間）の描画点の間隔を調べる。

    曲線が時点ごとの区間を同じ点数で描いたものなら、区間の長さ / 点の間隔は一定になる。
    一つの行程が長さの違う複数の区間からなれば、行程の中で間隔が変わるはずである。
    """
    t = [x * 3600 for x in f2["t"]]
    dt = [b - a for a, b in zip(t, t[1:])]
    events = sorted({0.0, f2["t"][-1], *f2["task_times"], *(x for b in f2["charge_boxes"] for x in b)})
    rows = []
    for a, b in zip(events, events[1:]):
        inside = [x for i, x in enumerate(dt) if t[i] >= a * 3600 + 2 and t[i + 1] <= b * 3600 - 2]
        base = min(inside)
        # 描画時に一部の点が間引かれているので、最小間隔の整数倍として数える。
        unit = statistics.mean(x / max(1, round(x / base)) for x in inside)
        spread = max(abs(x / max(1, round(x / base)) - unit) for x in inside)
        rows.append({"start_h": round(a, 4), "end_h": round(b, 4), "spacing_s": round(unit, 3),
                     "spacing_spread_s": round(spread, 3),
                     "intervals_per_leg": round((b - a) * 3600 / unit, 2)})
    return rows


def check_paper_solution(f1, f2):
    """図1の頂点と図2aの時刻を組み合わせ、速度と再訪間条件 (R) を調べる。"""
    v = f1["vertices"]
    events = sorted({0.0, f2["t"][-1], *f2["task_times"], *(x for b in f2["charge_boxes"] for x in b)})
    assert len(events) == len(v), (len(events), len(v))
    charge_start = {round(b[0], 6) for b in f2["charge_boxes"]}
    legs, charges = [], []
    for k in range(len(v) - 1):
        dist = math.dist(v[k], v[k + 1])
        dur = events[k + 1] - events[k]
        charging = round(events[k], 6) in charge_start
        legs.append({"k": k + 1, "charging": charging, "dist_km": round(dist, 3),
                     "duration_h": round(dur, 4), "speed_kmh": round(dist / dur, 2)})
        if charging:
            region = min(range(len(f1["regions"])), key=lambda j: max(
                math.dist(v[k], f1["regions"][j]["o"]), math.dist(v[k + 1], f1["regions"][j]["o"])))
            charges.append({"k": k + 1, "region": region + 1, "t0": events[k], "t1": events[k + 1],
                            "from": v[k], "to": v[k + 1]})
    revisits = []
    for i, a in enumerate(charges):
        for b in charges[i + 1:]:
            if b["region"] == a["region"]:
                gap = b["t0"] - a["t1"]
                need = math.dist(a["to"], b["from"])
                revisits.append({"region": a["region"], "from_segment": a["k"], "to_segment": b["k"],
                                 "distance_km": round(need, 3), "gap_h": round(gap, 4),
                                 "carrier_reach_km": round(V_C * gap, 3),
                                 "satisfied": need <= V_C * gap})
                break
    return {"total_time_h": round(f2["t"][-1], 4), "final_battery": round(f2["e"][-1], 4),
            "legs": legs, "revisits": revisits}


# ---------------------------------------------------------------- 図3

FIG3_PANELS = {
    "132.583887": ("time_min", lambda y: 10 ** (y / 14.052)),
    "243.296568": ("objective_h", lambda y: 0.5 + (y - 6.348342) / 30.9143),
    "270.049273": ("violation", lambda y: 10 ** (-11 + (y + 77.464653) / 7.04233)),
}
FIG3_COLORS = {"rgb(100%, 0%, 0%)": "NLP", "rgb(0%, 44.699097%, 74.099731%)": "SCIP",
               "rgb(0%, 50%, 29.998779%)": "Juniper"}


def fig3(pdf: Path):
    data = collections.defaultdict(list)
    for a, d in svg_paths(pdf, 7):
        tr, st = a.get("transform", ""), a.get("stroke")
        if st not in FIG3_COLORS or a.get("fill") != st or d.count("C") < 4:
            continue
        panel = [k for k in FIG3_PANELS if k in tr]
        if not panel:
            continue
        name, f = FIG3_PANELS[panel[0]]
        x, y = map(float, re.match("M " + NUM + " " + NUM, d).groups())
        tau = int((x - 0.3476) // 20.218) + 1  # 0.3476 は丸印の半径、20.218 はタスク数の間隔
        data[(name, FIG3_COLORS[st], tau)].append(f(y))
    return data


def fig3_summary(data):
    med = statistics.median
    lines = []
    for name, fmt in (("time_min", "{:8.3f}"), ("objective_h", "{:8.3f}"), ("violation", "{:8.1e}")):
        lines.append(f"{name}: 中央値（タスク数 1〜9）")
        for m in ("NLP", "SCIP", "Juniper"):
            lines.append(f"  {m:8}" + "".join(fmt.format(med(data[(name, m, t)])) for t in range(1, 10)))
    lines.append("点数: " + ", ".join(
        f"{m} {sum(len(data[('objective_h', m, t)]) for t in range(1, 10))}" for m in ("NLP", "SCIP", "Juniper")))
    for m in ("NLP", "SCIP", "Juniper"):
        v = [x for t in range(1, 10) for x in data[("violation", m, t)]]
        lines.append(f"違反 {m:8} 1e-3 超 {sum(x > 1e-3 for x in v):3d}  1e-4 超 {sum(x > 1e-4 for x in v):3d}"
                     f"  最大 {max(v):.2e}  (全 {len(v)} 点)")
    lines.append("計算時間が 10 時間の上限（599 分以上）に達した点数（タスク数 1〜9）")
    for m in ("SCIP", "Juniper"):
        lines.append(f"  {m:8}" + "".join(f"{sum(x >= 599 for x in data[('time_min', m, t)]):5d}" for t in range(1, 10)))
    lines.append("NLP と SCIP の目的関数の中央値の比（対応のない分布どうしの比較）")
    lines.append("  " + "".join(
        f"{med(data[('objective_h', 'NLP', t)]) / med(data[('objective_h', 'SCIP', t)]):7.3f}" for t in range(1, 10)))
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("data"))
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    f1, f2 = fig1(args.pdf), fig2a(args.pdf)
    stamps = infer_stamps(f2)
    sol = check_paper_solution(f1, f2)
    out = {
        "source": "arXiv:2609.40201v1, Fig. 1 (p.6) and Fig. 2a (p.7), read from vector drawing data",
        "fig1": f1,
        "fig2a": {"charge_boxes_h": [[round(a, 4), round(b, 4)] for a, b in f2["charge_boxes"]],
                  "task_times_h": [round(x, 4) for x in f2["task_times"]],
                  "curve_points": len(f2["t"])},
        "stamp_inference": stamps,
        "paper_solution": sol,
    }
    (args.out_dir / "paper_fig1_fig2.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")

    data = fig3(args.pdf)
    with open(args.out_dir / "paper_fig3.csv", "w") as f:
        f.write("quantity,method,tau,value\n")
        for (name, m, tau), values in sorted(data.items()):
            for x in values:
                f.write(f"{name},{m},{tau},{x:.6g}\n")

    print("== 図1: 領域・端点")
    for r in f1["regions"]:
        print(f"  中心 {r['o']}  半径 {r['rho']}")
    print(f"  r0 {f1['r0']}  rf {f1['rf']}  タスク {len(f1['tasks'])} 個  解の頂点 {len(f1['vertices'])} 個")
    print("== 図2a: 行程ごとの描画点の間隔（区間長 / 間隔 が一定なら 1 行程 = 1 区間）")
    for s in stamps:
        print(f"  {s['start_h']:.4f}〜{s['end_h']:.4f} h  間隔 {s['spacing_s']:7.3f} s (±{s['spacing_spread_s']:.3f})"
              f"  区間長/間隔 {s['intervals_per_leg']:.2f}")
    ratios = [s["intervals_per_leg"] for s in stamps]
    print(f"  行程数 {len(stamps)}、比の範囲 {min(ratios):.2f}〜{max(ratios):.2f}"
          f" → 時点数の推定 N = {len(stamps) + 1}")
    print(f"== 論文の解: 総時間 {sol['total_time_h']} h、終了時の電池 {sol['final_battery']}")
    fly = [l["speed_kmh"] for l in sol["legs"] if not l["charging"]]
    chg = [l["speed_kmh"] for l in sol["legs"] if l["charging"]]
    print(f"  飛行区間の速さ {min(fly):.2f}〜{max(fly):.2f} km/h (上限 {V_D})、"
          f"充電区間 {min(chg):.2f}〜{max(chg):.2f} km/h (上限 {V_C})")
    for r in sol["revisits"]:
        print(f"  領域 {r['region']} の再訪: 区間 {r['from_segment']} の終点 → 区間 {r['to_segment']} の始点"
              f" {r['distance_km']} km、間隔 {r['gap_h']} h で車両は {r['carrier_reach_km']} km まで移動可"
              f" → 条件(R) {'成立' if r['satisfied'] else '不成立'}")
    print("== 図3")
    print("\n".join(fig3_summary(data)))


if __name__ == "__main__":
    main()
