"""DIQQAT: bu skript SINTETIK (generator) ma'lumotda o'qitadi. Natijadagi model faqat muhandislik
sinovi uchun; dastur uni klinik ishga yuklamaydi (core.registry.refuse_synthetic)."""
from core.registry import SYNTHETIC_DATASET
"""Post-sternotomiya operatsiyadan keyingi yara holatini (infeksiya / ajralish)
tasvirdan aniqlovchi WoundNet modelini yaratish va ONNX ga eksport qilish.

Klasslar (4 ta):
  0: clean — asoratsiz toza bitish
  1: erythema — yara atrofida 2+ sm qizarish (yallig'lanish)
  2: discharge — ekssudat / yiringli ajralma
  3: dehiscence — chok ajralishi (dehissensiya)
"""
import json
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn


class ConvBlock(nn.Module):
    def __init__(self, in_c: int, out_c: int, stride: int = 1):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_c, in_c, kernel_size=3, stride=stride, padding=1, groups=in_c, bias=False),
            nn.BatchNorm2d(in_c),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_c, out_c, kernel_size=1, bias=False),
            nn.BatchNorm2d(out_c),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class WoundNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1, bias=False),  # 112x112
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            ConvBlock(32, 64, stride=2),   # 56x56
            ConvBlock(64, 128, stride=2),  # 28x28
            ConvBlock(128, 256, stride=2), # 14x14
            nn.Conv2d(256, 256, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, 4),
            nn.Softmax(dim=1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.features(x)
        return self.classifier(feat)


def generate_synthetic_wound_batch(batch_size: int = 64) -> tuple[torch.Tensor, torch.Tensor]:
    """Sintetik jarrohlik yara morfologiyasi generatori."""
    imgs = np.zeros((batch_size, 3, 224, 224), dtype=np.float32)
    labels = np.zeros(batch_size, dtype=np.int64)

    y, x = np.ogrid[:224, :224]

    for i in range(batch_size):
        cls_idx = i % 4
        labels[i] = cls_idx

        # Baza: inson teri foni (R: 0.72-0.82, G: 0.52-0.62, B: 0.45-0.55)
        skin_r = np.random.uniform(0.72, 0.82)
        skin_g = np.random.uniform(0.52, 0.62)
        skin_b = np.random.uniform(0.45, 0.55)

        base_img = np.zeros((3, 224, 224), dtype=np.float32)
        base_img[0] = skin_r + np.random.normal(0, 0.02, (224, 224))
        base_img[1] = skin_g + np.random.normal(0, 0.02, (224, 224))
        base_img[2] = skin_b + np.random.normal(0, 0.02, (224, 224))

        # Vertikal sternotomiya chiziqli chok izi (x ~ 112 atrofida)
        scar_mask = (np.abs(x - 112) <= 3) & (y >= 30) & (y <= 194)
        base_img[0, scar_mask] = 0.60
        base_img[1, scar_mask] = 0.38
        base_img[2, scar_mask] = 0.38

        if cls_idx == 0:
            # Clean: asoratsiz, toza chiziq
            pass
        elif cls_idx == 1:
            # Erythema: qizarish keng tarqalgan (x masofa 4 dan 25 gacha)
            halo_mask = (np.abs(x - 112) > 3) & (np.abs(x - 112) <= 28) & (y >= 40) & (y <= 180)
            base_img[0, halo_mask] = np.clip(base_img[0, halo_mask] + 0.28, 0, 1)
            base_img[1, halo_mask] = np.clip(base_img[1, halo_mask] - 0.12, 0, 1)
            base_img[2, halo_mask] = np.clip(base_img[2, halo_mask] - 0.12, 0, 1)
        elif cls_idx == 2:
            # Discharge: yiringli/sarg'ish ajralma o'chog'i (markazda)
            exudate_mask = ((x - 112)**2 / 12**2 + (y - 120)**2 / 24**2) <= 1.0
            base_img[0, exudate_mask] = 0.90
            base_img[1, exudate_mask] = 0.88
            base_img[2, exudate_mask] = 0.25
        elif cls_idx == 3:
            # Dehiscence: chok ochilib ketgan, markazda qora/chuqur bo'shliq
            gap_mask = (np.abs(x - 112) <= 8) & (y >= 80) & (y <= 150)
            base_img[0, gap_mask] = 0.12
            base_img[1, gap_mask] = 0.05
            base_img[2, gap_mask] = 0.05

        imgs[i] = np.clip(base_img, 0.0, 1.0)

    # ImageNet normallash
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)
    imgs = (imgs - mean) / std

    return torch.tensor(imgs, dtype=torch.float32), torch.tensor(labels, dtype=torch.long)


def train_and_export():
    torch.manual_seed(42)
    np.random.seed(42)

    model = WoundNet()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss()

    model.train()
    for step in range(100):
        optimizer.zero_grad()
        imgs, targets = generate_synthetic_wound_batch(32)
        preds = model(imgs)
        loss = loss_fn(preds, targets)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        val_imgs, val_targets = generate_synthetic_wound_batch(128)
        val_preds = model(val_imgs).numpy()

    acc = float(np.mean(np.argmax(val_preds, axis=1) == val_targets.numpy()))
    print(f"WoundNet validation accuracy: {acc:.3%}")

    # Export to ONNX
    out_dir = Path("weights/wound")
    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = out_dir / "wound.onnx"

    dummy_input = torch.zeros((1, 3, 224, 224), dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_path),
        input_names=["image"],
        output_names=["probabilities"],
        dynamic_axes={"image": {0: "batch_size"}, "probabilities": {0: "batch_size"}},
        opset_version=14,
        dynamo=False,
    )
    print(f"WoundNet ONNX eksport qilindi: {onnx_path} ({onnx_path.stat().st_size} bayt)")

    card = {
        "name": "wound_image_cv",
        "version": "v2026.11.03",
        "task": "Post-sternotomy wound complication & dehiscence detection (224x224 RGB)",
        "dataset": SYNTHETIC_DATASET,  # generator ma'lumoti — haqiqiy bemor emas
        "weights": "wound.onnx",
        "thresholds": {
            "clean": 0.50,
            "erythema": 0.35,
            "discharge": 0.45,
            "dehiscence": 0.35,
            "abstain_confidence": 0.40,
            "min_blur_variance": 35.0,
            "min_brightness": 25.0,
            "max_brightness": 240.0
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
