from living_assistant.tools.projects import detect_project

def test_node_detect(tmp_path):
    (tmp_path/"package.json").write_text('{"scripts":{"dev":"vite"}}')
    d = detect_project(tmp_path)
    assert "node" in d["types"]
    assert "npm run dev" in d["suggested_commands"]
