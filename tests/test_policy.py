from living_assistant.security_policy import classify_command, is_read_only_sql

def test_blocks_root_delete():
    assert not classify_command("rm -rf /").allowed

def test_blocks_defender_disable():
    assert not classify_command("Set-MpPreference -DisableRealtimeMonitoring $true").allowed

def test_sudo_needs_approval():
    d = classify_command("sudo apt update")
    assert d.allowed and d.requires_approval

def test_sql_read_only():
    assert is_read_only_sql("SELECT * FROM users LIMIT 2")
    assert is_read_only_sql("WITH x AS (SELECT 1) SELECT * FROM x")
    assert not is_read_only_sql("DELETE FROM users")
    assert not is_read_only_sql("DROP TABLE users")


def test_sql_comment_handling_cannot_hide_a_second_write_statement():
    assert is_read_only_sql('/* harmless */ SELECT 1 -- trailing comment')
    assert is_read_only_sql('-- DROP TABLE users\nSELECT 1')
    assert not is_read_only_sql('SELECT 1 -- harmless\n; DROP TABLE users')
    # Comment delimiters inside string literals are data, not comments. The real DROP
    # statement between them must therefore remain visible to the policy checker.
    assert not is_read_only_sql("SELECT '/*'; DROP TABLE users; '*/'")
    assert not is_read_only_sql("SELECT '--'; DROP TABLE users")
