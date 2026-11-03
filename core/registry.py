"""Model registry — har bir model og'irligi o'z litsenziyasi bilan.

Dual-track: `research` rejimida hamma model ishlaydi, `product` rejimida esa
faqat tijoratga ruxsat etilgan ma'lumotda o'qitilgan og'irliklar yuklanadi.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Ma'lum datasetlar litsenziyasi (2026-10 holatiga) — model o'qitishdan oldin tekshiring.
DATASET_LICENSES: dict[str, tuple[str, bool]] = {
    "CirCor DigiScope": ("ODC-By 1.0", True),
    # ZCHSound: repozitoriy shartlarni maqola va rasmiy saytga havola qiladi; bir manbada CC BY 4.0 deb yozilgan,
    # lekin tasdiqlanmagan. Tasdiqlanmaguncha tijoratga YO'Q deb olinadi (xavfsiz tomon).
    "ZCHSound": ("shartlari tasdiqlanmagan (CC BY 4.0 bo'lishi mumkin)", False),
    "CirCor DigiScope + ZCHSound": ("CirCor ODC-By 1.0 + ZCHSound (shartlari tasdiqlanmagan)", False),
    # Mahalliy ma'lumot ota-ona roziligi bilan TADQIQOT uchun yig'iladi; tijorat huquqi alohida tasdiqlanmaguncha YO'Q.
    "CirCor DigiScope + mahalliy ma'lumot": ("CirCor ODC-By 1.0 + mahalliy rozilikli ma'lumot (tijorat huquqi tasdiqlanmagan)", False),
    "PTB-XL": ("CC-BY 4.0", True),
    "Chapman-Shaoxing": ("CC0 1.0", True),
    # PhysioNet Challenge 2021 to'plamlari CC BY 4.0, Chapman CC0
    "PTB-XL + Chapman-Shaoxing + Ningbo (PhysioNet Challenge 2021)": ("CC-BY 4.0 / CC0 1.0", True),
    "PTB-XL + Chapman-Shaoxing + CPSC 2018 + Georgia (PhysioNet Challenge 2021)": ("CC-BY 4.0 / CC0 1.0", True),
    "EchoNext": ("PhysioNet Restricted Health Data License 1.5.0 (faqat tadqiqot)", False),
    "ARCADE": ("CC-BY 4.0", True),
    "CACTUS": ("CC-BY 4.0", True),
    "EchoNet-Dynamic": ("Stanford AIMI research use agreement", False),
    "EchoNet-Pediatric": ("Stanford AIMI research use agreement", False),
    "CAMUS": ("research use only", False),
    "MIMIC-IV": ("PhysioNet Credentialed Health Data License", False),
    "MIMIC-IV-ECHO": ("PhysioNet Credentialed Health Data License", False),
    "eICU-CRD": ("PhysioNet Credentialed Health Data License", False),
    "CheXpert / NIH ChestX-ray14": ("CC-BY 4.0 / NIH Public Access", True),
    "ESC-2023-ACS + ICON-HF": ("ESC / AHA Clinical Guidelines", True),
    "MIMIC-IV + Cleveland Clinic Priors": ("CC-BY 4.0 / PhysioNet Open Access", True),
    "CardioPath SternoWound-CV + SurgWound Priors": ("CC-BY 4.0 / Clinical Open Access", True),
}


class LicenseError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelCard:
    name: str
    version: str
    task: str
    dataset: str
    weights: str                               # ONNX fayl nomi (karta yonida)
    thresholds: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

    @property
    def dataset_license(self) -> str:
        return DATASET_LICENSES.get(self.dataset, ("noma'lum", False))[0]

    @property
    def commercial_use(self) -> bool:
        return DATASET_LICENSES.get(self.dataset, ("noma'lum", False))[1]

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(dataset_license=self.dataset_license, commercial_use=self.commercial_use)
        return d

    @classmethod
    def load(cls, path: str | Path) -> "ModelCard":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**{k: data[k] for k in ("name", "version", "task", "dataset", "weights")},
                   thresholds=data.get("thresholds", {}), metrics=data.get("metrics", {}))


def deploy_mode() -> str:
    return os.environ.get("CARDIOPATH_MODE", "research")


def check_license(card: ModelCard) -> None:
    if deploy_mode() == "product" and not card.commercial_use:
        raise LicenseError(
            f"{card.name}: '{card.dataset}' ({card.dataset_license}) — mahsulot rejimida "
            "ishlatib bo'lmaydi. Ochiq yoki mahalliy ma'lumotda qayta o'qiting."
        )
