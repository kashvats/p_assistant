from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace

import pytest

from living_assistant.skills.library import SkillError, SkillLibrary, _github_source, _skillhub_source, parse_skill_md
from living_assistant.skills.library_tools import build_skill_library_tools

PDF_SKILL = """---
name: pdf-tools
description: Merge, split and extract text from PDF files.
---

# PDF tools

1. Run scripts/merge.py with the input files.
"""


def _lib(tmp_path, complete=None, builtin=None):
    return SkillLibrary(tmp_path / "skills", builtin=builtin or (tmp_path / "builtin"), complete=complete)


def _skill_folder(tmp_path, text=PDF_SKILL, name="pdf"):
    folder = tmp_path / "src" / name
    (folder / "scripts").mkdir(parents=True)
    (folder / "SKILL.md").write_text(text, encoding="utf-8")
    (folder / "scripts" / "merge.py").write_text("print('merged')\n", encoding="utf-8")
    return folder


def test_install_from_a_folder_then_read_find_and_list(tmp_path):
    lib = _lib(tmp_path)
    assert lib.inspect(str(_skill_folder(tmp_path)))[0]["name"] == "pdf-tools"
    assert lib.list() == []  # inspecting installs nothing
    out = lib.install(str(_skill_folder(tmp_path, name="pdf2")))
    assert out[0]["name"] == "pdf-tools" and out[0]["files"] >= 2
    read = lib.read("pdf-tools")
    assert "Run scripts/merge.py" in read["instructions"] and "scripts/merge.py" in read["files"]
    assert lib.read("pdf-tools", file="scripts/merge.py")["content"].startswith("print")
    with pytest.raises(SkillError):
        lib.read("pdf-tools", file="../../etc/passwd")
    assert [r["name"] for r in lib.relevant("please merge these two pdf files")] == ["pdf-tools"]
    assert lib.relevant("what's the weather tomorrow") == []
    assert "skill_read" in lib.prompt_block("extract text from a PDF")
    with pytest.raises(SkillError, match="already installed"):
        lib.install(str(_skill_folder(tmp_path, name="pdf3")))
    assert lib.install(str(_skill_folder(tmp_path, name="pdf4")), force=True)[0]["name"] == "pdf-tools"


def test_archives_are_checked_and_multi_skill_repos_install_together(tmp_path):
    lib = _lib(tmp_path)
    good = tmp_path / "pack.zip"
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("repo/skills/a/SKILL.md", PDF_SKILL.replace("pdf-tools", "alpha"))
        z.writestr("repo/skills/b/SKILL.md", PDF_SKILL.replace("pdf-tools", "beta"))
        z.writestr("repo/README.md", "hi")
    assert sorted(r["name"] for r in lib.install(str(good))) == ["alpha", "beta"]
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../escape/SKILL.md", PDF_SKILL)
    with pytest.raises(SkillError, match="unsafe"):
        lib.install(str(evil))
    assert not (tmp_path / "escape").exists()
    nothing = tmp_path / "none.zip"
    with zipfile.ZipFile(nothing, "w") as z:
        z.writestr("readme.txt", "no skill here")
    with pytest.raises(SkillError, match="no SKILL.md"):
        lib.install(str(nothing))
    single = tmp_path / "SKILL.md"
    single.write_text(PDF_SKILL.replace("pdf-tools", "gamma"), encoding="utf-8")
    assert lib.install(str(single))[0]["name"] == "gamma"


def test_remove_goes_to_trash_and_restores_and_builtins_are_protected(tmp_path):
    builtin = tmp_path / "builtin" / "skill-creator"
    builtin.mkdir(parents=True)
    (builtin / "SKILL.md").write_text(PDF_SKILL.replace("pdf-tools", "skill-creator"), encoding="utf-8")
    lib = _lib(tmp_path)
    lib.install(str(_skill_folder(tmp_path)))
    assert {r["name"]: r["builtin"] for r in lib.list()} == {"pdf-tools": False, "skill-creator": True}
    removed = lib.remove("pdf-tools")
    assert [r["name"] for r in lib.list()] == ["skill-creator"] and lib.trash()[0]["trash_name"] == removed["trash_name"]
    assert lib.restore(removed["trash_name"])["restored"] == "pdf-tools" and lib.read("pdf-tools")
    with pytest.raises(SkillError, match="built-in"):
        lib.remove("skill-creator")
    with pytest.raises(SkillError, match="built in"):
        lib.edit("skill-creator", description="x")


def test_write_edit_and_learn_a_skill_from_material(tmp_path):
    asked = []

    def complete(messages, max_tokens):
        asked.append(messages)
        return ("```markdown\n---\nname: weekly-report\ndescription: Write the weekly status report from the team's notes.\n"
                "---\n\n# Weekly report\n\n1. Collect the notes.\n2. Group them by project.\n3. Write three bullet points "
                "per project and a risks section.\n```")

    lib = _lib(tmp_path, complete=complete)
    out = lib.learn("Weekly Report", "write my weekly report", "We met Monday. Steps: collect notes, group by project...")
    assert out["name"] == "weekly-report" and "Group them by project" in lib.read("weekly-report")["instructions"]
    assert "Material to learn from" in asked[0][-1]["content"]
    lib.edit("weekly-report", description="Weekly status report for the platform team.")
    assert parse_skill_md((tmp_path / "skills" / "weekly-report" / "SKILL.md").read_text())[0]["description"].startswith("Weekly status")
    with pytest.raises(SkillError, match="already installed"):
        lib.write("weekly-report", "x", "do things")
    lib2 = _lib(tmp_path / "b", complete=lambda m, n: "just some prose, not a skill")
    with pytest.raises(SkillError, match="valid SKILL.md"):
        lib2.learn("thing", "goal", "material " * 20)


def test_source_parsing_for_github_and_skillhub():
    assert _github_source("https://github.com/acme/skills/tree/main/pdf") == ("https://github.com/acme/skills.git", "main", "pdf")
    assert _github_source("https://github.com/acme/skills/blob/main/pdf/SKILL.md")[2] == "pdf"
    assert _skillhub_source("skillhub:kunlungrowth/pdf") == ("pdf", "kunlungrowth")
    assert _skillhub_source("https://skillhub.cn/skills/acme/pdf-tools") == ("pdf-tools", "acme")
    assert _skillhub_source("https://example.com/x") is None
    with pytest.raises(SkillError):
        _skillhub_source("skillhub:a/b/c")


def test_skillhub_install_downloads_the_package(tmp_path, monkeypatch):
    import living_assistant.skills.library as L

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("pdf/SKILL.md", PDF_SKILL)
    urls = []
    monkeypatch.setattr(L, "_http_get", lambda url, **k: urls.append(url) or buf.getvalue())
    out = _lib(tmp_path).install("skillhub:kunlungrowth/pdf")
    assert out[0]["name"] == "pdf" and "download?slug=pdf" in urls[0]  # SkillHub's slug names the skill
    monkeypatch.setattr(L, "_http_get", lambda url, **k: json.dumps({"results": [
        {"slug": "pdf", "displayName": "PDF", "summary": "PDF tools", "namespace": {"handle": "kunlungrowth"}}]}).encode())
    assert L.skillhub_search("pdf")[0]["source"] == "skillhub:kunlungrowth/pdf"


def test_chat_tools_learn_from_the_conversation_and_ask_before_removing(tmp_path):
    lib = _lib(tmp_path, complete=lambda m, n: "---\nname: x\ndescription: Rename photos by date taken.\n---\n\n"
                                                "# Rename photos\n\n1. Read EXIF dates.\n2. Rename files to YYYY-MM-DD_n.jpg.\n"
                                                "3. Show the user the list before renaming.\n")
    requests = []
    approval = SimpleNamespace(request=lambda *a: requests.append(a) or {"allowed": False, "pending": True, "approval_id": "a1"})
    tools = {t.name: t.handler for t in build_skill_library_tools(
        lib, approval=approval, session_text=lambda sid: f"user: rename my photos by date ({sid})")}
    out = tools["skill_learn"](name="rename-photos", from_conversation=True, _session_id="s1")
    assert out["ok"] and out["name"] == "rename-photos"
    assert tools["skill_learn"](name="other", from_conversation=True)["ok"] is False  # no conversation
    assert tools["skill_read"](name="rename-photos")["ok"]
    blocked = tools["skill_remove"](name="rename-photos")
    assert blocked["approval_required"] and requests and lib.read("rename-photos")  # nothing removed yet
    assert tools["skill_read"](name="missing")["ok"] is False


def test_the_orchestrator_offers_matching_skills_and_passes_the_session():
    from living_assistant.agents.orchestrator import Orchestrator

    lib = SimpleNamespace(prompt_block=lambda text: "\n\n[INSTALLED SKILLS THAT MAY FIT THIS REQUEST]\n- pdf-tools: PDFs")
    orch = Orchestrator.__new__(Orchestrator)
    orch.skill_library, orch.skills = lib, None
    assert "pdf-tools" in orch._skill_context("merge pdfs")
    seen = {}
    tool = SimpleNamespace(handler=lambda name, _session_id=None: seen.update(name=name, sid=_session_id) or {"ok": True})
    assert Orchestrator._wants_session(tool) and not Orchestrator._wants_session(SimpleNamespace(handler=lambda name: 1))


def test_dashboard_routes_install_read_edit_remove_and_restore(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import living_assistant.api as api

    lib = _lib(tmp_path)
    monkeypatch.setattr(api, "runtime", SimpleNamespace(skill_library=lib))
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "t")
    c = TestClient(api.app, headers={"Authorization": "Bearer t"})
    src = str(_skill_folder(tmp_path))
    assert c.post("/skill-library/preview", json={"source": src}).json()["skills"][0]["name"] == "pdf-tools"
    assert c.post("/skill-library/install", json={"source": src}).json()["installed"][0]["name"] == "pdf-tools"
    assert c.post("/skill-library/install", json={"source": src}).status_code == 400  # already installed
    assert "merge.py" in c.get("/skill-library/pdf-tools").json()["instructions"]
    assert c.get("/skill-library/search", params={"q": "merge pdf", "hub": False}).json()["installed"][0]["name"] == "pdf-tools"
    assert c.put("/skill-library/pdf-tools", json={"description": "PDF helper"}).json()["ok"]
    gone = c.delete("/skill-library/pdf-tools").json()
    listing = c.get("/skill-library").json()
    assert listing["skills"] == [] and listing["trash"][0]["trash_name"] == gone["trash_name"]
    assert c.post(f"/skill-library/trash/{gone['trash_name']}/restore").json()["restored"] == "pdf-tools"
    assert c.get("/skill-library/nope").status_code == 404
    assert c.get("/skill-library", headers={"Authorization": "Bearer wrong"}).status_code == 401
