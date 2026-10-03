from fastapi.testclient import TestClient
import pytest
from living_assistant.api import app
from living_assistant.security.api_auth import get_api_token

def test_career_api_routes():
    # 0. Verify unauthenticated call is rejected with 401
    unauth_client = TestClient(app)
    unauth_res = unauth_client.get("/api/v1/career/profile")
    assert unauth_res.status_code == 401

    token = get_api_token()
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    
    # 1. GET profile
    res_get = client.get("/api/v1/career/profile")
    assert res_get.status_code == 200
    data = res_get.json()
    assert "profile" in data
    
    # 2. PUT profile
    res_put = client.put("/api/v1/career/profile", json={
        "full_name": "Robin Engineer",
        "email": "robin@example.com",
        "skills": ["Python", "Playwright", "FastAPI"]
    })
    assert res_put.status_code == 200
    assert res_put.json()["profile"]["full_name"] == "Robin Engineer"
    
    # 3. POST jobs analyze
    res_job = client.post("/api/v1/career/jobs/analyze", json={
        "url": "https://jobs.lever.co/mockcompany/123",
        "html_text": "<html><body><h1>Senior Platform Engineer</h1><p>Contact talent@mockcompany.com</p></body></html>"
    })
    assert res_job.status_code == 200
    job_data = res_job.json()
    assert job_data["ok"] is True
    assert job_data["company"] == "Mockcompany" or job_data["title"] == "Senior Platform Engineer"
    app_id = job_data["application_id"]
    assert "talent@mockcompany.com" in job_data["recruiter_emails"]
    
    # 4. GET applications list
    res_apps = client.get("/api/v1/career/applications")
    assert res_apps.status_code == 200
    apps_data = res_apps.json()
    assert apps_data["count"] >= 1
    assert any(a["id"] == app_id for a in apps_data["applications"])
    
    # 5. POST outreach generate
    res_outreach = client.post(f"/api/v1/career/applications/{app_id}/outreach")
    assert res_outreach.status_code == 200
    outreach_data = res_outreach.json()
    assert outreach_data["ok"] is True
    assert "outreach_email" in outreach_data
    assert outreach_data["outreach_email"]["recipient"] == "talent@mockcompany.com"

def test_career_cli_help():
    from typer.testing import CliRunner
    from living_assistant.cli import app as cli_app
    runner = CliRunner()
    result = runner.invoke(cli_app, ["career", "--help"])
    assert result.exit_code == 0
    assert "Job search, resume management" in result.stdout
