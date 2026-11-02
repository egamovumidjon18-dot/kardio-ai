"""Locust yuklama va stress sinovlari (CardioPath AI Stress Testing Suite).

Foydalanish:
    locust -f tests/load/locustfile.py --host=http://localhost:8010 --users 50 --spawn-rate 5 --run-time 1m --headless
"""
import random
import uuid
from locust import HttpUser, between, task


class ClinicDoctorUser(HttpUser):
    wait_time = between(0.2, 1.0)
    token = None

    def on_start(self):
        # Admin yoki shifokor sifatida kirish (agar auth yoqilgan bo'lsa)
        r = self.client.post("/auth/login", json={"username": "admin", "password": "Yaxshi-parol-123"})
        if r.status_code == 200:
            self.token = r.json().get("token")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(4)
    def check_health(self):
        self.client.get("/health")
        self.client.get("/health/deep")

    @task(3)
    def create_episode_and_report(self):
        ref = f"P-LOAD-{uuid.uuid4().hex[:6]}"
        r = self.client.post("/episodes", json={"patient_ref": ref, "population": "pediatric", "actor": "dr_load"})
        if r.status_code == 201:
            eid = r.json()["id"]

            # KDIGO AKI baholash
            self.client.post(
                f"/episodes/{eid}/kdigo",
                json={
                    "actor": "dr_load",
                    "baseline_creatinine": random.uniform(50.0, 90.0),
                    "current_creatinine": random.uniform(90.0, 180.0),
                    "creatinine_48h_rise": random.uniform(10.0, 45.0),
                    "urine_output_ml_kg_h": random.uniform(0.3, 1.2),
                    "urine_hours": 12.0,
                    "rrt": False,
                },
            )

            # Rasmiy hisobot (Epikriz) olish
            self.client.get(f"/episodes/{eid}/report")

    @task(1)
    def verify_audit_trail(self):
        self.client.get("/audit/verify")
