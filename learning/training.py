"""Haqiqiy o'qitish dvigateli: joriy modeldan davom ettirib (fine-tuning) CirCor + mahalliy ma'lumotda nomzod o'qitadi.

Unutib qo'ymaslik uchun CirCor ham aralashtiriladi (har bir manba ichida sinflar teng vaznlanadi — research.train_multisite.fit).
Baholash platformaning haqiqiy yo'li (PCGModel, ONNX, abstain) orqali, joriy va nomzod uchun bir xil bolalarda.
"""
from __future__ import annotations

import json
import random
import time
import warnings
from pathlib import Path
from typing import Optional

import numpy as np

from learning.dataset import label_of, to_patients
from screening.features import N_MELS


class RealEngine:
    def __init__(self, circor_dir: Path, champion_dir: Path, work_dir: Path, circor_split: Path = Path("weights/pcg/split.json"),
                 epochs: int = 15, lr: float = 3e-4, seed: int = 42, device: Optional[str] = None) -> None:
        import torch

        self.circor_dir, self.champion_dir, self.work_dir = Path(circor_dir), Path(champion_dir), Path(work_dir)
        self.circor_split, self.epochs, self.lr, self.seed = Path(circor_split), epochs, lr, seed
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self._c = None
        self.work_dir.mkdir(parents=True, exist_ok=True)

    # ---- ma'lumot
    def _circor(self):
        if self._c is None:
            from research.train_multisite import load_circor
            self._c = load_circor(self.circor_dir, self.circor_split)
        return self._c

    def _local_items(self, children: list[dict]) -> list[dict]:
        from research.train_pcg import IGNORE, featurize

        items = featurize(to_patients(children))
        for it in items:
            it["site"], it["outcome"] = 1, IGNORE
        return items

    def _labels(self, split: dict) -> dict:
        _, c_labels, _ = self._circor()
        return {**c_labels, **{c["eid"]: label_of(c["dx"]) for part in split.values() for c in part}}

    def _init_state(self):
        import torch

        pt = self.champion_dir / "pcg.pt"
        return torch.load(pt, map_location=self.device) if pt.exists() else None

    # ---- o'qitish
    def _fit(self, split: dict, shuffle_local: bool = False, epochs: Optional[int] = None):
        from research.train_multisite import fit

        c_items, _, _ = self._circor()
        train_local = [dict(c) for c in split["train"]]
        if shuffle_local:                                   # salbiy nazorat: mahalliy belgilarni aralashtirish
            labs = [label_of(c["dx"]) for c in train_local]
            random.Random(self.seed).shuffle(labs)
            for c, lab in zip(train_local, labs):
                c["dx"] = "VSD" if lab else "NORMAL"
        tr = c_items["train"] + self._local_items(train_local)
        va = c_items["val"] + self._local_items(split["val"])
        labels = {**self._labels(split), **{c["eid"]: label_of(c["dx"]) for c in split["val"]}}
        if shuffle_local:
            labels.update({c["eid"]: label_of(c["dx"]) for c in train_local})
        model, best = fit(tr, va, labels, self.device, epochs or self.epochs, self.seed, lr=self.lr,
                          init_state=self._init_state(), log=lambda m: None)
        return model, best, va, labels

    def train(self, split: dict[str, list[dict]]) -> dict[str, Path]:
        import torch
        from research.train_pcg import choose_thresholds, patient_scores

        model, best, va, labels = self._fit(split)
        sc = patient_scores(model, va, self.device)
        ids = [p for p in sc if labels.get(p) is not None]
        low, high = choose_thresholds(np.array([labels[p] for p in ids]), np.array([sc[p]["p_murmur"] for p in ids]), 0.95, 0.90)
        out = self.work_dir / time.strftime("cand-%Y%m%d-%H%M%S")
        out.mkdir(parents=True)
        model.eval().cpu()
        torch.save(model.state_dict(), out / "pcg.pt")
        t_frames = va[0]["x"].shape[-1]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            torch.onnx.export(model, torch.zeros(1, 1, N_MELS, t_frames), out / "pcg.onnx", input_names=["logmel"],
                              output_names=["murmur_logits", "outcome_logits"],
                              dynamic_axes={"logmel": {0: "n"}, "murmur_logits": {0: "n"}, "outcome_logits": {0: "n"}},
                              opset_version=17, dynamo=False)
        card = {"name": "pcg_murmur_cnn", "version": time.strftime("%Y.%m.%d-%H%M"),
                "task": "pediatrik PCG: shovqin / yurak nuqsoni — CirCor + mahalliy ma'lumotda davom ettirib o'qitilgan",
                "dataset": "CirCor DigiScope + mahalliy ma'lumot", "weights": "pcg.onnx",
                "thresholds": {"murmur_low": low, "murmur_high": high, "window_agreement": 0.6, "min_age_days": 29},
                "metrics": {"val_auroc_mean_sites": best},
                "training": {"seed": self.seed, "epochs": self.epochs, "lr": self.lr, "fine_tuned_from_champion": (self.champion_dir / "pcg.pt").exists(),
                             "n_local_train": len(split["train"]), "n_local_val": len(split["val"])}}
        (out / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
        return {n: out / n for n in ("pcg.onnx", "pcg.pt", "model_card.json")}

    # ---- baholash (platformaning haqiqiy yo'li)
    def evaluate(self, model_dir: Path, split: dict[str, list[dict]]) -> dict:
        from research.evaluate_pcg import metrics, run
        from research.train_pcg import read_patients
        from screening.model import PCGModel

        model = PCGModel.from_dir(model_dir)
        if model is None:
            raise RuntimeError(f"{model_dir}: model_card.json topilmadi")
        test_ids = set(json.loads(self.circor_split.read_text(encoding="utf-8"))["test"])
        circor_test = [p for p in read_patients(self.circor_dir) if p["id"] in test_ids]
        rows_local = run(model, to_patients(split["test"]))
        return {"local": metrics(rows_local), "circor": metrics(run(model, circor_test)),
                "rows_local": [{"id": r["id"], "murmur": r["murmur"], "p": r["p"]} for r in rows_local]}

    def control(self, split: dict[str, list[dict]]) -> Optional[float]:
        from research.train_pcg import auroc, patient_scores

        model, _, _, labels = self._fit(split, shuffle_local=True, epochs=max(3, self.epochs // 2))
        test = self._local_items(split["test"])
        sc = patient_scores(model, test, self.device)
        ids = [p for p in sc if labels.get(p) is not None]
        a = auroc(np.array([labels[p] for p in ids]), np.array([sc[p]["p_murmur"] for p in ids]))
        return None if a != a else float(a)
