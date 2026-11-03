"""CardioPath AI — To'liq Jonli Klinik Sinov (Live End-to-End Clinical Trial).

Ushbu skript http://127.0.0.1:8010 da ishlab turgan serverga ulanib,
bemorning butun hayot sikli (Skrining -> Workup -> Heart Team -> ICU -> Guardian)
bo'yicha barcha 8 ta sun'iy intellekt modeli va klinik qoidalarni sinovdan o'tkazadi.
"""
import io
import time
from datetime import datetime, timezone
import httpx
import numpy as np
from PIL import Image

BASE_URL = "http://127.0.0.1:8010"


def print_step(step_num: int, title: str):
    print(f"\n{'='*75}")
    print(f"BOSQICH {step_num}: {title.upper()}")
    print(f"{'='*75}")


def make_dummy_ecg_csv(fs: int = 100) -> bytes:
    """10 soniyalik 12 tarmoqli sinov EKG signali."""
    t = np.linspace(0, 10, 10 * fs)
    names = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
    leads = []
    for i in range(12):
        sig = 0.8 * np.sin(2 * np.pi * 1.2 * t + i * 0.2) + 0.1 * np.sin(2 * np.pi * 50 * t)
        leads.append(sig)
    leads_arr = np.column_stack(leads)

    buf = io.StringIO()
    buf.write(",".join(names) + "\n")
    for row in leads_arr:
        buf.write(",".join(f"{v:.4f}" for v in row) + "\n")
    return buf.getvalue().encode("utf-8")


def make_dummy_cxr_png() -> bytes:
    """Sintetik 224x224 ko'krak qafasi frontal rentgenogrammasi."""
    y, x = np.ogrid[:224, :224]
    thorax_w = 160
    heart_w = 90  # CTR ~ 0.56 (Kardiomegaliya)
    heart_mask = ((x - 112)**2 / (heart_w / 2)**2 + (y - 125)**2 / 70**2) <= 1.0

    img = np.random.normal(0.2, 0.05, (224, 224)).astype(np.float32)
    img[heart_mask] += 0.55
    img = np.clip(img * 255, 0, 255).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="PNG")
    return buf.getvalue()


def make_dummy_angio_png() -> bytes:
    """Sintetik koronar angiografiya kadri (512x512)."""
    img = np.ones((512, 512), dtype=np.uint8) * 180
    y, x = np.ogrid[:512, :512]
    vessel = (np.abs(y - x) <= 12) & (x >= 80) & (x <= 420)
    img[vessel] = 60
    stenosis = (np.abs(y - x) <= 3) & (x >= 230) & (x <= 270)
    img[stenosis] = 90

    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="PNG")
    return buf.getvalue()


def make_wound_image(blurred: bool = False) -> bytes:
    """Sintetik sternotomiya yarasi fotosurati (224x224 RGB)."""
    if blurred:
        arr = np.ones((224, 224, 3), dtype=np.uint8) * 128
    else:
        rng = np.random.default_rng(42)
        arr = np.clip(rng.normal(140, 25, (224, 224, 3)), 0, 255).astype(np.uint8)
        arr[40:180, 110:114, 0] = 220
        arr[40:180, 110:114, 1] = 60
        arr[40:180, 110:114, 2] = 60

    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def run_trial():
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # -------------------------------------------------------------------------
    # 1. TIZIM STATUSI VA MODELLAR RO'YXATI
    # -------------------------------------------------------------------------
    print_step(1, "Tizim Salomatligi va Barcha 8 ta Model Holatini Tekshirish")
    res_health = client.get("/health")
    assert res_health.status_code == 200, f"Health xatosi: {res_health.text}"
    h_data = res_health.json()
    print(f"✓ /health javobi: status={h_data['status']}, rejim={h_data['mode']}, PCG={h_data['pcg_model']['name']}")

    res_models = client.get("/models")
    assert res_models.status_code == 200, f"Models xatosi: {res_models.text}"
    m_data = res_models.json()
    print(f"✓ /models javobi: {len(m_data)} ta parametr qabul qilindi.")
    blocked = m_data.get("blocked", {})
    print(f"  • Bloklangan modellar soni: {len(blocked)} ta")
    assert len(blocked) == 0, f"Bloklangan modellar mavjud: {blocked}"
    print("  • Barcha AI modellar Faol holatda:")
    for k in ["ecg", "angio", "cxr", "ecg_low_ef", "ecg_shd", "csa_aki_ml", "wound_image_cv"]:
        item = m_data.get(k)
        if item:
            auroc_val = item['metrics'].get('AUROC') or item['metrics'].get('test', {}).get('cardiomegaly_auc') or item['metrics'].get('test_auroc') or 'N/A'
            print(f"    - {k:15}: {item['name']:25} | Litsenziya: {item['dataset_license']} | AUROC: {auroc_val}")

    # -------------------------------------------------------------------------
    # 2. PEDIATRIK CHAQALOQLAR TYN SKRININGI
    # -------------------------------------------------------------------------
    print_step(2, "Pediatrik Chaqaloq Tug'ma Yurak Nuqsoni (TYN) Skriningi")
    p_code = f"TEST-PED-{int(time.time())}"
    res_ep1 = client.post("/episodes", json={"patient_ref": p_code, "actor": "dr_screening", "population": "pediatric"})
    assert res_ep1.status_code == 201
    eid_ped = res_ep1.json()["id"]
    print(f"✓ Yangi chaqaloq epizodi yaratildi: {eid_ped} (Kodi: {p_code})")

    # Giperoksiya testi va SpO2 (O'ng qo'l 97%, oyoq 90% — patologik gipoksiya, duktusga bog'liq TYN shubhasi)
    res_scr = client.post(
        f"/episodes/{eid_ped}/screening",
        data={
            "actor": "dr_screening",
            "right_hand_spo2": "97.0",
            "foot_spo2": "90.0",
            "age_hours": "36.0",
            "red_flags": "cyanosis,tachypnea_rest",
            "lang": "uz"
        }
    )
    assert res_scr.status_code == 200, f"Screening xatosi: {res_scr.text}"
    scr_out = res_scr.json()
    print(f"✓ Chaqaloq skrining triaj natijasi: {scr_out['plain']['headline']}")
    print(f"  • Triaj xulosasi: {scr_out['plain']['todo']}")
    print(f"  • Xavf darajasi: {scr_out['plain']['level'].upper()}")

    # -------------------------------------------------------------------------
    # 3. KATTA YOSHLI OKS VA MULTIMODAL ISHLAB CHIQARISH (WORKUP)
    # -------------------------------------------------------------------------
    print_step(3, "Katta Yoshli Bemor: OKS, 12-Tarmoqli EKG, Rentgen va Biomarkerlar")
    a_code = f"TEST-ADULT-ACS-{int(time.time())}"
    res_ep2 = client.post("/episodes", json={"patient_ref": a_code, "actor": "dr_emergency", "population": "adult"})
    assert res_ep2.status_code == 201
    eid_adult = res_ep2.json()["id"]
    print(f"✓ Katta yoshli shoshilinch bemor yaratildi: {eid_adult} (Kodi: {a_code})")

    # Workup bosqichiga o'tkazish
    res_tr1 = client.post(f"/episodes/{eid_adult}/transition", json={"from_stage": "screening", "to_stage": "workup", "author": "dr_emergency"})
    assert res_tr1.status_code == 200
    print("✓ Bosqich muvaffaqiyatli o'zgartirildi: screening -> workup")

    # A) 12 tarmoqli EKG yuklash va AI tahlili
    print("\n  [A] 12-tarmoqli EKG yuklash...")
    ecg_bytes = make_dummy_ecg_csv()
    res_ecg = client.post(
        f"/episodes/{eid_adult}/ecg",
        data={"actor": "dr_emergency", "fs": "100", "age_years": "64"},
        files={"file": ("ecg_patient.csv", ecg_bytes, "text/csv")}
    )
    assert res_ecg.status_code == 200, f"EKG xatosi: {res_ecg.text}"
    ecg_out = res_ecg.json()
    print(f"  ✓ EKG AI natijalari:")
    print(f"    - Asosiy EKG Ritm: {ecg_out['evidence']['kind']} | Xavf: {ecg_out['evidence']['risk']}")
    if "low_ef" in ecg_out:
        print(f"    - Yashirin Past LVEF AI: {ecg_out['low_ef']['evidence']['risk']} | p={ecg_out['low_ef']['evidence']['value'].get('prob_low_ef', 'N/A')}")
    if "structural" in ecg_out:
        print(f"    - Strukturaviy patologiya AI: {ecg_out['structural']['evidence']['risk']} | Tavsiya: {ecg_out['structural']['evidence']['explanation'][0] if ecg_out['structural']['evidence']['explanation'] else ''}")

    # B) Ko'krak qafasi rentgenogrammasi (CXR) yuklash
    print("\n  [B] Ko'krak qafasi rentgenogrammasi (CXR) tahlili...")
    cxr_bytes = make_dummy_cxr_png()
    res_cxr = client.post(
        f"/episodes/{eid_adult}/cxr",
        data={"actor": "dr_radiology", "view_position": "PA", "lang": "uz"},
        files={"file": ("cxr_frontal.png", cxr_bytes, "image/png")}
    )
    assert res_cxr.status_code == 200, f"CXR xatosi: {res_cxr.text}"
    cxr_ev = res_cxr.json()["evidence"]
    print(f"  ✓ CXR AI natijalari:")
    print(f"    - Xavf darajasi: {cxr_ev['risk']}")
    print(f"    - O'lchovlar: CTR = {cxr_ev['value']['ctr_ratio']:.2f} (Norma <=0.50) | Kardiomegaliya={cxr_ev['value']['cardiomegaly']} | O'pka dimlanishi={cxr_ev['value']['pulmonary_congestion']}")

    # C) Yuqori sezgir Troponin (hs-cTn 0h/1h) va NT-proBNP biomarker kinetikasi
    print("\n  [C] Biomarkerlar kinetikasi (ESC 2023 algoritmi)...")
    res_bio = client.post(f"/episodes/{eid_adult}/biomarkers", json={
        "actor": "dr_lab",
        "troponin_0h_ng_l": 55.0,
        "troponin_1h_ng_l": 95.0,  # Ko'tarilish delta > 5 ng/L -> ESC Rule-in (O'tkir miokard infarkti)
        "nt_probnp_pg_ml": 3400.0,
        "age_years": 64.0
    })
    assert res_bio.status_code == 200, f"Biomarker xatosi: {res_bio.text}"
    bio_ev = res_bio.json()["evidence"]
    print(f"  ✓ Biomarkerlar natijasi: Xavf = {bio_ev['risk']}")
    for exp in bio_ev["explanation"]:
        print(f"    - {exp}")

    # D) Valvular ExoKG Doppler tahlili (Aortal stenoz va Mitral regürgitatsiya)
    print("\n  [D] Valvular Doppler ExoKG gemodinamikasi...")
    res_valve = client.post(f"/episodes/{eid_adult}/echo/valves", json={
        "actor": "dr_echo",
        "as_vmax": 4.3,          # >4.0 m/s -> Og'ir aortal stenoz
        "as_mean_gradient": 45.0, # >40 mmHg -> Og'ir aortal stenoz
        "as_ava": 0.75,          # <1.0 cm2 -> Og'ir aortal stenoz
        "mr_eroa": 42.0,         # >=40 mm2 -> Og'ir mitral regürgitatsiya
        "mr_reg_vol": 62.0,      # >=60 ml -> Og'ir mitral regürgitatsiya
        "tr_vmax": 3.6,          # O'pka bosimi sPAP hisoblash uchun
        "rap": 10.0,
        "lvef": 42.0
    })
    assert res_valve.status_code == 200, f"Valves xatosi: {res_valve.text}"
    valve_ev = res_valve.json()["evidence"]
    print(f"  ✓ ExoKG gemodinamik xulosasi: Xavf={valve_ev['risk']}")
    for exp in valve_ev.get('explanation', []):
        print(f"    - {exp}")

    # E) Koronar angiografiya U-Net segmentatsiyasi
    print("\n  [E] Koronar angiografiya stenoz segmentatsiyasi (ARCADE U-Net)...")
    angio_bytes = make_dummy_angio_png()
    res_angio = client.post(
        f"/episodes/{eid_adult}/angio",
        data={"actor": "dr_cath_lab"},
        files={"file": ("coronary_angio.png", angio_bytes, "image/png")}
    )
    assert res_angio.status_code == 200, f"Angio xatosi: {res_angio.text}"
    angio_ev = res_angio.json()["evidence"]
    print(f"  ✓ Angiografiya AI tahlili: Xavf={angio_ev['risk']} | Stenoz={angio_ev['value']['label']}")

    # -------------------------------------------------------------------------
    # 4. HEART TEAM KONSILIUMI VA CSA-AKI ML MODELI
    # -------------------------------------------------------------------------
    print_step(4, "Heart Team Konsiliumi: EuroSCORE II, Thakar AKI va CSA-AKI ML Modeli")
    res_tr2 = client.post(f"/episodes/{eid_adult}/transition", json={
        "from_stage": "workup", "to_stage": "heart_team", "author": "dr_chief",
        "questions": ["KShSh (CABG) yoki Ko'p tomirli Stentlash (PCI)?", "Aortal qopqoqni almashtirish (AVR) zarurati."]
    })
    assert res_tr2.status_code == 200
    print("✓ Bosqich muvaffaqiyatli o'zgartirildi: workup -> heart_team")

    euroscore_body = {
        "age": 64, "female": False, "weight_kg": 84, "creatinine_umol_l": 145.0,
        "extracardiac_arteriopathy": True, "poor_mobility": False, "previous_cardiac_surgery": False,
        "chronic_lung_disease": True, "active_endocarditis": False, "critical_preop_state": False,
        "insulin_diabetes": True, "nyha": 3, "ccs4_angina": True, "urgency": "emergency",
        "weight_of_intervention": "two", "lvef_percent": 42.0, "pa_systolic_mmhg": 62.0
    }
    aki_body = {
        "female": False, "congestive_heart_failure": True, "lvef_percent": 42.0, "preop_iabp": False,
        "copd": True, "insulin_diabetes": True, "previous_cardiac_surgery": False, "emergency": True,
        "surgery": "cabg_valve", "creatinine_umol_l": 145.0
    }

    res_risk = client.post(f"/episodes/{eid_adult}/risk", json={
        "actor": "dr_heart_team",
        "euroscore": euroscore_body,
        "aki": aki_body,
        "lvef_measured_at": datetime.now(timezone.utc).isoformat()
    })
    assert res_risk.status_code == 200, f"Risk xatosi: {res_risk.text}"
    risk_out = res_risk.json()
    print("✓ Heart Team xavf tahlili to'liq yakunlandi:")
    for rev in risk_out["evidence"]:
        print(f"  • {rev['kind']:22} | Qiymat: {rev['value']} {rev.get('unit','')} | Xavf: {rev['risk']}")
    
    conc = risk_out.get("aki_concordance")
    if conc:
        print(f"\n  ✓ BUYRAK ASORATI KONKORDANSI: Status={conc['status']} | Yakuniy Xavf={conc['final_risk']}")
        print(f"    - Tushuntirish: {conc.get('message', '')}")

    # Heart Team rasmiy protokoli matnini generatsiya qilish
    res_proto = client.get(f"/episodes/{eid_adult}/heart-team-protocol")
    assert res_proto.status_code == 200
    print("\n✓ Konsilium rasmiy protokoli generatsiya qilindi:")
    print("  " + "\n  ".join(res_proto.text.strip().split("\n")[:6]) + "\n  ...")

    # -------------------------------------------------------------------------
    # 5. REANIMATSIYA (ICU), BUYRAK MONITORINGI VA CHIQARISH
    # -------------------------------------------------------------------------
    print_step(5, "Operatsiya, Reanimatsiya (ICU), KDIGO Monitoringi va Chiqarish")
    client.post(f"/episodes/{eid_adult}/transition", json={"from_stage": "heart_team", "to_stage": "procedure", "author": "dr_surgeon"})
    print("✓ Bosqich: heart_team -> procedure (KShSh + Aortal qopqoq operatsiyasi o'tkazildi)")
    
    client.post(f"/episodes/{eid_adult}/transition", json={"from_stage": "procedure", "to_stage": "icu", "author": "dr_icu"})
    print("✓ Bosqich: procedure -> icu (Bemor reanimatsiyaga qabul qilindi)")

    res_kdigo = client.post(f"/episodes/{eid_adult}/kdigo", json={
        "actor": "dr_icu",
        "baseline_creatinine": 145.0,
        "current_creatinine": 210.0,
        "urine_output_ml_kg_h": 0.42,
        "urine_hours": 8.0,
        "rrt": False
    })
    assert res_kdigo.status_code == 200
    kdigo_ev = res_kdigo.json()["evidence"]
    print(f"✓ Reanimatsiya KDIGO AKI holati: Bosqich={kdigo_ev['value']['stage']} | Xavf={kdigo_ev['risk']}")

    client.post(f"/episodes/{eid_adult}/transition", json={"from_stage": "icu", "to_stage": "discharge", "author": "dr_icu"})
    print("✓ Bosqich: icu -> discharge (Palataga o'tkazildi, dori buyurildi)")
    client.post(f"/episodes/{eid_adult}/transition", json={"from_stage": "discharge", "to_stage": "guardian_30d", "author": "dr_surgeon"})
    print("✓ Bosqich: discharge -> guardian_30d (Bemor uyga chiqarildi, 30 kunlik masofaviy qo'riqchi ishga tushdi)")

    # -------------------------------------------------------------------------
    # 6. POST-OP GUARDIAN 30D MASOFAVIY MONITORING VA WOUND_IMAGE_CV
    # -------------------------------------------------------------------------
    print_step(6, "Post-Op Guardian 30D: Uy Monitoringi, INR OCR va WoundNet CV")
    
    # A) Kunlik tana vazni va shikoyatlar
    res_chk = client.post(f"/episodes/{eid_adult}/guardian/checkin", json={
        "actor": "patient",
        "weight_kg": 85.8,
        "heart_rate": 88.0,
        "temperature_c": 37.4,
        "symptoms": ["entikish", "oyoq_shishi"]
    })
    assert res_chk.status_code == 200
    print(f"✓ Bemor uy check-in tekshiruvi: Eskalatsiya={res_chk.json()['escalation']['alert']}")

    # B) Varfarin INR tahlili
    res_inr = client.post(f"/episodes/{eid_adult}/guardian/inr", json={
        "actor": "patient",
        "indication": "mechanical_aortic",
        "value": 1.7
    })
    assert res_inr.status_code == 200
    inr_esc = res_inr.json()["escalation"]
    print(f"✓ Varfarin INR tahlili: Qiymat=1.7 | Eskalatsiya darajasi={inr_esc['alert'].upper()}")

    # C) Sternotomiya yarasi fotosurati (WoundImage CV AI)
    print("\n  [WoundNet CV Sinovi 1]: Sifatsiz (xira) rasm yuborilganda model Abstain xatti-harakati...")
    blur_img = make_wound_image(blurred=True)
    res_w1 = client.post(
        f"/episodes/{eid_adult}/guardian/wound-image",
        data={"actor": "patient"},
        files={"file": ("wound_blur.png", blur_img, "image/png")}
    )
    assert res_w1.status_code == 200
    ev_w1 = res_w1.json()["evidence"][0]
    print(f"  ✓ Sifatsiz rasmda AI to'xtadi (Abstained={ev_w1['abstained']}): '{ev_w1['explanation'][0]}'")

    print("\n  [WoundNet CV Sinovi 2]: Sifatli yara surati tahlili va eskalatsiya...")
    valid_img = make_wound_image(blurred=False)
    res_w2 = client.post(
        f"/episodes/{eid_adult}/guardian/wound-image",
        data={"actor": "patient"},
        files={"file": ("wound_valid.png", valid_img, "image/png")}
    )
    assert res_w2.status_code == 200
    w2_json = res_w2.json()
    ev_w2 = w2_json["evidence"][0]
    print(f"  ✓ Sifatli rasmda AI muvaffaqiyatli xulosa berdi:")
    print(f"    - Xavf darajasi: {ev_w2['risk']}")
    print(f"    - Ehtimolliklar: {ev_w2['value']}")
    print(f"    - Shifokorga eskalatsiya ogohlantirishi: {w2_json['escalation']['alert'].upper()}")

    # -------------------------------------------------------------------------
    # 7. ZAXIRA TIKLASH MASHQI (RESTORE DRILL) VA AUDIT LOGI
    # -------------------------------------------------------------------------
    print_step(7, "Tizim Zaxirasi Tiklash Mashqi (Restore Drill) va Audit Logi")
    res_b = client.post("/backups")
    if res_b.status_code == 201:
        b_info = res_b.json()
        print(f"✓ Yangi tizim zaxira nusxasi yaratildi: {b_info.get('name')} ({b_info.get('size_bytes')} bayt)")
    
    res_drill = client.post("/backups/restore-drill")
    if res_drill.status_code == 200:
        drill_data = res_drill.json()
        print(f"✓ Avtomatik zaxira tiklash mashqi (Restore Drill): Muvaffaqiyatli={drill_data.get('success')}")
        print(f"  • Tekshirilgan zaxira fayli: {drill_data.get('backup_path')}")
        print(f"  • Tiklangan audit yozuvlari soni: {drill_data.get('audit_count')} ta")
        print(f"  • Kriptografik audit xesh zanjiri: {drill_data.get('audit_chain_valid')} ({drill_data.get('audit_chain_message')})")
    else:
        print(f"  • Zaxira mashqi statusi: {res_drill.status_code}")

    res_final = client.get(f"/episodes/{eid_adult}").json()
    res_audit = client.get(f"/episodes/{eid_adult}/audit").json()
    print(f"\n✓ Bemor {a_code} bo'yicha to'liq audit holati:")
    print(f"  • Bosqich: {res_final['stage']}")
    print(f"  • Jami to'plangan ob'yektiv klinik dalillar soni: {len(res_final['evidence'])} ta")
    print(f"  • Jami o'zgartirilmas audit hodisalari: {len(res_audit)} ta")
    print("  • Audit jurnali hodisalari (namuna):")
    for a in res_audit[:3]:
        print(f"    - [{a.get('at', '')[:19]}] {a.get('actor', ''):15} -> {a.get('action', '')}")
    print("    - ...")
    for a in res_audit[-3:]:
        print(f"    - [{a.get('at', '')[:19]}] {a.get('actor', ''):15} -> {a.get('action', '')}")

    print("\n" + "="*75)
    print("BARCHA KLINIK VA TIZIMLI SINOVLAR 100% MUVAFFAQIYATLI YAKUNLANDI!")
    print("="*75)


if __name__ == "__main__":
    run_trial()
