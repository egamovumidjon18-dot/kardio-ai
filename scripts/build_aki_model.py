"""DIQQAT: bu skript SINTETIK (generator) ma'lumotda o'qitadi. Natijadagi model faqat muhandislik
sinovi uchun; dastur uni klinik ishga yuklamaydi (core.registry.refuse_synthetic)."""
from core.registry import SYNTHETIC_DATASET
"""MIMIC-IV va Cleveland Clinic klinik xavf omillari asosida
Kardioxirurgiyadan keyingi o'tkir buyrak zararlanishi (CSA-AKI, KDIGO)
bashorat modelini o'qitish va ONNX ga eksport qilish.

Xususiyatlar (12 ta):
0: female
1: congestive_heart_failure
2: lvef_percent
3: preop_iabp
4: copd
5: insulin_diabetes
6: previous_cardiac_surgery
7: emergency
8: creatinine_umol_l
9: surgery_valve
10: surgery_cabg_valve
11: surgery_other
"""
import json
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn


class AKINet(nn.Module):
    def __init__(self, mean: torch.Tensor, std: torch.Tensor):
        super().__init__()
        self.register_buffer("mean", mean)
        self.register_buffer("std", std)
        self.net = nn.Sequential(
            nn.Linear(12, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_norm = (x - self.mean) / (self.std + 1e-6)
        return self.net(x_norm)


def generate_cohort(n_samples: int = 10000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)

    female = rng.binomial(1, 0.32, n_samples).astype(np.float32)
    chf = rng.binomial(1, 0.22, n_samples).astype(np.float32)
    lvef = rng.normal(52.0, 12.0, n_samples).clip(15.0, 75.0).astype(np.float32)
    iabp = rng.binomial(1, 0.05, n_samples).astype(np.float32)
    copd = rng.binomial(1, 0.18, n_samples).astype(np.float32)
    diabetes = rng.binomial(1, 0.25, n_samples).astype(np.float32)
    prior_surg = rng.binomial(1, 0.12, n_samples).astype(np.float32)
    emergency = rng.binomial(1, 0.08, n_samples).astype(np.float32)

    creat = np.exp(rng.normal(np.log(88.0), 0.42, n_samples)).clip(45.0, 500.0).astype(np.float32)

    surg_type = rng.choice([0, 1, 2, 3], size=n_samples, p=[0.55, 0.25, 0.12, 0.08])
    surg_valve = (surg_type == 1).astype(np.float32)
    surg_cabg_valve = (surg_type == 2).astype(np.float32)
    surg_other = (surg_type == 3).astype(np.float32)

    X = np.column_stack([
        female, chf, lvef, iabp, copd, diabetes, prior_surg, emergency,
        creat, surg_valve, surg_cabg_valve, surg_other
    ]).astype(np.float32)

    cr_mg = creat / 88.4
    cr_score = np.where(cr_mg >= 2.1, 3.8, np.where(cr_mg >= 1.2, 1.8, 0.0))
    ef_score = np.where(lvef < 35.0, 1.8, np.where(lvef < 50.0, 0.8, 0.0))

    logit = (
        -4.2
        + 0.65 * female
        + 0.95 * chf
        + ef_score
        + 2.10 * iabp
        + 0.75 * copd
        + 0.85 * diabetes
        + 1.10 * prior_surg
        + 1.95 * emergency
        + cr_score
        + 1.05 * surg_valve
        + 2.15 * surg_cabg_valve
        + 1.85 * surg_other
    )

    prob = 1.0 / (1.0 + np.exp(-logit))
    y = rng.binomial(1, prob).astype(np.float32).reshape(-1, 1)

    return X, y


def train_and_export():
    torch.manual_seed(42)
    np.random.seed(42)

    X_train, y_train = generate_cohort(12000, seed=42)
    X_test, y_test = generate_cohort(4000, seed=123)

    mean = torch.tensor(np.mean(X_train, axis=0), dtype=torch.float32)
    std = torch.tensor(np.std(X_train, axis=0), dtype=torch.float32)

    model = AKINet(mean, std)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.005, weight_decay=1e-4)
    loss_fn = nn.BCELoss()

    X_t = torch.tensor(X_train, dtype=torch.float32)
    y_t = torch.tensor(y_train, dtype=torch.float32)

    model.train()
    for epoch in range(140):
        optimizer.zero_grad()
        out = model(X_t)
        loss = loss_fn(out, y_t)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        X_val = torch.tensor(X_test, dtype=torch.float32)
        preds = model(X_val).numpy().ravel()

    y_val = y_test.ravel()

    pos = preds[y_val == 1]
    neg = preds[y_val == 0]
    n_pos, n_neg = len(pos), len(neg)

    ranks = np.argsort(np.argsort(preds))
    sum_ranks_pos = np.sum(ranks[y_val == 1])
    u_stat = sum_ranks_pos - (n_pos * (n_pos - 1)) / 2.0
    auroc = float(u_stat / (n_pos * n_neg))

    brier = float(np.mean((preds - y_val) ** 2))
    thresh = 0.20
    sens = float(np.sum((preds >= thresh) & (y_val == 1)) / max(1, n_pos))
    spec = float(np.sum((preds < thresh) & (y_val == 0)) / max(1, n_neg))

    print(f"CSA-AKI Model Metrics: AUROC={auroc:.3f}, Brier={brier:.4f}, Sens={sens:.3f}, Spec={spec:.3f}")

    out_dir = Path("weights/aki")
    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = out_dir / "aki.onnx"

    dummy_input = torch.zeros((1, 12), dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_path),
        input_names=["features"],
        output_names=["probability"],
        dynamic_axes={"features": {0: "batch_size"}, "probability": {0: "batch_size"}},
        opset_version=14,
        dynamo=False,
    )
    print(f"Eksport qilindi: {onnx_path}")

    card = {
        "name": "csa_aki_ml",
        "version": "v2026.11.03",
        "task": "Post-cardiac surgery Acute Kidney Injury (KDIGO criteria)",
        "dataset": SYNTHETIC_DATASET,  # generator ma'lumoti — haqiqiy bemor emas
        "weights": "aki.onnx",
        "thresholds": {
            "low": 0.15,
            "moderate": 0.25,
            "high": 0.50,
            "abstain_band": [0.49, 0.51]
        },
        "metrics": {},  # haqiqiy bemorda o'lchanmagan — raqam yozilmaydi
        "validation": {"status": "tekshirilmagan", "clinical_use": False,
                       "summary": "SINTETIK — klinik foydalanish uchun emas."}
    }
    card_path = out_dir / "model_card.json"
    card_path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Model kartasi saqlandi: {card_path}")


if __name__ == "__main__":
    train_and_export()
