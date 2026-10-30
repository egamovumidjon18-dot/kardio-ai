"""O'z-o'zini o'rgatish sikli: yangi tasdiqlangan holatlar → nomzod model → avtomatik darvozalar → (inson tasdig'i).

    python -m learning.cycle --db cardiopath.db --recordings <papka> --circor-dir <CirCor> [--force]

Sikl hech qachon modelni o'zi almashtirmaydi: u faqat NOMZOD yaratadi va hisobot yozadi. Almashtirish — faqat
`python -m learning.promote` orqali, ismi aniq ko'rsatilgan shifokor tasdiqlasa (darvozalardan o'tgan nomzodni).
Windows vazifalar rejalashtiruvchisi (Task Scheduler) bilan har kuni/haftada ishga tushirsa bo'ladi.

`run_cycle` tartibga soluvchi mantiq: dvigatel (o'qitish/baholash) tashqaridan beriladi, shuning uchun testlanadi.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Protocol

from core.evidence import utcnow
from core.store import EpisodeStore
from learning.dataset import label_of, split_children, usable
from learning.gates import CFG, dataset_gate, model_gate, paired_bootstrap_delta
from learning.versions import ModelVersions
from research.export_local import collect_children


class Engine(Protocol):
    def train(self, split: dict[str, list[dict]]) -> dict[str, Path]:
        """Nomzod fayllari: {'pcg.onnx': yo'l, 'pcg.pt': yo'l, 'model_card.json': yo'l}."""

    def evaluate(self, model_dir: Path, split: dict[str, list[dict]]) -> dict:
        """{'local': metrika, 'circor': metrika, 'rows_local': [{'id','murmur','p'}]} — platformadagi ishlov yo'li bilan."""

    def control(self, split: dict[str, list[dict]]) -> Optional[float]:
        """Mahalliy belgilari aralashtirilgan nomzodning mahalliy testdagi AUROC'i."""


def _known_ids(versions: ModelVersions) -> set[str]:
    listed = versions.list()
    return set(versions.report(listed[-1]["version"]).get("children_ids", [])) if listed else set()


def _paired(rows_new: list[dict], rows_old: list[dict]):
    old = {r["id"]: r for r in rows_old}
    y, s_new, s_old = [], [], []
    for r in rows_new:
        o = old.get(r["id"])
        if o and r["p"] is not None and o["p"] is not None and r["murmur"] in ("Present", "Absent"):
            y.append(int(r["murmur"] == "Present")); s_new.append(float(r["p"])); s_old.append(float(o["p"]))
    if not y or sum(y) in (0, len(y)):
        return 0.0, float("nan"), float("nan"), len(y)
    return (*paired_bootstrap_delta(y, s_new, s_old), len(y))


def run_cycle(store: EpisodeStore, recordings_dir: Path, versions: ModelVersions, champion_dir: Path, engine: Engine,
              force: bool = False, cfg: dict = CFG) -> dict:
    children, skipped = collect_children(store, recordings_dir)
    use = usable(children)
    known = _known_ids(versions)
    new = [c for c in use if c["eid"] not in known]
    result: dict = {"started_at": utcnow(), "n_confirmed": len(use), "n_new": len(new), "skipped": dict(skipped),
                    "champion": versions.current() or "baseline"}

    def done(status: str, **extra) -> dict:
        result.update(status=status, finished_at=utcnow(), **extra)
        (versions.root / "last_cycle.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
        return result

    ds = dataset_gate(children, cfg)
    result["dataset_gate"] = ds
    if len(new) < cfg["min_new"] and not force:
        return done("not_enough_new", message=f"yangi tasdiqlangan bola {len(new)} ta, kerak: {cfg['min_new']} (yoki --force)")
    if not ds["passed"]:
        return done("dataset_rejected", message="ma'lumot darvozasidan o'tmadi: o'qitish BOSHLANMADI",
                    failed=[g["name"] for g in ds["items"] if not g["passed"]])

    split = split_children(children)
    champ = engine.evaluate(champion_dir, split)
    files = engine.train(split)
    chall = engine.evaluate(files["model_card.json"].parent, split)
    d, lo, hi, n_pair = _paired(chall["rows_local"], champ["rows_local"])
    control = engine.control(split)
    gates = model_gate(champ, chall, (d, lo, hi), control, cfg)
    report = {"children_ids": sorted(c["eid"] for c in use), "split_counts": {k: len(v) for k, v in split.items()},
              "dataset_gate": ds, "champion_version": result["champion"], "champion": {k: champ[k] for k in ("local", "circor")},
              "challenger": {k: chall[k] for k in ("local", "circor")},
              "delta_local": {"delta": d, "lo": lo, "hi": hi, "n_paired": n_pair}, "control_auroc": control, "gates": gates,
              "config": cfg, "note": "Nomzod avtomatik JORIY BO'LMAYDI: faqat shifokor tasdig'i bilan (learning.promote)."}
    vid = versions.add_candidate(files, report)
    return done("candidate_ready" if gates["passed"] else "candidate_failed", version=vid, gates=gates)


def _print(res: dict, root: Path) -> None:
    print(f"yangi tasdiqlangan bolalar: {res['n_new']} (jami {res['n_confirmed']}); joriy model: {res['champion']}")
    for g in res.get("dataset_gate", {}).get("items", []):
        print(f"  [{'OK ' if g['passed'] else 'XATO'}] {g['name']}: {g['detail']}")
    print(f"\nNATIJA: {res['status']} {res.get('message', '')}")
    if res["status"] in ("candidate_ready", "candidate_failed"):
        for g in res["gates"]["items"]:
            print(f"  [{'OK ' if g['passed'] else 'XATO'}] {g['name']}: {g['detail']}")
        v = res["version"]
        if res["status"] == "candidate_ready":
            print(f"\nNomzod {v} barcha darvozalardan o'tdi, lekin AVTOMATIK ALMASHTIRILMADI. Tasdiqlash uchun:\n"
                  f"  python -m learning.promote --models-dir {root} --version {v} --approved-by \"Ismingiz\" --note \"sabab\"")
        else:
            print(f"\nNomzod {v} darvozalardan o'tmadi: tasdiqlab bo'lmaydi (hisobot: {root}/versions/{v}/report.json).")


def main() -> None:
    import warnings
    from core.store import SqliteEpisodeStore
    from learning.training import RealEngine
    from learning.versions import resolve_weights_dir

    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--recordings", type=Path, required=True)
    ap.add_argument("--circor-dir", type=Path, required=True)
    ap.add_argument("--models-dir", type=Path, default=Path("models/pcg"))
    ap.add_argument("--baseline-dir", type=Path, default=Path("weights/pcg"))
    ap.add_argument("--circor-split", type=Path, default=Path("weights/pcg/split.json"))
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--force", action="store_true", help="yangi bolalar soni yetmasa ham ishga tushirish")
    args = ap.parse_args()

    versions = ModelVersions(args.models_dir)
    champion_dir, label = resolve_weights_dir(args.baseline_dir, args.models_dir)
    engine = RealEngine(args.circor_dir, champion_dir, args.models_dir / "work", args.circor_split, epochs=args.epochs)
    res = run_cycle(SqliteEpisodeStore(args.db), args.recordings, versions, champion_dir, engine, force=args.force)
    _print(res, args.models_dir)


if __name__ == "__main__":
    main()
