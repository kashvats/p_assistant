from pathlib import Path

from living_assistant.task_graph import TaskGraphManager
from living_assistant.tools.planning import build_planning_tools


def test_planning_tools_form_a_working_dependency_dag(tmp_path):
    graph = TaskGraphManager(tmp_path / 'plan.sqlite3')
    tools = {tool.name: tool for tool in build_planning_tools(graph)}
    assert set(tools) == {
        'plan_add_task','plan_complete_task','plan_fail_task','plan_get_ready','plan_clear'
    }

    a = tools['plan_add_task'].handler('a', 'First step', [])
    b = tools['plan_add_task'].handler('b', 'Second step', ['a'])
    assert a['ok'] and b['ok']
    assert [x['id'] for x in tools['plan_get_ready'].handler()['ready_tasks']] == ['a']

    assert tools['plan_complete_task'].handler('a', 'done')['ok'] is True
    assert [x['id'] for x in tools['plan_get_ready'].handler()['ready_tasks']] == ['b']


def test_planning_tools_expose_valid_ollama_function_schemas(tmp_path):
    tools = build_planning_tools(tmp_path / 'plan.sqlite3')
    schemas = [tool.ollama_schema() for tool in tools]
    assert all(x['type'] == 'function' for x in schemas)
    by_name = {x['function']['name']: x['function'] for x in schemas}
    assert by_name['plan_add_task']['parameters']['required'] == ['task_id', 'description']
    assert by_name['plan_get_ready']['parameters'] == {'type':'object','properties':{}}


def test_runtime_registers_planning_tools_and_exposes_shared_graph(tmp_path, monkeypatch):
    # Isolate all default SQLite/state paths used during runtime assembly.
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'xdg'))
    import living_assistant.runtime as runtime

    rt = runtime.build_runtime(interactive=False)
    try:
        assert isinstance(rt.planner, TaskGraphManager)
        assert {'plan_add_task','plan_complete_task','plan_fail_task','plan_get_ready','plan_clear'} <= set(rt.orchestrator.tools)
        result = rt.orchestrator.tools['plan_add_task'].handler('runtime-a', 'Runtime connected task', [])
        assert result['ok'] is True
        assert rt.planner.get_task('runtime-a') is not None
    finally:
        # Close thread-local stores that expose explicit cleanup; other components are lazy.
        for obj in (rt.approvals, rt.memory, rt.sessions, rt.experiences):
            conn = getattr(obj, 'conn', None)
            if conn is not None and hasattr(conn, 'close_all'):
                conn.close_all()
