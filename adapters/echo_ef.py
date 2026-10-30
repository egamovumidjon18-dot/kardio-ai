"""ExoKG EF adapteri: NeuroSon-AI (`uttai/heart`, EchoNet-Dynamic, R(2+1)D-18) → `Evidence("echo.ef")`.

NeuroSon kodi import QILINMAYDI (torch/smp og'ir bog'liqliklari): faqat uning ONNX og'irligi
`onnxruntime` bilan ishga tushiriladi, oldindan ishlov esa NeuroSon `EFModule` bilan bir xil:
kulrang → 112×112 → [0,1] → 16 ta teng taqsimlangan kadr → 3 kanalga takrorlash.

LITSENZIYA: EchoNet-Dynamic — Stanford AIMI tadqiqot shartnomasi, tijorat EMAS (registry: commercial_use=False).
`CARDIOPATH_MODE=product` da bu adapter yuklanmaydi (LicenseError).

Metrika (NeuroSon hisoboti bo'yicha, validatsiya): MAE 5.83%, R² 0.575. Biz EchoNet ma'lumotini ko'chirib
qayta baholamadik — bu raqamlar bu loyiha ichida tasdiqlanmagan.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np

from core.evidence import Evidence, Provenance, RiskLevel, Source
from core.registry import ModelCard, check_license

DEFAULT_ONNX = r"C:\Users\user\NeuroSon-AI\weights\heart_echonet.onnx"
MAE = 5.83                       # NeuroSon val MAE (%) — noaniqlik shkalasi
EF_PLAUSIBLE = (10.0, 85.0)
MIN_AGE_YEARS = 18.0             # EchoNet-Dynamic — kattalar, apikal 4 kamera
REFERENCE = "EchoNet-Dynamic (Ouyang 2020), R(2+1)D-18; NeuroSon-AI uttai/heart EFModule"


def ef_risk(ef: float) -> RiskLevel:
    """ASE/ESC toifalari: ≥50 saqlangan, 41–49 biroz pasaygan, 31–40 pasaygan, ≤30 og'ir pasaygan."""
    if ef >= 50:
        return RiskLevel.LOW
    if ef > 40:
        return RiskLevel.MODERATE
    if ef > 30:
        return RiskLevel.HIGH
    return RiskLevel.VERY_HIGH


def sample_frames(video: str | Path, n: int = 16, size: int = 112) -> Optional[np.ndarray]:
    """Videodan n ta teng taqsimlangan kulrang kadr → [n, size, size] float32 [0,1] (NeuroSon bilan bir xil)."""
    import cv2

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return None
    idxs = sorted(set(np.linspace(0, max(total - 1, 0), n).astype(int).tolist()))
    got, i = {}, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i in idxs:
            got[i] = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (size, size))
        i += 1
    cap.release()
    if len(got) < max(4, len(idxs) // 2):
        return None
    fallback = got[min(got)]
    seq = [got.get(k, fallback) for k in idxs]
    while len(seq) < n:                      # qisqa video: oxirgi kadrni takrorlash
        seq.append(seq[-1])
    return np.stack(seq).astype(np.float32) / 255.0


class EchoEFAdapter:
    def __init__(self, onnx_path: str | Path, num_frames: int = 16, size: int = 112) -> None:
        import onnxruntime as ort

        self.card = ModelCard(name="echo_ef_r2plus1d", version="neuroson-2026", task="ExoKG videosidan LVEF% regressiyasi",
                              dataset="EchoNet-Dynamic", weights=str(onnx_path),
                              metrics={"val_mae_pct": MAE, "val_r2": 0.575, "source": "NeuroSon-AI hisoboti; bu yerda qayta baholanmagan"})
        check_license(self.card)
        so = ort.SessionOptions()
        so.add_session_config_entry("session.set_denormal_as_zero", "1")
        self.sess = ort.InferenceSession(str(onnx_path), so, providers=["CPUExecutionProvider"])
        self.num_frames, self.size = num_frames, size

    @classmethod
    def from_env(cls) -> Optional["EchoEFAdapter"]:
        """CARDIOPATH_EF_WEIGHTS (yoki NeuroSon standart yo'li). Yo'q bo'lsa None → EF moduli o'chiq."""
        path = Path(os.environ.get("CARDIOPATH_EF_WEIGHTS", DEFAULT_ONNX))
        if not path.exists():
            return None
        meta = path.with_suffix(".meta.json")
        nf, sz = 16, 112
        if meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            nf, sz = int(m.get("num_frames", 16)), int(m.get("size", 112))
        return cls(path, nf, sz)

    def _prov(self) -> Provenance:
        return Provenance(name=self.card.name, version=self.card.version, reference=REFERENCE,
                          dataset_license=self.card.dataset_license)

    def predict_frames(self, clip: np.ndarray) -> float:
        """clip: [T, H, W] float32 [0,1] → EF%."""
        x = np.stack([clip] * 3, axis=1)[None].astype(np.float32)          # [1, T, 3, H, W]
        return float(self.sess.run(["ef"], {"input": x})[0][0])

    def analyze(self, video: str | Path, age_years: Optional[float] = None) -> Evidence:
        prov, kind = self._prov(), "echo.ef"
        if age_years is not None and age_years < MIN_AGE_YEARS:
            return Evidence.abstain(kind, Source.MODEL, prov,
                                    f"yosh {age_years:.0f}: model kattalar ExoKG'sida o'rgatilgan — bolalarda baholanmagan")
        if not Path(video).exists():
            return Evidence.abstain(kind, Source.MODEL, prov, "video fayl topilmadi")
        clip = sample_frames(video, self.num_frames, self.size)
        if clip is None:
            return Evidence.abstain(kind, Source.MODEL, prov, "videoni o'qib bo'lmadi yoki kadrlar yetarli emas "
                                                              "(EF uchun to'liq yurak sikli kerak, bitta rasm yetmaydi)")
        if clip.std() < 0.03 or clip.std(axis=0).mean() < 0.005:
            return Evidence.abstain(kind, Source.MODEL, prov,
                                    "kontrast past yoki kadrlar o'zgarmaydi (harakat yo'q) — EF baholab bo'lmaydi")
        ef = self.predict_frames(clip)
        if not EF_PLAUSIBLE[0] <= ef <= EF_PLAUSIBLE[1]:
            return Evidence.abstain(kind, Source.MODEL, prov,
                                    f"EF {ef:.0f}% — fiziologik/ishonchli diapazondan tashqari (rasm apikal 4 kamera emas bo'lishi mumkin)")
        ef = round(ef, 1)
        expl = [f"EF ≈ {ef:.0f}% (±{MAE:.0f}% model xatosi); ExoKG apikal 4 kameradan",
                "tadqiqot rejimi: EchoNet litsenziyasi tijoratga ruxsat bermaydi",
                "yakuniy EF — ExoKG shifokorining (Simpson) o'lchovi"]
        return Evidence(kind=kind, value=ef, unit="%", source=Source.MODEL, provenance=prov, risk=ef_risk(ef),
                        uncertainty=MAE, explanation=expl)
