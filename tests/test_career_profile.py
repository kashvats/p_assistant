from pathlib import Path
import pytest
from living_assistant.career.profile import CareerProfileStore, CandidateProfile, ResumeParser

def test_profile_default_and_update(tmp_path):
    store = CareerProfileStore(storage_dir=tmp_path)
    profile = store.get_profile()
    assert profile.full_name == ""
    assert profile.screener.legally_authorized is True
    assert profile.screener.requires_visa_sponsorship is False
    
    updated = store.update_profile({
        "full_name": "Alex Developer",
        "email": "alex@example.com",
        "phone": "+1-555-0199",
        "linkedin_url": "https://linkedin.com/in/alexdev",
        "skills": ["Python", "FastAPI", "React"]
    })
    assert updated.full_name == "Alex Developer"
    assert updated.email == "alex@example.com"
    assert "Python" in updated.skills
    
    # Reload from disk
    reloaded_store = CareerProfileStore(storage_dir=tmp_path)
    reloaded_profile = reloaded_store.get_profile()
    assert reloaded_profile.full_name == "Alex Developer"
    assert reloaded_profile.email == "alex@example.com"
    assert "Python" in reloaded_profile.skills

def test_resume_parser_markdown_and_text(tmp_path):
    md_file = tmp_path / "resume.md"
    md_file.write_text("# John Doe\nSoftware Engineer\n- Built AI systems", encoding="utf-8")
    parser = ResumeParser()
    extracted = parser.extract_text(md_file)
    assert "John Doe" in extracted
    assert "Software Engineer" in extracted

def test_resume_parser_missing_and_empty(tmp_path):
    parser = ResumeParser()
    missing_file = tmp_path / "does_not_exist.pdf"
    res_missing = parser.extract_text(missing_file)
    assert res_missing == ""
    
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")
    assert parser.extract_text(empty_file) == ""

def test_save_resume_file(tmp_path):
    store = CareerProfileStore(storage_dir=tmp_path)
    resume_bytes = b"# My Resume\nExperienced developer."
    saved_res = store.save_resume_file("my_resume.md", resume_bytes)
    assert saved_res["ok"] is True
    saved_path = saved_res["path"]
    assert Path(saved_path).exists()
    assert Path(saved_path).name == "my_resume.md"
    
    profile = store.get_profile()
    assert profile.resume_file_path == str(saved_path)
