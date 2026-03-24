"""
Load Testing with Locust.
Simulates user behavior: Landing -> Login -> Upload -> Dashboard.
"""
from locust import HttpUser, task, between, events
import random
import string

class DashboardUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login before testing"""
        # Simulate login (mocked for load test)
        self.client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })

    @task(3)
    def view_landing(self):
        """View landing page (most common)"""
        self.client.get("/")
    
    @task(2)
    def view_dashboard_list(self):
        """View personal cabinet"""
        self.client.get("/dashboard")
    
    @task(1)
    def upload_file(self):
        """Upload a file (heavy operation)"""
        # Mock file upload
        files = {'file': ('test.xlsx', b'mock excel content')}
        self.client.post("/upload", files=files)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("🚀 Load test started...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("✅ Load test finished.")
