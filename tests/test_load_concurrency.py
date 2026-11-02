"""Bir vaqtning o'zida ko'p sonli so'rovlar (Parallel Concurrency & Stress) testi."""
import concurrent.futures
import time
from fastapi.testclient import TestClient

from api.main import create_app
from core.store import SqliteEpisodeStore


def test_concurrent_episode_creation_and_kdigo_stress(tmp_path):
    db_path = str(tmp_path / "concurrency_test.db")
    store = SqliteEpisodeStore(db_path)
    client = TestClient(create_app(store, None))

    num_threads = 20
    results = []

    def worker(i: int):
        # 1. Epizod ochish
        r_ep = client.post("/episodes", json={"patient_ref": f"P-CONC-{i:03d}", "population": "pediatric", "actor": f"dr_{i}"})
        if r_ep.status_code != 201:
            return False, f"Episode create failed: {r_ep.text}"
        eid = r_ep.json()["id"]

        # 2. Stage transition
        r_tr = client.post(f"/episodes/{eid}/transition", json={"from_stage": "screening", "to_stage": "workup", "author": f"dr_{i}"})
        if r_tr.status_code != 200:
            return False, f"Transition 1 failed: {r_tr.text}"
        r_tr2 = client.post(f"/episodes/{eid}/transition", json={"from_stage": "workup", "to_stage": "heart_team", "author": f"dr_{i}"})
        if r_tr2.status_code != 200:
            return False, f"Transition 2 failed: {r_tr2.text}"
        r_tr3 = client.post(f"/episodes/{eid}/transition", json={"from_stage": "heart_team", "to_stage": "procedure", "author": f"dr_{i}"})
        if r_tr3.status_code != 200:
            return False, f"Transition 3 failed: {r_tr3.text}"
        r_tr4 = client.post(f"/episodes/{eid}/transition", json={"from_stage": "procedure", "to_stage": "icu", "author": f"dr_{i}"})
        if r_tr4.status_code != 200:
            return False, f"Transition 4 failed: {r_tr4.text}"

        # 3. KDIGO AKI kiritish
        r_k = client.post(
            f"/episodes/{eid}/kdigo",
            json={
                "actor": f"dr_{i}",
                "baseline_creatinine": 60.0 + i,
                "current_creatinine": 120.0 + i,
                "urine_output_ml_kg_h": 0.5,
                "urine_hours": 12.0,
                "rrt": False,
            },
        )
        if r_k.status_code != 200:
            return False, f"KDIGO failed: {r_k.text}"

        # 4. Yozma rozilik biriktirish
        r_c = client.post(
            f"/episodes/{eid}/consent",
            json={
                "actor": f"dr_{i}",
                "clinician": f"Dr. Doctor #{i}",
                "paper_ref": f"BLANK-CONC-{i}",
                "consent_type": "treatment_and_ai",
            },
        )
        if r_c.status_code != 200:
            return False, f"Consent failed: {r_c.text}"

        # 5. Hisobotni olish
        r_rep = client.get(f"/episodes/{eid}/report")
        if r_rep.status_code != 200 or f"BLANK-CONC-{i}" not in r_rep.text:
            return False, f"Report failed: {r_rep.status_code}"

        return True, "ok"

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            ok, msg = f.result()
            results.append((ok, msg))
    dur = time.perf_counter() - t0

    # Barcha 20 ta parallel shifokor sessiyasi muvaffaqiyatli yakunlanishi kerak
    failures = [msg for ok, msg in results if not ok]
    assert not failures, f"Parallel so'rovlarda xatolar yuz berdi: {failures}"
    assert len(results) == num_threads

    # Va nihoyat, kriptografik audit jurnali zanjiri butunligini tekshiramiz
    valid, err = store.verify_audit_integrity()
    assert valid is True, f"Parallel yozishlardan keyin audit zanjiri buzildi: {err}"
