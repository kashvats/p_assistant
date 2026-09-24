# Module: src

> Generated navigation map. Source code is authoritative.

## `src/living_assistant/__init__.py`

- language: `py`
- size: 24 bytes
- hash: `7d0e9bad8349`

## `src/living_assistant/agents/__init__.py`

- language: `py`
- size: 270 bytes
- hash: `83398b2e6bf3`
- imports:
  - `agents`

## `src/living_assistant/agents/agents.py`

- language: `py`
- size: 5453 bytes
- hash: `382296a05b33`
- symbols:
  - `class` `SpecialistRouter` — line 13
  - `method` `SpecialistRouter.__init__` — line 14
  - `method` `SpecialistRouter.delegate` — line 27
- imports:
  - `__future__`
  - `contextlib`
  - `living_assistant.agents.prompts`
  - `living_assistant.core.model_provider`
  - `living_assistant.system.resource_manager`
  - `queue`
  - `re`
  - `threading`
  - `time`

## `src/living_assistant/agents/aggregator.py`

- language: `py`
- size: 6979 bytes
- hash: `d797457e3c50`
- symbols:
  - `class` `AggregatedResult` — line 8
  - `class` `Aggregator` — line 26
  - `method` `Aggregator.__init__` — line 27
  - `method` `Aggregator.aggregate` — line 32
- imports:
  - `contextlib`
  - `json`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.models`
  - `pydantic`
  - `typing`

## `src/living_assistant/agents/custom/__init__.py`

- language: `py`
- size: 1640 bytes
- hash: `a1f51a893815`
- imports:
  - `__future__`
  - `living_assistant.agents.custom.creator`
  - `living_assistant.agents.custom.delegation`
  - `living_assistant.agents.custom.examples`
  - `living_assistant.agents.custom.manager`
  - `living_assistant.agents.custom.manifest`
  - `living_assistant.agents.custom.memory`
  - `living_assistant.agents.custom.package`
  - `living_assistant.agents.custom.runner`
  - `living_assistant.agents.custom.store`
  - `living_assistant.agents.custom.tools`

## `src/living_assistant/agents/custom/creator.py`

- language: `py`
- size: 7632 bytes
- hash: `bdc10f7ba9ea`
- symbols:
  - `class` `AgentCreator` — line 21
  - `method` `AgentCreator.__init__` — line 24
  - `method` `AgentCreator._slugify` — line 38
  - `method` `AgentCreator._heuristic_agent_draft` — line 44
  - `method` `AgentCreator.create_draft` — line 128
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.agents.custom.manifest`
  - `living_assistant.agents.custom.package`
  - `living_assistant.agents.custom.store`
  - `living_assistant.tools.registry`
  - `pathlib`
  - `re`
  - `typing`

## `src/living_assistant/agents/custom/delegation.py`

- language: `py`
- size: 2978 bytes
- hash: `2a06a040e208`
- symbols:
  - `class` `DelegationViolation` — line 9
  - `class` `AgentDelegationCoordinator` — line 13
  - `method` `AgentDelegationCoordinator.__init__` — line 16
  - `method` `AgentDelegationCoordinator.validate_delegation` — line 21
- imports:
  - `__future__`
  - `living_assistant.agents.custom.manifest`
  - `threading`
  - `typing`

## `src/living_assistant/agents/custom/examples.py`

- language: `py`
- size: 5726 bytes
- hash: `9169b1c5d67e`
- symbols:
  - `function` `get_research_agent_manifest` — line 12
  - `function` `get_file_assistant_manifest` — line 54
  - `function` `get_planner_agent_manifest` — line 96
- imports:
  - `__future__`
  - `living_assistant.agents.custom.manifest`

## `src/living_assistant/agents/custom/manager.py`

- language: `py`
- size: 9817 bytes
- hash: `ec17aacc2f15`
- symbols:
  - `function` `default_agents_dir` — line 22
  - `class` `AgentManager` — line 26
  - `method` `AgentManager.__init__` — line 29
  - `method` `AgentManager._seed_builtins_if_needed` — line 65
  - `method` `AgentManager.list_agents` — line 85
  - `method` `AgentManager.get_agent` — line 107
  - `method` `AgentManager.create_draft` — line 128
  - `method` `AgentManager.update_agent` — line 131
  - `method` `AgentManager.activate_agent` — line 144
  - `method` `AgentManager.disable_agent` — line 177
  - `method` `AgentManager.archive_agent` — line 181
  - `method` `AgentManager.execute_agent` — line 185
  - `method` `AgentManager.export_agent` — line 222
  - `method` `AgentManager.import_agent` — line 229
- imports:
  - `__future__`
  - `datetime`
  - `living_assistant.agents.custom.creator`
  - `living_assistant.agents.custom.delegation`
  - `living_assistant.agents.custom.examples`
  - `living_assistant.agents.custom.manifest`
  - `living_assistant.agents.custom.package`
  - `living_assistant.agents.custom.runner`
  - `living_assistant.agents.custom.store`
  - `living_assistant.core.config`
  - `living_assistant.tools.registry`
  - `pathlib`
  - `typing`

## `src/living_assistant/agents/custom/manifest.py`

- language: `py`
- size: 3916 bytes
- hash: `b99c014a4502`
- symbols:
  - `class` `AgentLimits` — line 9
  - `class` `AgentDelegationPolicy` — line 18
  - `class` `AgentMemoryScope` — line 25
  - `class` `AgentModelPreference` — line 35
  - `class` `AgentProvenance` — line 41
  - `class` `AgentManifest` — line 48
  - `method` `AgentManifest.permission_hash` — line 67
  - `method` `AgentManifest.validate_against_system` — line 79
  - `method` `AgentManifest.from_json` — line 104
- imports:
  - `__future__`
  - `hashlib`
  - `json`
  - `pydantic`
  - `typing`

## `src/living_assistant/agents/custom/memory.py`

- language: `py`
- size: 3719 bytes
- hash: `6239be75aa45`
- symbols:
  - `class` `MemoryScopeViolation` — line 8
  - `class` `AgentScopedMemory` — line 12
  - `method` `AgentScopedMemory.__init__` — line 15
  - `method` `AgentScopedMemory._check_read` — line 28
  - `method` `AgentScopedMemory._check_write` — line 35
  - `method` `AgentScopedMemory.read` — line 42
  - `method` `AgentScopedMemory.write` — line 54
  - `method` `AgentScopedMemory.list_keys` — line 68
  - `method` `AgentScopedMemory.get_prompt_context` — line 76
- imports:
  - `__future__`
  - `living_assistant.agents.custom.manifest`
  - `living_assistant.agents.custom.store`
  - `typing`

## `src/living_assistant/agents/custom/package.py`

- language: `py`
- size: 7627 bytes
- hash: `3759189de6e6`
- symbols:
  - `class` `AgentPackageError` — line 15
  - `class` `AgentPackage` — line 19
  - `method` `AgentPackage.__init__` — line 22
  - `method` `AgentPackage.save` — line 36
  - `method` `AgentPackage.load` — line 59
  - `method` `AgentPackage.deterministic_hash` — line 90
  - `method` `AgentPackage.create_snapshot` — line 104
  - `method` `AgentPackage.export_zip` — line 120
  - `method` `AgentPackage.import_zip` — line 136
- imports:
  - `__future__`
  - `hashlib`
  - `json`
  - `living_assistant.agents.custom.manifest`
  - `os`
  - `pathlib`
  - `shutil`
  - `tempfile`
  - `typing`
  - `zipfile`

## `src/living_assistant/agents/custom/runner.py`

- language: `py`
- size: 10768 bytes
- hash: `c16713633ade`
- symbols:
  - `class` `AgentExecutionError` — line 17
  - `class` `AgentExecutor` — line 21
  - `method` `AgentExecutor.__init__` — line 24
  - `method` `AgentExecutor.execute` — line 40
- imports:
  - `__future__`
  - `collections`
  - `datetime`
  - `hashlib`
  - `json`
  - `living_assistant.agents.custom.delegation`
  - `living_assistant.agents.custom.manifest`
  - `living_assistant.agents.custom.memory`
  - `living_assistant.agents.custom.store`
  - `living_assistant.tools.registry`
  - `time`
  - `typing`

## `src/living_assistant/agents/custom/store.py`

- language: `py`
- size: 15928 bytes
- hash: `5cd61d1f6d92`
- symbols:
  - `class` `AgentStore` — line 85
  - `method` `AgentStore.__init__` — line 88
  - `method` `AgentStore._init_schema` — line 97
  - `method` `AgentStore.close` — line 101
  - `method` `AgentStore.register_agent` — line 109
  - `method` `AgentStore.get_lifecycle` — line 171
  - `method` `AgentStore.set_state` — line 177
  - `method` `AgentStore.approve_agent` — line 185
  - `method` `AgentStore.is_approved` — line 210
  - `method` `AgentStore.list_agents` — line 231
  - `method` `AgentStore.get_versions` — line 242
  - `method` `AgentStore.record_execution_start` — line 254
  - `method` `AgentStore.record_execution_finish` — line 285
  - `method` `AgentStore.get_executions` — line 321
  - `method` `AgentStore.record_action` — line 362
  - `method` `AgentStore.set_memory` — line 408
  - `method` `AgentStore.get_memory` — line 423
  - `method` `AgentStore.list_memory` — line 437
  - `method` `AgentStore.clear_memory` — line 451
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.agents.custom.manifest`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `pathlib`
  - `sqlite3`
  - `typing`
  - `uuid`

## `src/living_assistant/agents/custom/tools.py`

- language: `py`
- size: 4647 bytes
- hash: `16ea00a28004`
- symbols:
  - `function` `build_agent_tools` — line 8
- imports:
  - `__future__`
  - `living_assistant.agents.custom.manager`
  - `living_assistant.tools.base`
  - `typing`

## `src/living_assistant/agents/orchestrator.py`

- language: `py`
- size: 57133 bytes
- hash: `db3db457a114`
- symbols:
  - `class` `_ToolDocument` — line 41
  - `class` `DynamicToolRouter` — line 51
  - `method` `DynamicToolRouter.__init__` — line 66
  - `method` `DynamicToolRouter._normalize_text` — line 75
  - `method` `DynamicToolRouter._term_variants` — line 84
  - `method` `DynamicToolRouter._tokenize` — line 117
  - `method` `DynamicToolRouter._flatten_schema` — line 127
  - `method` `DynamicToolRouter._safe_schema` — line 146
  - `method` `DynamicToolRouter._signature` — line 153
  - `method` `DynamicToolRouter.refresh` — line 165
  - `method` `DynamicToolRouter._char_ngrams` — line 228
  - `method` `DynamicToolRouter._fuzzy_score` — line 234
  - `method` `DynamicToolRouter.search` — line 258
  - `class` `Orchestrator` — line 330
  - `method` `Orchestrator.__init__` — line 331
  - `method` `Orchestrator._duplicate_tool_names` — line 438
  - `method` `Orchestrator._register_internal_tool` — line 442
  - `method` `Orchestrator._delegate` — line 453
  - `method` `Orchestrator._tool_catalog_search` — line 485
  - `method` `Orchestrator._merge_tool_names` — line 503
  - `method` `Orchestrator._initial_tool_names` — line 520
  - `method` `Orchestrator._followup_tool_names` — line 576
  - `method` `Orchestrator._expand_from_discovery_result` — line 605
  - `method` `Orchestrator._schemas_for` — line 623
  - `method` `Orchestrator._routing_context` — line 633
  - `method` `Orchestrator._model_lease` — line 649
  - `method` `Orchestrator._publish` — line 663
  - `method` `Orchestrator._history_start` — line 671
  - `method` `Orchestrator._history_tool` — line 692
  - `method` `Orchestrator._history_finish` — line 715
  - `method` `Orchestrator._record_model_usage` — line 736
  - `method` `Orchestrator._skill_context` — line 762
  - `method` `Orchestrator._session_context` — line 780
  - `method` `Orchestrator._project_hint` — line 804
  - `method` `Orchestrator._experience_context` — line 821
  - `method` `Orchestrator._finish` — line 833
  - `method` `Orchestrator._prepare` — line 838
  - `method` `Orchestrator._execute_tool` — line 878
  - `method` `Orchestrator._serialized_tool_result` — line 920
  - `method` `Orchestrator._update_active_tools_after_result` — line 928
  - `method` `Orchestrator.run` — line 952
  - `method` `Orchestrator.run_stream` — line 1230
- imports:
  - `__future__`
  - `collections`
  - `contextlib`
  - `dataclasses`
  - `difflib`
  - `inspect`
  - `json`
  - `living_assistant.agents.agents`
  - `living_assistant.agents.prompts`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.skills`
  - `living_assistant.core.typesafe`
  - `living_assistant.security.security_utils`
  - `living_assistant.system.resource_manager`
  - `living_assistant.tools.base`
  - `math`
  - `pathlib`
  - `re`
  - `time`
  - `typing`

## `src/living_assistant/agents/orchestrator_teams.py`

- language: `py`
- size: 4137 bytes
- hash: `ddd294e4f7d2`
- symbols:
  - `function` `dispatch_to_teams` — line 8
- imports:
  - `living_assistant.agents.aggregator`
  - `living_assistant.core.models`
  - `logging`

## `src/living_assistant/agents/prompts.py`

- language: `py`
- size: 4680 bytes
- hash: `5bf652731736`

## `src/living_assistant/agents/task_graph.py`

- language: `py`
- size: 3823 bytes
- hash: `493e41400b23`
- symbols:
  - `class` `TaskNode` — line 9
  - `class` `TaskGraphManager` — line 18
  - `method` `TaskGraphManager.__init__` — line 19
  - `method` `TaskGraphManager._init_db` — line 23
  - `method` `TaskGraphManager.add_task` — line 38
  - `method` `TaskGraphManager.get_task` — line 57
  - `method` `TaskGraphManager.update_task_status` — line 72
  - `method` `TaskGraphManager.get_ready_tasks` — line 80
  - `method` `TaskGraphManager.clear_graph` — line 97
- imports:
  - `dataclasses`
  - `json`
  - `pathlib`
  - `sqlite3`
  - `time`
  - `typing`

## `src/living_assistant/aggregator.py`

- language: `py`
- size: 257 bytes
- hash: `6bfe3bfbbf54`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/api.py`

- language: `py`
- size: 7474 bytes
- hash: `5fa0051fa1f5`
- symbols:
  - `function` `_allowed_hostnames` — line 58
  - `function` `_host_only` — line 67
  - `function` `_origin_is_local_or_same` — line 74
  - `async-function` `local_api_boundary` — line 85
  - `function` `_rt` — line 106
  - `function` `_auth` — line 110
  - `function` `health` — line 127
  - `function` `status` — line 132
  - `function` `platform_status_endpoint` — line 171
  - `function` `platform_service_status_endpoint` — line 179
- routes:
  - `GET /health` → `health` — line 127
  - `GET /status` → `status` — line 132
  - `GET /platform/status` → `platform_status_endpoint` — line 171
  - `GET /platform/service-status` → `platform_service_status_endpoint` — line 179
- imports:
  - `__future__`
  - `fastapi`
  - `fastapi.responses`
  - `hmac`
  - `living_assistant.api_routes.agents`
  - `living_assistant.api_routes.assistant`
  - `living_assistant.api_routes.desktop`
  - `living_assistant.api_routes.improvements`
  - `living_assistant.api_routes.integrations`
  - `living_assistant.api_routes.models`
  - `living_assistant.api_routes.peers`
  - `living_assistant.api_routes.personal`
  - `living_assistant.api_routes.schemas`
  - `living_assistant.api_routes.security`
  - `living_assistant.api_routes.skills`
  - `living_assistant.api_routes.ui`
  - `living_assistant.api_routes.workspace`
  - `living_assistant.core.runtime`
  - `living_assistant.security.api_auth`
  - `living_assistant.system.platform_hardening`
  - `os`
  - `urllib.parse`

## `src/living_assistant/api_auth.py`

- language: `py`
- size: 257 bytes
- hash: `9d219b0711a2`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/api_routes/__init__.py`

- language: `py`
- size: 58 bytes
- hash: `7f55c2bc60d4`

## `src/living_assistant/api_routes/agents.py`

- language: `py`
- size: 6132 bytes
- hash: `846777d0adda`
- symbols:
  - `class` `AgentDraftRequest` — line 13
  - `class` `UpdateAgentRequest` — line 18
  - `class` `ExecuteAgentRequest` — line 23
  - `class` `ImportAgentZipRequest` — line 30
  - `function` `list_agents` — line 35
  - `function` `create_draft` — line 45
  - `function` `get_agent` — line 61
  - `function` `update_agent` — line 74
  - `function` `activate_agent` — line 92
  - `function` `disable_agent` — line 106
  - `function` `execute_agent` — line 116
  - `function` `export_agent` — line 140
  - `function` `import_agent` — line 163
- routes:
  - `POST /draft` → `create_draft` — line 45
  - `GET /{agent_id}` → `get_agent` — line 61
  - `PUT /{agent_id}` → `update_agent` — line 74
  - `POST /{agent_id}/activate` → `activate_agent` — line 92
  - `POST /{agent_id}/disable` → `disable_agent` — line 106
  - `POST /{agent_id}/execute` → `execute_agent` — line 116
  - `GET /{agent_id}/export` → `export_agent` — line 140
  - `POST /import` → `import_agent` — line 163
- imports:
  - `__future__`
  - `base64`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `pydantic`
  - `typing`

## `src/living_assistant/api_routes/assistant.py`

- language: `py`
- size: 5099 bytes
- hash: `01faa652b5c6`
- symbols:
  - `function` `_has_screen_intent` — line 22
  - `function` `_model_http_error` — line 26
  - `function` `_sse` — line 37
  - `function` `ask` — line 53
  - `function` `activity` — line 92
  - `function` `activity_stream` — line 102
  - `function` `chat_stream` — line 131
- routes:
  - `POST /ask` → `ask` — line 53
  - `GET /activity` → `activity` — line 92
  - `GET /activity/stream` → `activity_stream` — line 102
  - `POST /chat/stream` → `chat_stream` — line 131
- imports:
  - `__future__`
  - `fastapi`
  - `fastapi.responses`
  - `json`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`
  - `living_assistant.core.model_provider`
  - `re`

## `src/living_assistant/api_routes/dependencies.py`

- language: `py`
- size: 561 bytes
- hash: `daae7187c038`
- symbols:
  - `function` `runtime` — line 6
  - `function` `authorize` — line 14
- imports:
  - `__future__`
  - `living_assistant.core.runtime`

## `src/living_assistant/api_routes/desktop.py`

- language: `py`
- size: 2137 bytes
- hash: `584103f1de04`
- symbols:
  - `function` `desktop_status` — line 12
  - `function` `desktop_monitors` — line 18
  - `function` `desktop_windows` — line 24
  - `function` `desktop_analyze_screen` — line 30
  - `function` `desktop_screen_access` — line 56
- routes:
  - `GET /desktop/status` → `desktop_status` — line 12
  - `GET /desktop/monitors` → `desktop_monitors` — line 18
  - `GET /desktop/windows` → `desktop_windows` — line 24
  - `POST /desktop/analyze-screen` → `desktop_analyze_screen` — line 30
  - `POST /desktop/screen-access` → `desktop_screen_access` — line 56
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`

## `src/living_assistant/api_routes/improvements.py`

- language: `py`
- size: 8557 bytes
- hash: `db13c90e5103`
- symbols:
  - `function` `improvements` — line 19
  - `function` `improvement_apply` — line 30
  - `function` `improvement_rollback` — line 39
  - `function` `improvement_suites` — line 48
  - `function` `improvement_suite_add` — line 54
  - `function` `improvement_suite_delete` — line 79
  - `function` `improvement_evaluations` — line 88
  - `function` `improvement_evaluation_get` — line 99
  - `function` `improvement_evaluate` — line 111
  - `function` `sandbox_status` — line 134
  - `function` `canaries` — line 144
  - `function` `canary_get` — line 153
  - `function` `canary_run` — line 165
  - `function` `improvement_promote` — line 187
  - `function` `improvement_revert` — line 196
  - `function` `experiences` — line 205
  - `function` `experience_search` — line 220
  - `function` `experience_patterns` — line 237
  - `function` `experience_stats` — line 247
  - `function` `experience_get` — line 253
  - `function` `experience_record` — line 265
  - `function` `experience_verify` — line 286
  - `function` `experience_confirm` — line 300
  - `function` `experience_reject` — line 310
- routes:
  - `GET /improvements` → `improvements` — line 19
  - `POST /improvements/{proposal_id}/apply` → `improvement_apply` — line 30
  - `POST /improvements/{proposal_id}/rollback` → `improvement_rollback` — line 39
  - `GET /improvement-suites` → `improvement_suites` — line 48
  - `POST /improvement-suites` → `improvement_suite_add` — line 54
  - `DELETE /improvement-suites/{name}` → `improvement_suite_delete` — line 79
  - `GET /improvement-evaluations` → `improvement_evaluations` — line 88
  - `GET /improvement-evaluations/{evaluation_id}` → `improvement_evaluation_get` — line 99
  - `POST /improvements/{proposal_id}/evaluate` → `improvement_evaluate` — line 111
  - `GET /sandbox/status` → `sandbox_status` — line 134
  - `GET /canaries` → `canaries` — line 144
  - `GET /canaries/{canary_id}` → `canary_get` — line 153
  - `POST /improvement-evaluations/{evaluation_id}/canary` → `canary_run` — line 165
  - `POST /improvement-evaluations/{evaluation_id}/promote` → `improvement_promote` — line 187
  - `POST /improvement-evaluations/{evaluation_id}/revert` → `improvement_revert` — line 196
  - `GET /experiences` → `experiences` — line 205
  - `GET /experiences/search` → `experience_search` — line 220
  - `GET /experiences/patterns` → `experience_patterns` — line 237
  - `GET /experiences/stats` → `experience_stats` — line 247
  - `GET /experiences/{experience_id}` → `experience_get` — line 253
  - `POST /experiences` → `experience_record` — line 265
  - `POST /experiences/{experience_id}/verify` → `experience_verify` — line 286
  - `POST /experiences/{experience_id}/confirm` → `experience_confirm` — line 300
  - `DELETE /experiences/{experience_id}` → `experience_reject` — line 310
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`

## `src/living_assistant/api_routes/integrations.py`

- language: `py`
- size: 6949 bytes
- hash: `50872a2e0be2`
- symbols:
  - `function` `voice_status` — line 21
  - `function` `voice_ask` — line 34
  - `function` `voice_hands_free` — line 84
  - `function` `voice_enabled` — line 126
  - `function` `browser_sessions` — line 141
  - `function` `browser_session_start` — line 147
  - `function` `browser_session_navigate` — line 161
  - `function` `browser_session_interact` — line 171
  - `function` `browser_session_close` — line 186
  - `function` `connectors` — line 195
  - `function` `connector_status` — line 201
  - `function` `connector_call` — line 210
- routes:
  - `GET /voice/status` → `voice_status` — line 21
  - `POST /voice/ask` → `voice_ask` — line 34
  - `POST /voice/hands-free` → `voice_hands_free` — line 84
  - `POST /voice/enabled` → `voice_enabled` — line 126
  - `GET /browser/sessions` → `browser_sessions` — line 141
  - `POST /browser/sessions` → `browser_session_start` — line 147
  - `POST /browser/sessions/{name}/navigate` → `browser_session_navigate` — line 161
  - `POST /browser/sessions/{name}/interact` → `browser_session_interact` — line 171
  - `DELETE /browser/sessions/{name}` → `browser_session_close` — line 186
  - `GET /connectors` → `connectors` — line 195
  - `GET /connectors/{name}/status` → `connector_status` — line 201
  - `POST /connectors/{name}/call` → `connector_call` — line 210
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`
  - `threading`

## `src/living_assistant/api_routes/models.py`

- language: `py`
- size: 4230 bytes
- hash: `b02d1621b73f`
- symbols:
  - `function` `model_status` — line 14
  - `function` `model_select` — line 25
  - `function` `model_preload` — line 61
  - `function` `model_unload` — line 76
  - `function` `model_local_catalog` — line 85
  - `function` `model_pull` — line 94
  - `function` `model_delete` — line 103
  - `function` `model_usage` — line 111
- routes:
  - `GET /models/status` → `model_status` — line 14
  - `POST /models/select` → `model_select` — line 25
  - `POST /models/preload` → `model_preload` — line 61
  - `POST /models/unload` → `model_unload` — line 76
  - `GET /models/local` → `model_local_catalog` — line 85
  - `POST /models/pull` → `model_pull` — line 94
  - `POST /models/delete` → `model_delete` — line 103
  - `GET /models/usage` → `model_usage` — line 111
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`
  - `living_assistant.core.config`
  - `living_assistant.core.model_provider`

## `src/living_assistant/api_routes/peers.py`

- language: `py`
- size: 911 bytes
- hash: `54ac8cce5d74`
- symbols:
  - `function` `peers_list` — line 12
  - `function` `peer_delegate` — line 18
- routes:
  - `GET /peers` → `peers_list` — line 12
  - `POST /peer/delegate` → `peer_delegate` — line 18
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`

## `src/living_assistant/api_routes/personal.py`

- language: `py`
- size: 4518 bytes
- hash: `205c432353c9`
- symbols:
  - `function` `events` — line 17
  - `function` `todos` — line 26
  - `function` `todo_add` — line 32
  - `function` `todo_complete` — line 41
  - `function` `calendar` — line 50
  - `function` `calendar_add` — line 60
  - `function` `calendar_cancel` — line 75
  - `function` `briefing` — line 84
  - `function` `personal` — line 98
  - `function` `focus` — line 108
  - `function` `focus_stop` — line 117
  - `function` `quiet` — line 126
  - `function` `sessions` — line 139
  - `function` `session_get` — line 148
  - `function` `session_delete` — line 161
  - `function` `queued_notifications` — line 170
  - `function` `flush_notifications` — line 176
- routes:
  - `GET /events` → `events` — line 17
  - `GET /todos` → `todos` — line 26
  - `POST /todos` → `todo_add` — line 32
  - `POST /todos/{todo_id}/complete` → `todo_complete` — line 41
  - `GET /calendar` → `calendar` — line 50
  - `POST /calendar` → `calendar_add` — line 60
  - `DELETE /calendar/{event_id}` → `calendar_cancel` — line 75
  - `GET /briefing/{kind}` → `briefing` — line 84
  - `GET /personal` → `personal` — line 98
  - `POST /personal/focus` → `focus` — line 108
  - `DELETE /personal/focus` → `focus_stop` — line 117
  - `POST /personal/quiet` → `quiet` — line 126
  - `GET /sessions` → `sessions` — line 139
  - `GET /sessions/{session_id}` → `session_get` — line 148
  - `DELETE /sessions/{session_id}` → `session_delete` — line 161
  - `GET /notifications/queued` → `queued_notifications` — line 170
  - `POST /notifications/flush` → `flush_notifications` — line 176
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`

## `src/living_assistant/api_routes/schemas.py`

- language: `py`
- size: 4484 bytes
- hash: `37983fdc11ec`
- symbols:
  - `class` `AskRequest` — line 6
  - `class` `ApprovalDecision` — line 12
  - `class` `TodoRequest` — line 16
  - `class` `BrowserStartRequest` — line 21
  - `class` `BrowserInteractRequest` — line 28
  - `class` `BrowserNavigateRequest` — line 34
  - `class` `CalendarEventRequest` — line 38
  - `class` `FocusRequest` — line 46
  - `class` `QuietRequest` — line 51
  - `class` `IntegrityBaselineRequest` — line 57
  - `class` `EvaluationSuiteRequest` — line 64
  - `class` `SecurityPathRequest` — line 78
  - `class` `BackupBaselineCreateRequest` — line 84
  - `class` `ImprovementEvaluateRequest` — line 89
  - `class` `CanaryRequest` — line 102
  - `class` `ExperienceRecordRequest` — line 115
  - `class` `ExperienceVerifyRequest` — line 128
  - `class` `ExperienceConfirmRequest` — line 133
  - `class` `ConnectorCallRequest` — line 137
  - `class` `ModelRequest` — line 142
  - `class` `ModelDeleteRequest` — line 146
  - `class` `EnabledRequest` — line 151
  - `class` `VoiceAskRequest` — line 155
  - `class` `DesktopAnalyzeRequest` — line 161
  - `class` `PeerDelegateRequest` — line 170
- imports:
  - `__future__`
  - `pydantic`

## `src/living_assistant/api_routes/security.py`

- language: `py`
- size: 13502 bytes
- hash: `c329059aa8f3`
- symbols:
  - `function` `approvals` — line 22
  - `function` `approval_decide` — line 31
  - `function` `quarantine` — line 41
  - `function` `quarantine_item` — line 47
  - `function` `quarantine_scan` — line 60
  - `function` `security_summary` — line 80
  - `function` `security_posture` — line 86
  - `function` `security_findings` — line 95
  - `function` `security_finding_resolve` — line 107
  - `function` `security_startup` — line 124
  - `function` `security_startup_capture` — line 130
  - `function` `security_network` — line 144
  - `function` `security_network_capture` — line 150
  - `function` `security_integrity` — line 164
  - `function` `security_integrity_add` — line 170
  - `function` `security_integrity_check` — line 193
  - `function` `security_integrity_refresh` — line 202
  - `function` `security_integrity_remove` — line 219
  - `function` `security_processes_triage` — line 236
  - `function` `security_network_activity` — line 245
  - `function` `security_process` — line 254
  - `function` `security_process_contain` — line 263
  - `function` `security_sensors_status` — line 272
  - `function` `security_sensors_events` — line 278
  - `function` `security_sensors_correlations` — line 287
  - `function` `security_sensors_dns` — line 296
  - `function` `security_sensors_tls` — line 305
  - `function` `security_sensors_yara` — line 314
  - `function` `security_sensors_reputation` — line 327
  - `function` `security_sensors_reputation_process` — line 337
  - `function` `security_sensors_binary_assess` — line 346
  - `function` `security_sensors_binary_trust` — line 356
  - `function` `security_sensors_binary_check` — line 369
  - `function` `security_sensors_usb` — line 377
  - `function` `security_sensors_usb_baseline` — line 383
  - `function` `security_sensors_extensions` — line 391
  - `function` `security_sensors_extensions_baseline` — line 399
  - `function` `security_sensors_backups` — line 407
  - `function` `security_sensors_backup_create` — line 413
  - `function` `security_sensors_backup_check` — line 426
  - `function` `security_sensors_network_isolate` — line 435
  - `function` `security_sensors_network_restore` — line 443
- routes:
  - `GET /approvals` → `approvals` — line 22
  - `POST /approvals/{approval_id}` → `approval_decide` — line 31
  - `GET /quarantine` → `quarantine` — line 41
  - `GET /quarantine/{item_id}` → `quarantine_item` — line 47
  - `POST /quarantine/{item_id}/scan` → `quarantine_scan` — line 60
  - `GET /security/summary` → `security_summary` — line 80
  - `GET /security/posture` → `security_posture` — line 86
  - `GET /security/findings` → `security_findings` — line 95
  - `POST /security/findings/{finding_id}/resolve` → `security_finding_resolve` — line 107
  - `GET /security/startup` → `security_startup` — line 124
  - `POST /security/startup/capture` → `security_startup_capture` — line 130
  - `GET /security/network` → `security_network` — line 144
  - `POST /security/network/capture` → `security_network_capture` — line 150
  - `GET /security/integrity` → `security_integrity` — line 164
  - `POST /security/integrity` → `security_integrity_add` — line 170
  - `GET /security/integrity/{name}/check` → `security_integrity_check` — line 193
  - `POST /security/integrity/{name}/refresh` → `security_integrity_refresh` — line 202
  - `DELETE /security/integrity/{name}` → `security_integrity_remove` — line 219
  - `GET /security/processes/triage` → `security_processes_triage` — line 236
  - `GET /security/network/activity` → `security_network_activity` — line 245
  - `GET /security/process/{pid}` → `security_process` — line 254
  - `POST /security/process/{pid}/contain` → `security_process_contain` — line 263
  - `GET /security/sensors/status` → `security_sensors_status` — line 272
  - `GET /security/sensors/events` → `security_sensors_events` — line 278
  - `GET /security/sensors/correlations` → `security_sensors_correlations` — line 287
  - `GET /security/sensors/dns` → `security_sensors_dns` — line 296
  - `GET /security/sensors/tls` → `security_sensors_tls` — line 305
  - `POST /security/sensors/yara` → `security_sensors_yara` — line 314
  - `POST /security/sensors/reputation` → `security_sensors_reputation` — line 327
  - `GET /security/sensors/reputation/process/{pid}` → `security_sensors_reputation_process` — line 337
  - `POST /security/sensors/binary/assess` → `security_sensors_binary_assess` — line 346
  - `POST /security/sensors/binary/trust` → `security_sensors_binary_trust` — line 356
  - `GET /security/sensors/binary/check` → `security_sensors_binary_check` — line 369
  - `GET /security/sensors/usb` → `security_sensors_usb` — line 377
  - `POST /security/sensors/usb/baseline` → `security_sensors_usb_baseline` — line 383
  - `GET /security/sensors/extensions` → `security_sensors_extensions` — line 391
  - `POST /security/sensors/extensions/baseline` → `security_sensors_extensions_baseline` — line 399
  - `GET /security/sensors/backups` → `security_sensors_backups` — line 407
  - `POST /security/sensors/backups` → `security_sensors_backup_create` — line 413
  - `GET /security/sensors/backups/{name}/check` → `security_sensors_backup_check` — line 426
  - `POST /security/sensors/network/isolate` → `security_sensors_network_isolate` — line 435
  - `POST /security/sensors/network/restore` → `security_sensors_network_restore` — line 443
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`
  - `living_assistant.security.security_guardian`

## `src/living_assistant/api_routes/skills.py`

- language: `py`
- size: 9437 bytes
- hash: `6d531e7bd3b7`
- symbols:
  - `class` `DraftRequest` — line 14
  - `class` `UpdateSkillRequest` — line 18
  - `class` `ExecuteRequest` — line 23
  - `class` `RollbackRequest` — line 28
  - `class` `UndoRequest` — line 32
  - `class` `ImportCollectionRequest` — line 36
  - `class` `ImportZipRequest` — line 41
  - `function` `list_skills` — line 46
  - `function` `create_draft` — line 58
  - `function` `get_skill` — line 74
  - `function` `update_skill` — line 87
  - `function` `activate_skill` — line 106
  - `function` `disable_skill` — line 119
  - `function` `archive_skill` — line 130
  - `function` `execute_skill` — line 141
  - `function` `rollback_skill` — line 155
  - `function` `undo_skill` — line 174
  - `function` `reconcile_skill` — line 187
  - `function` `export_skill` — line 200
  - `function` `import_skill` — line 218
  - `function` `browse_collections` — line 239
  - `function` `import_collection_skill` — line 246
- routes:
  - `POST /draft` → `create_draft` — line 58
  - `GET /{skill_id}` → `get_skill` — line 74
  - `PUT /{skill_id}` → `update_skill` — line 87
  - `POST /{skill_id}/activate` → `activate_skill` — line 106
  - `POST /{skill_id}/disable` → `disable_skill` — line 119
  - `POST /{skill_id}/archive` → `archive_skill` — line 130
  - `POST /{skill_id}/execute` → `execute_skill` — line 141
  - `POST /{skill_id}/rollback` → `rollback_skill` — line 155
  - `POST /{skill_id}/undo` → `undo_skill` — line 174
  - `POST /{skill_id}/reconcile` → `reconcile_skill` — line 187
  - `GET /{skill_id}/export` → `export_skill` — line 200
  - `POST /import` → `import_skill` — line 218
  - `GET /collections/browse` → `browse_collections` — line 239
  - `POST /collections/import` → `import_collection_skill` — line 246
- imports:
  - `__future__`
  - `base64`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.skills.collections`
  - `pydantic`
  - `typing`

## `src/living_assistant/api_routes/ui.py`

- language: `py`
- size: 2599 bytes
- hash: `475737d5bdd9`
- symbols:
  - `function` `_security_headers` — line 17
  - `function` `dashboard` — line 26
  - `function` `dashboard_asset` — line 48
- routes:
  - `GET /dashboard` → `dashboard` — line 26
  - `GET /dashboard-assets/{asset_path:path}` → `dashboard_asset` — line 48
- imports:
  - `__future__`
  - `fastapi`
  - `fastapi.responses`
  - `importlib`
  - `mimetypes`
  - `pathlib`

## `src/living_assistant/api_routes/workspace.py`

- language: `py`
- size: 1005 bytes
- hash: `1297d39ab53f`
- symbols:
  - `function` `projects` — line 11
  - `function` `groups` — line 17
  - `function` `processes` — line 23
  - `function` `watches` — line 29
  - `function` `routines` — line 35
- routes:
  - `GET /projects` → `projects` — line 11
  - `GET /groups` → `groups` — line 17
  - `GET /processes` → `processes` — line 23
  - `GET /watches` → `watches` — line 29
  - `GET /routines` → `routines` — line 35
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`

## `src/living_assistant/approval.py`

- language: `py`
- size: 249 bytes
- hash: `a098bd0930cc`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/approval_ui.py`

- language: `py`
- size: 261 bytes
- hash: `f6717db34551`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/briefing.py`

- language: `py`
- size: 249 bytes
- hash: `94b2301e2ac2`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/browser.py`

- language: `py`
- size: 253 bytes
- hash: `2355842700be`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/calendar_store.py`

- language: `py`
- size: 261 bytes
- hash: `614cf71aa686`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/canary.py`

- language: `py`
- size: 253 bytes
- hash: `64e30fe60a93`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/cli/__init__.py`

- language: `py`
- size: 232 bytes
- hash: `063dea33adca`
- imports:
  - `commands`

## `src/living_assistant/cli/commands.py`

- language: `py`
- size: 70545 bytes
- hash: `5aaaf660e416`
- symbols:
  - `function` `onboard` — line 61
  - `function` `doctor` — line 123
  - `function` `platform_status_cmd` — line 159
  - `function` `platform_link_probe` — line 164
  - `function` `platform_service_status` — line 169
  - `function` `release_status` — line 175
  - `function` `release_verify` — line 179
  - `function` `release_backup` — line 184
  - `function` `release_rollback` — line 188
  - `function` `release_remove_version` — line 192
  - `function` `model_status` — line 196
  - `function` `model_preload` — line 202
  - `function` `model_unload` — line 208
  - `function` `model_sleep` — line 213
  - `function` `ask` — line 219
  - `function` `chat` — line 227
  - `function` `daemon` — line 243
  - `function` `tick` — line 250
  - `function` `serve` — line 257
  - `function` `tray` — line 264
  - `function` `project_add` — line 274
  - `function` `project_list` — line 289
  - `function` `project_detect` — line 296
  - `function` `project_audit` — line 301
  - `function` `project_snapshot` — line 308
  - `function` `project_snapshots` — line 314
  - `function` `project_snapshot_restore` — line 321
  - `function` `project_run` — line 336
  - `function` `project_test` — line 347
  - `function` `project_processes` — line 359
  - `function` `project_logs` — line 363
  - `function` `project_restart` — line 368
  - `function` `project_stop` — line 375
  - `function` `group_add` — line 378
  - `function` `group_list` — line 390
  - `function` `group_plan` — line 393
  - `function` `group_run` — line 396
  - `function` `group_stop` — line 400
  - `function` `approval_list` — line 403
  - `function` `approval_approve` — line 407
  - `function` `approval_deny` — line 410
  - `function` `approval_ui` — line 413
  - `function` `watch_add` — line 422
  - `function` `watch_list` — line 426
  - `function` `watch_remove` — line 429
  - `function` `skill_add` — line 432
  - `function` `skill_list` — line 437
  - `function` `skill_remove` — line 446
  - `function` `skill_create` — line 449
  - `function` `skill_activate` — line 459
  - `function` `skill_disable` — line 468
  - `function` `skill_test` — line 477
  - `function` `skill_run` — line 486
  - `function` `skill_rollback` — line 495
  - `function` `skill_export` — line 505
  - `function` `skill_import` — line 517
  - `function` `agent_list` — line 528
  - `function` `agent_info` — line 537
  - `function` `agent_draft` — line 546
  - `function` `agent_activate` — line 556
  - `function` `agent_disable` — line 565
  - `function` `agent_test` — line 574
  - `function` `agent_run` — line 583
  - `function` `agent_export` — line 592
  - `function` `agent_import` — line 603
  - `function` `todo_add` — line 613
  - `function` `todo_list` — line 617
  - `function` `todo_done` — line 620
  - `function` `quarantine_list` — line 623
  - `function` `quarantine_release` — line 626
  - `function` `quarantine_inspect` — line 637
  - `function` `quarantine_scan` — line 643
  - `function` `git_status` — line 652
  - `function` `git_diff` — line 658
  - `function` `desktop_screenshot` — line 664
  - `function` `desktop_clipboard_read` — line 671
  - `function` `desktop_status` — line 678
  - `function` `desktop_monitors` — line 682
  - `function` `desktop_windows` — line 686
  - `function` `desktop_accessibility` — line 690
  - `function` `desktop_click` — line 694
  - `function` `desktop_type` — line 698
  - `function` `desktop_hotkey` — line 702
  - `function` `desktop_analyze_screen` — line 706
  - `function` `security_audit` — line 710
  - `function` `security_av_status` — line 713
  - `function` `security_posture` — line 716
  - `function` `security_findings` — line 720
  - `function` `security_resolve` — line 724
  - `function` `security_initialize` — line 728
  - `function` `security_startup_inventory` — line 735
  - `function` `security_startup_capture` — line 738
  - `function` `security_startup_check` — line 741
  - `function` `security_network_capture` — line 744
  - `function` `security_network_check` — line 747
  - `function` `security_process` — line 750
  - `function` `security_process_triage` — line 753
  - `function` `security_network_activity` — line 756
  - `function` `security_file_signature` — line 759
  - `function` `security_baseline_add` — line 762
  - `function` `security_baseline_list` — line 767
  - `function` `security_baseline_check` — line 770
  - `function` `security_baseline_refresh` — line 773
  - `function` `security_baseline_remove` — line 776
  - `function` `security_contain_process` — line 779
  - `function` `security_sensor_status` — line 783
  - `function` `security_events` — line 786
  - `function` `security_correlate` — line 789
  - `function` `security_dns` — line 792
  - `function` `security_tls_context` — line 795
  - `function` `security_yara` — line 798
  - `function` `security_reputation` — line 802
  - `function` `security_reputation_process` — line 805
  - `function` `security_binary_assess` — line 808
  - `function` `security_binary_trust` — line 811
  - `function` `security_binary_check` — line 814
  - `function` `security_usb_check` — line 817
  - `function` `security_usb_capture` — line 820
  - `function` `security_extensions_check` — line 823
  - `function` `security_extensions_capture` — line 826
  - `function` `security_backup_capture` — line 829
  - `function` `security_backup_list` — line 832
  - `function` `security_backup_check` — line 835
  - `function` `security_network_isolate` — line 838
  - `function` `security_network_restore` — line 841
  - `function` `browser_live` — line 846
  - `function` `browser_sessions` — line 879
  - `function` `browser_start` — line 883
  - `function` `browser_snapshot` — line 889
  - `function` `browser_navigate` — line 893
  - `function` `browser_click` — line 897
  - `function` `browser_fill` — line 901
  - `function` `browser_close` — line 905
  - `function` `voice_status` — line 909
  - `function` `voice_record` — line 914
  - `function` `voice_record_utterance` — line 919
  - `function` `voice_transcribe` — line 928
  - `function` `voice_wake` — line 936
  - `function` `voice_wake_model_download` — line 947
  - `function` `voice_ask` — line 955
  - `function` `voice_presence` — line 973
  - `function` `routine_list` — line 1036
  - `function` `routine_add_event_notify` — line 1040
  - `function` `routine_add_interval_notify` — line 1045
  - `function` `routine_add_interval_todo` — line 1050
  - `function` `routine_add_daily_notify` — line 1055
  - `function` `routine_add_daily_todo` — line 1060
  - `function` `routine_add_weekly_notify` — line 1065
  - `function` `routine_add_prompt` — line 1070
  - `function` `routine_enable` — line 1077
  - `function` `routine_disable` — line 1081
  - `function` `routine_remove` — line 1085
  - `function` `improve_list` — line 1089
  - `function` `improve_show` — line 1093
  - `function` `improve_propose` — line 1097
  - `function` `improve_apply` — line 1104
  - `function` `improve_rollback` — line 1108
  - `function` `improve_reject` — line 1112
  - `function` `improve_suite_add` — line 1116
  - `function` `improve_suite_list` — line 1131
  - `function` `improve_suite_remove` — line 1135
  - `function` `improve_evaluate` — line 1139
  - `function` `improve_evaluations` — line 1155
  - `function` `improve_report` — line 1159
  - `function` `improve_sandbox_status` — line 1164
  - `function` `improve_canary_run` — line 1169
  - `function` `improve_canaries` — line 1179
  - `function` `improve_canary_report` — line 1183
  - `function` `improve_promote` — line 1187
  - `function` `improve_revert_promotion` — line 1191
  - `function` `improve_cleanup_evaluation` — line 1195
  - `function` `calendar_add` — line 1200
  - `function` `calendar_list` — line 1204
  - `function` `calendar_upcoming` — line 1208
  - `function` `calendar_cancel` — line 1212
  - `function` `calendar_export` — line 1216
  - `function` `personal_status` — line 1221
  - `function` `personal_quiet` — line 1225
  - `function` `personal_quiet_off` — line 1229
  - `function` `personal_focus` — line 1233
  - `function` `personal_focus_off` — line 1237
  - `function` `personal_flush_notifications` — line 1241
  - `function` `briefing_now` — line 1245
  - `function` `session_list` — line 1252
  - `function` `session_show` — line 1256
  - `function` `session_search` — line 1260
  - `function` `session_delete` — line 1264
  - `function` `integration_list` — line 1269
  - `function` `integration_providers` — line 1273
  - `function` `integration_add` — line 1278
  - `function` `integration_status` — line 1289
  - `function` `integration_call` — line 1293
  - `function` `integration_auth` — line 1302
  - `function` `integration_clear_credentials` — line 1326
  - `function` `integration_enable` — line 1334
  - `function` `integration_disable` — line 1338
  - `function` `integration_remove` — line 1342
  - `function` `experience_add` — line 1347
  - `function` `experience_list` — line 1363
  - `function` `experience_show` — line 1368
  - `function` `experience_search` — line 1372
  - `function` `experience_confirm` — line 1376
  - `function` `experience_verify` — line 1381
  - `function` `experience_reject` — line 1385
  - `function` `experience_supersede` — line 1389
  - `function` `experience_episodes` — line 1393
  - `function` `experience_patterns` — line 1397
  - `function` `experience_stats` — line 1401
  - `function` `experience_maintenance` — line 1405
- imports:
  - `__future__`
  - `helpers`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.runtime`
  - `living_assistant.security.security_guardian`
  - `living_assistant.security.security_policy`
  - `living_assistant.system.daemon`
  - `living_assistant.system.hardware`
  - `living_assistant.system.onboarding`
  - `living_assistant.system.platform_hardening`
  - `living_assistant.system.release_manager`
  - `living_assistant.tools.security`
  - `os`
  - `pathlib`
  - `rich.table`
  - `typer`

## `src/living_assistant/cli/helpers.py`

- language: `py`
- size: 2952 bytes
- hash: `54875526b622`
- imports:
  - `__future__`
  - `rich.console`
  - `typer`

## `src/living_assistant/config.py`

- language: `py`
- size: 245 bytes
- hash: `c35158bc7ce0`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/connector_credentials.py`

- language: `py`
- size: 287 bytes
- hash: `01fb3dca4713`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/connector_oauth.py`

- language: `py`
- size: 275 bytes
- hash: `b01898e3e8d0`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/connectors/__init__.py`

- language: `py`
- size: 277 bytes
- hash: `7141c929f808`
- imports:
  - `connectors`
  - `mobile_bridge`

## `src/living_assistant/connectors/connector_credentials.py`

- language: `py`
- size: 3661 bytes
- hash: `d3104e5a8727`
- symbols:
  - `function` `_norm` — line 14
  - `class` `CredentialStore` — line 19
  - `method` `CredentialStore.__post_init__` — line 27
  - `method` `CredentialStore.prefix_for` — line 32
  - `method` `CredentialStore.env` — line 35
  - `method` `CredentialStore._keyring` — line 39
  - `method` `CredentialStore.load_bundle` — line 44
  - `method` `CredentialStore.save_bundle` — line 54
  - `method` `CredentialStore.delete_bundle` — line 59
  - `method` `CredentialStore.secret` — line 65
  - `method` `CredentialStore.status` — line 77
  - `method` `CredentialStore.safe_error` — line 94
- imports:
  - `__future__`
  - `dataclasses`
  - `json`
  - `living_assistant.security.security_utils`
  - `os`
  - `re`
  - `typing`

## `src/living_assistant/connectors/connector_oauth.py`

- language: `py`
- size: 10415 bytes
- hash: `08d6afd73d2e`
- symbols:
  - `class` `OAuthManager` — line 25
  - `method` `OAuthManager._client` — line 30
  - `method` `OAuthManager._post` — line 33
  - `method` `OAuthManager._pkce` — line 47
  - `method` `OAuthManager.google_authorization_url` — line 53
  - `method` `OAuthManager.google_exchange` — line 66
  - `method` `OAuthManager.google_login` — line 77
  - `method` `OAuthManager.microsoft_begin_device` — line 99
  - `method` `OAuthManager.microsoft_poll_device` — line 107
  - `method` `OAuthManager.github_begin_device` — line 130
  - `method` `OAuthManager.github_poll_device` — line 135
  - `method` `OAuthManager.refresh` — line 157
- imports:
  - `__future__`
  - `base64`
  - `dataclasses`
  - `hashlib`
  - `http.server`
  - `httpx`
  - `living_assistant.connectors.connector_credentials`
  - `living_assistant.security.security_utils`
  - `secrets`
  - `socketserver`
  - `time`
  - `urllib.parse`
  - `webbrowser`

## `src/living_assistant/connectors/connectors.py`

- language: `py`
- size: 24783 bytes
- hash: `fea28e3ef7e9`
- symbols:
  - `function` `_safe_settings` — line 73
  - `function` `_json_external` — line 93
  - `class` `ConnectorRegistry` — line 98
  - `method` `ConnectorRegistry.__init__` — line 100
  - `method` `ConnectorRegistry._load` — line 104
  - `method` `ConnectorRegistry._save` — line 107
  - `method` `ConnectorRegistry.add` — line 109
  - `method` `ConnectorRegistry.list` — line 124
  - `method` `ConnectorRegistry.get` — line 125
  - `method` `ConnectorRegistry.remove` — line 127
  - `method` `ConnectorRegistry.set_enabled` — line 129
  - `class` `ConnectorManager` — line 135
  - `method` `ConnectorManager.__init__` — line 136
  - `method` `ConnectorManager._client` — line 143
  - `method` `ConnectorManager._request` — line 144
  - `method` `ConnectorManager._token` — line 156
  - `method` `ConnectorManager.status` — line 171
  - `method` `ConnectorManager.refresh_expiring_oauth_tokens` — line 176
  - `method` `ConnectorManager.oauth_scopes` — line 216
  - `method` `ConnectorManager._store_device_transaction` — line 224
  - `method` `ConnectorManager._consume_device_transaction` — line 240
  - `method` `ConnectorManager.authorize` — line 249
  - `method` `ConnectorManager.finish_device_authorize` — line 266
  - `method` `ConnectorManager.call` — line 278
  - `method` `ConnectorManager._dispatch` — line 302
  - `method` `ConnectorManager._google` — line 305
  - `method` `ConnectorManager._microsoft` — line 322
  - `method` `ConnectorManager._github` — line 332
  - `method` `ConnectorManager._telegram` — line 344
  - `method` `ConnectorManager._discord` — line 350
  - `method` `ConnectorManager._notion` — line 358
  - `method` `ConnectorManager._obsidian` — line 370
- imports:
  - `__future__`
  - `base64`
  - `httpx`
  - `json`
  - `living_assistant.connectors.connector_credentials`
  - `living_assistant.connectors.connector_oauth`
  - `living_assistant.core.approval`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `living_assistant.security.security_policy`
  - `living_assistant.security.security_utils`
  - `os`
  - `pathlib`
  - `re`
  - `secrets`
  - `threading`
  - `time`
  - `typing`
  - `urllib.parse`

## `src/living_assistant/connectors/mobile_bridge.py`

- language: `py`
- size: 9052 bytes
- hash: `69dcfd954fbc`
- symbols:
  - `class` `MobileBridge` — line 13
  - `method` `MobileBridge.__init__` — line 22
  - `method` `MobileBridge.enabled` — line 33
  - `method` `MobileBridge._load_state` — line 36
  - `method` `MobileBridge._save_state` — line 43
  - `method` `MobileBridge._connector` — line 46
  - `method` `MobileBridge._allowed` — line 63
  - `method` `MobileBridge._rate_allowed` — line 83
  - `method` `MobileBridge._telegram_updates` — line 95
  - `method` `MobileBridge._send_text` — line 103
  - `method` `MobileBridge.poll_once` — line 116
- imports:
  - `__future__`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `time`
  - `typing`

## `src/living_assistant/core/__init__.py`

- language: `py`
- size: 49 bytes
- hash: `b6fcb4dac9f2`

## `src/living_assistant/core/approval.py`

- language: `py`
- size: 7821 bytes
- hash: `d0cde3aa8c25`
- symbols:
  - `class` `ApprovalStore` — line 27
  - `method` `ApprovalStore.__init__` — line 28
  - `method` `ApprovalStore.action_hash` — line 37
  - `method` `ApprovalStore.expire_pending` — line 47
  - `method` `ApprovalStore.consume_preapproval` — line 62
  - `method` `ApprovalStore.create` — line 78
  - `method` `ApprovalStore.list` — line 98
  - `method` `ApprovalStore.resolve` — line 109
  - `class` `ApprovalManager` — line 125
  - `method` `ApprovalManager.__post_init__` — line 130
  - `method` `ApprovalManager.request` — line 134
  - `method` `ApprovalManager.approve` — line 169
- imports:
  - `__future__`
  - `dataclasses`
  - `datetime`
  - `hashlib`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `rich.console`
  - `sqlite3`
  - `uuid`

## `src/living_assistant/core/briefing.py`

- language: `py`
- size: 6832 bytes
- hash: `dc8dc55c2c77`
- symbols:
  - `class` `BriefingEngine` — line 5
  - `method` `BriefingEngine.__init__` — line 6
  - `method` `BriefingEngine._day_bounds` — line 12
  - `method` `BriefingEngine.build` — line 16
  - `method` `BriefingEngine._time_due` — line 86
  - `method` `BriefingEngine.process_due` — line 91
- imports:
  - `__future__`
  - `copy`
  - `datetime`

## `src/living_assistant/core/calendar_store.py`

- language: `py`
- size: 4987 bytes
- hash: `d799197f191a`
- symbols:
  - `class` `CalendarStore` — line 23
  - `method` `CalendarStore.__init__` — line 24
  - `method` `CalendarStore._validate_iso` — line 31
  - `method` `CalendarStore.add` — line 37
  - `method` `CalendarStore.get` — line 51
  - `method` `CalendarStore.list` — line 55
  - `method` `CalendarStore.upcoming` — line 66
  - `method` `CalendarStore.cancel` — line 71
  - `method` `CalendarStore.delete` — line 74
  - `method` `CalendarStore.export_ics` — line 77
- imports:
  - `__future__`
  - `datetime`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `pathlib`
  - `sqlite3`
  - `uuid`

## `src/living_assistant/core/config.py`

- language: `py`
- size: 4613 bytes
- hash: `8c142fe2233f`
- symbols:
  - `function` `_expand_env` — line 18
  - `function` `source_root` — line 31
  - `function` `data_dir` — line 40
  - `function` `config_dir` — line 51
  - `function` `cache_dir` — line 62
  - `function` `log_dir` — line 68
  - `function` `state_dir` — line 74
  - `function` `venvs_dir` — line 80
  - `function` `user_config_path` — line 87
  - `function` `model_preferences_path` — line 91
  - `function` `load_model_preferences` — line 95
  - `function` `save_model_preference` — line 106
  - `function` `active_config_path` — line 116
  - `function` `project_root` — line 128
  - `function` `_default_config_text` — line 137
  - `function` `load_config` — line 144
- imports:
  - `__future__`
  - `importlib`
  - `json`
  - `living_assistant.core.storage_utils`
  - `os`
  - `pathlib`
  - `platformdirs`
  - `re`
  - `yaml`

## `src/living_assistant/core/event_bus.py`

- language: `py`
- size: 4761 bytes
- hash: `1bf4b3a1b5d8`
- symbols:
  - `class` `ActivityEvent` — line 16
  - `method` `ActivityEvent.to_dict` — line 22
  - `class` `EventBus` — line 26
  - `method` `EventBus.__init__` — line 33
  - `method` `EventBus.publish` — line 66
  - `method` `EventBus.recent` — line 96
  - `method` `EventBus.wait_for_events` — line 101
  - `method` `EventBus.stream` — line 113
- imports:
  - `__future__`
  - `collections`
  - `dataclasses`
  - `datetime`
  - `json`
  - `living_assistant.core.sqlite_utils`
  - `pathlib`
  - `threading`
  - `time`
  - `typing`

## `src/living_assistant/core/memory.py`

- language: `py`
- size: 5920 bytes
- hash: `5d37c6c1fb8a`
- symbols:
  - `class` `MemoryStore` — line 47
  - `method` `MemoryStore.__init__` — line 48
  - `method` `MemoryStore._migrate` — line 63
  - `method` `MemoryStore.remember` — line 68
  - `method` `MemoryStore.search` — line 75
  - `method` `MemoryStore.add_todo` — line 88
  - `method` `MemoryStore.list_todos` — line 95
  - `method` `MemoryStore.due_todos` — line 99
  - `method` `MemoryStore.mark_todo_notified` — line 107
  - `method` `MemoryStore.complete_todo` — line 110
  - `method` `MemoryStore.add_event` — line 113
  - `method` `MemoryStore.list_events` — line 120
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `sqlite3`

## `src/living_assistant/core/model_provider.py`

- language: `py`
- size: 50523 bytes
- hash: `d62b351913cb`
- symbols:
  - `class` `ModelError` — line 15
  - `function` `model_provider_info` — line 41
  - `class` `OllamaProvider` — line 88
  - `method` `OllamaProvider.__post_init__` — line 94
  - `method` `OllamaProvider._client` — line 107
  - `method` `OllamaProvider._validate_model_name` — line 111
  - `method` `OllamaProvider.available_models` — line 130
  - `method` `OllamaProvider.model_inventory` — line 133
  - `method` `OllamaProvider.model_size_bytes` — line 148
  - `method` `OllamaProvider.running_models` — line 158
  - `method` `OllamaProvider.pull` — line 169
  - `method` `OllamaProvider.delete` — line 189
  - `method` `OllamaProvider.preload` — line 209
  - `method` `OllamaProvider.chat_stream` — line 223
  - `method` `OllamaProvider.chat` — line 252
  - `method` `OllamaProvider.unload` — line 270
  - `class` `AirLLMProvider` — line 278
  - `method` `AirLLMProvider.__init__` — line 294
  - `method` `AirLLMProvider.is_airllm_model` — line 323
  - `method` `AirLLMProvider.normalize_model` — line 327
  - `method` `AirLLMProvider.external_name` — line 336
  - `method` `AirLLMProvider._airllm_module` — line 339
  - `method` `AirLLMProvider._load_model` — line 347
  - `method` `AirLLMProvider._prompt` — line 384
  - `method` `AirLLMProvider._sequence_length` — line 417
  - `method` `AirLLMProvider.available_models` — line 429
  - `method` `AirLLMProvider.model_inventory` — line 433
  - `method` `AirLLMProvider.model_size_bytes` — line 444
  - `method` `AirLLMProvider.running_models` — line 452
  - `method` `AirLLMProvider.preload` — line 459
  - `method` `AirLLMProvider.chat` — line 464
  - `method` `AirLLMProvider.chat_stream` — line 526
  - `method` `AirLLMProvider.unload` — line 533
  - `class` `CompositeModelProvider` — line 547
  - `method` `CompositeModelProvider.__init__` — line 550
  - `method` `CompositeModelProvider._route` — line 558
  - `method` `CompositeModelProvider.available_models` — line 563
  - `method` `CompositeModelProvider.model_inventory` — line 573
  - `method` `CompositeModelProvider.model_size_bytes` — line 584
  - `method` `CompositeModelProvider.running_models` — line 588
  - `method` `CompositeModelProvider.preload` — line 598
  - `method` `CompositeModelProvider.chat_stream` — line 602
  - `method` `CompositeModelProvider.chat` — line 609
  - `method` `CompositeModelProvider.unload` — line 614
  - `class` `ModelManager` — line 619
  - `method` `ModelManager.__init__` — line 627
  - `method` `ModelManager._publish` — line 644
  - `method` `ModelManager._model_sem` — line 651
  - `method` `ModelManager._touch_locked` — line 659
  - `method` `ModelManager._evict_one_locked` — line 673
  - `method` `ModelManager._prepare_locked` — line 696
  - `method` `ModelManager.activate` — line 750
  - `method` `ModelManager.effective_keep_alive` — line 755
  - `method` `ModelManager._wait_for_thermal_slot` — line 760
  - `method` `ModelManager.lease` — line 786
  - `method` `ModelManager._ollama_provider` — line 818
  - `method` `ModelManager.resolve_local_model` — line 825
  - `method` `ModelManager.local_model_catalog` — line 848
  - `method` `ModelManager.pull_local_model` — line 923
  - `method` `ModelManager.delete_local_model` — line 930
  - `method` `ModelManager.preload` — line 948
  - `method` `ModelManager.unload` — line 954
  - `method` `ModelManager.sleep` — line 967
  - `method` `ModelManager.sync_running_models` — line 982
  - `method` `ModelManager.status` — line 1009
  - `method` `ModelManager.provider_info` — line 1039
  - `method` `ModelManager.validate_model_selection` — line 1101
- imports:
  - `__future__`
  - `collections`
  - `contextlib`
  - `dataclasses`
  - `datetime`
  - `gc`
  - `httpx`
  - `importlib`
  - `living_assistant.security.security_utils`
  - `os`
  - `threading`
  - `time`
  - `typing`

## `src/living_assistant/core/models.py`

- language: `py`
- size: 2309 bytes
- hash: `ddbf781d8f03`
- symbols:
  - `class` `ExecutivePlan` — line 4
  - `class` `ProposedMutation` — line 12
  - `class` `SpecialistResponse` — line 18
- imports:
  - `pydantic`
  - `typing`

## `src/living_assistant/core/personal_state.py`

- language: `py`
- size: 6251 bytes
- hash: `943a68c63ab4`
- symbols:
  - `function` `_parse_hhmm` — line 10
  - `class` `PersonalState` — line 18
  - `method` `PersonalState.__init__` — line 20
  - `method` `PersonalState._load` — line 32
  - `method` `PersonalState._save` — line 42
  - `method` `PersonalState.tzinfo` — line 46
  - `method` `PersonalState.now` — line 54
  - `method` `PersonalState.status` — line 57
  - `method` `PersonalState.set_quiet_hours` — line 81
  - `method` `PersonalState.set_quiet_enabled` — line 88
  - `method` `PersonalState.start_focus` — line 92
  - `method` `PersonalState.stop_focus` — line 103
  - `method` `PersonalState.is_quiet` — line 107
  - `method` `PersonalState.briefing_last` — line 137
  - `method` `PersonalState.mark_briefing` — line 140
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `pathlib`
  - `zoneinfo`

## `src/living_assistant/core/runtime.py`

- language: `py`
- size: 28293 bytes
- hash: `1ed1e9effcbc`
- symbols:
  - `class` `Runtime` — line 90
  - `method` `Runtime.dispatch` — line 130
  - `function` `get_runtime` — line 151
  - `function` `build_runtime` — line 158
- imports:
  - `__future__`
  - `dataclasses`
  - `dotenv`
  - `living_assistant.agents.agents`
  - `living_assistant.agents.orchestrator`
  - `living_assistant.agents.task_graph`
  - `living_assistant.connectors.connector_credentials`
  - `living_assistant.connectors.connectors`
  - `living_assistant.connectors.mobile_bridge`
  - `living_assistant.core.approval`
  - `living_assistant.core.briefing`
  - `living_assistant.core.calendar_store`
  - `living_assistant.core.config`
  - `living_assistant.core.event_bus`
  - `living_assistant.core.memory`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.personal_state`
  - `living_assistant.core.sessions`
  - `living_assistant.core.skills`
  - `living_assistant.core.workspace`
  - `living_assistant.desktop.browser`
  - `living_assistant.desktop.desktop_intelligence`
  - `living_assistant.desktop.voice`
  - `living_assistant.integrations`
  - `living_assistant.learning.canary`
  - `living_assistant.learning.evaluation`
  - `living_assistant.learning.experience`
  - `living_assistant.learning.improvements`
  - `living_assistant.learning.knowledge_gap_detection`
  - `living_assistant.learning.repair_loop`
  - `living_assistant.learning.run_history`
  - `living_assistant.security.quarantine`
  - `living_assistant.security.security_guardian`
  - `living_assistant.security.security_sensors`
  - `living_assistant.system.codebase_index`
  - `living_assistant.system.groups`
  - `living_assistant.system.hardware`
  - `living_assistant.system.model_usage`
  - `living_assistant.system.notifications`
  - `living_assistant.system.peer_agents`

## `src/living_assistant/core/sessions.py`

- language: `py`
- size: 7826 bytes
- hash: `03254166c2e8`
- symbols:
  - `class` `SessionStore` — line 45
  - `method` `SessionStore.__init__` — line 46
  - `method` `SessionStore.create` — line 67
  - `method` `SessionStore.ensure` — line 74
  - `method` `SessionStore.get` — line 77
  - `method` `SessionStore._redact` — line 81
  - `method` `SessionStore.add_message` — line 84
  - `method` `SessionStore.recent_messages` — line 92
  - `method` `SessionStore.list` — line 96
  - `method` `SessionStore.search` — line 100
  - `method` `SessionStore.delete` — line 119
  - `method` `SessionStore.prune` — line 122
- imports:
  - `__future__`
  - `datetime`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.core.storage_utils`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `re`
  - `sqlite3`
  - `uuid`

## `src/living_assistant/core/skills.py`

- language: `py`
- size: 4858 bytes
- hash: `e84ad512c3f1`
- symbols:
  - `class` `Skill` — line 14
  - `class` `SkillRegistry` — line 20
  - `method` `SkillRegistry.__init__` — line 26
  - `method` `SkillRegistry._load` — line 42
  - `method` `SkillRegistry._save` — line 48
  - `method` `SkillRegistry.add` — line 51
  - `method` `SkillRegistry.remove` — line 64
  - `method` `SkillRegistry.list` — line 67
  - `method` `SkillRegistry.match` — line 85
- imports:
  - `__future__`
  - `dataclasses`
  - `importlib`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `pathlib`
  - `re`
  - `time`
  - `typing`

## `src/living_assistant/core/sqlite_utils.py`

- language: `py`
- size: 5264 bytes
- hash: `e71dbd77ee3c`
- symbols:
  - `class` `ThreadLocalSQLite` — line 8
  - `method` `ThreadLocalSQLite.__init__` — line 16
  - `method` `ThreadLocalSQLite._connection` — line 26
  - `method` `ThreadLocalSQLite.row_factory` — line 61
  - `method` `ThreadLocalSQLite.row_factory` — line 65
  - `method` `ThreadLocalSQLite.execute` — line 71
  - `method` `ThreadLocalSQLite.executemany` — line 74
  - `method` `ThreadLocalSQLite.executescript` — line 77
  - `method` `ThreadLocalSQLite.cursor` — line 80
  - `method` `ThreadLocalSQLite.commit` — line 83
  - `method` `ThreadLocalSQLite.rollback` — line 86
  - `method` `ThreadLocalSQLite.close` — line 89
  - `method` `ThreadLocalSQLite.close_all` — line 100
  - `method` `ThreadLocalSQLite.__enter__` — line 126
  - `method` `ThreadLocalSQLite.__exit__` — line 129
  - `method` `ThreadLocalSQLite.__getattr__` — line 132
- imports:
  - `__future__`
  - `pathlib`
  - `sqlite3`
  - `threading`

## `src/living_assistant/core/storage_utils.py`

- language: `py`
- size: 1398 bytes
- hash: `ac010667a969`
- symbols:
  - `function` `atomic_write_text` — line 9
  - `function` `atomic_write_json` — line 41
- imports:
  - `__future__`
  - `json`
  - `os`
  - `pathlib`
  - `tempfile`

## `src/living_assistant/core/typesafe.py`

- language: `py`
- size: 17202 bytes
- hash: `faf2f8548955`
- symbols:
  - `class` `JevClient` — line 44
  - `method` `JevClient.__init__` — line 79
  - `method` `JevClient.choice` — line 94
  - `method` `JevClient.noul` — line 105
  - `method` `JevClient.score` — line 114
  - `method` `JevClient.goal_achieved` — line 129
  - `method` `JevClient.is_lesson_relevant` — line 146
  - `method` `JevClient.link_incident` — line 165
  - `method` `JevClient.score_secret_risk` — line 193
  - `method` `JevClient.score_knowledge_value` — line 205
  - `method` `JevClient._live_choice` — line 227
  - `method` `JevClient._live_noul` — line 249
  - `method` `JevClient._live_score` — line 269
  - `method` `JevClient._mock_choice` — line 295
  - `method` `JevClient._mock_noul` — line 307
  - `method` `JevClient._mock_score` — line 338
  - `method` `JevClient._days_since` — line 393
- imports:
  - `__future__`
  - `json`
  - `logging`
  - `os`
  - `re`
  - `typing`

## `src/living_assistant/core/workspace.py`

- language: `py`
- size: 2260 bytes
- hash: `097a2c4b7d2c`
- symbols:
  - `class` `WorkspaceViolation` — line 4
  - `class` `Workspace` — line 7
  - `method` `Workspace.__init__` — line 8
  - `method` `Workspace.resolve` — line 13
  - `method` `Workspace.list` — line 27
  - `method` `Workspace.read_text` — line 46
  - `method` `Workspace.write_text` — line 50
- imports:
  - `__future__`
  - `pathlib`

## `src/living_assistant/daemon.py`

- language: `py`
- size: 249 bytes
- hash: `a77a386d5813`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/default_config.yaml`

- language: `yaml`
- size: 10834 bytes
- hash: `4605de4acbea`

## `src/living_assistant/default_skills.json`

- language: `json`
- size: 1740 bytes
- hash: `40ae87d020bc`

## `src/living_assistant/desktop/__init__.py`

- language: `py`
- size: 52 bytes
- hash: `66de8a485787`

## `src/living_assistant/desktop/approval_ui.py`

- language: `py`
- size: 2322 bytes
- hash: `34cfadbc0b1c`
- symbols:
  - `function` `run_approval_ui` — line 4
- imports:
  - `__future__`

## `src/living_assistant/desktop/browser.py`

- language: `py`
- size: 28395 bytes
- hash: `425a9c6dc964`
- symbols:
  - `function` `safe_browser_url` — line 16
  - `function` `_safe_name` — line 25
  - `class` `BrowserController` — line 33
  - `method` `BrowserController._quiet_block` — line 41
  - `method` `BrowserController._playwright` — line 52
  - `method` `BrowserController._authorize_url` — line 59
  - `method` `BrowserController._authorize_extra_host` — line 77
  - `method` `BrowserController._resolver_args` — line 94
  - `method` `BrowserController._install_route_guard` — line 105
  - `method` `BrowserController.search_web` — line 130
  - `method` `BrowserController.search_images` — line 215
  - `method` `BrowserController._screenshot_target` — line 293
  - `method` `BrowserController.snapshot` — line 306
  - `method` `BrowserController.interact` — line 335
  - `method` `BrowserController.start_session` — line 368
  - `method` `BrowserController.list_sessions` — line 440
  - `method` `BrowserController._session` — line 447
  - `method` `BrowserController.snapshot_session` — line 453
  - `method` `BrowserController.navigate_session` — line 470
  - `method` `BrowserController.interact_session` — line 491
  - `method` `BrowserController.close_session` — line 511
- imports:
  - `__future__`
  - `dataclasses`
  - `json`
  - `living_assistant.core.approval`
  - `living_assistant.core.config`
  - `living_assistant.core.workspace`
  - `living_assistant.security.security_policy`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `re`
  - `shutil`
  - `typing`
  - `urllib.parse`

## `src/living_assistant/desktop/desktop_intelligence.py`

- language: `py`
- size: 18375 bytes
- hash: `97faf68ce9e4`
- symbols:
  - `class` `DesktopError` — line 17
  - `class` `MonitorInfo` — line 22
  - `class` `WindowInfo` — line 32
  - `class` `DesktopController` — line 40
  - `method` `DesktopController.__init__` — line 47
  - `method` `DesktopController._approve` — line 57
  - `method` `DesktopController._quiet_vision_block` — line 60
  - `method` `DesktopController.status` — line 70
  - `method` `DesktopController._module_available` — line 83
  - `method` `DesktopController._semantic_backend` — line 90
  - `method` `DesktopController._accessibility_note` — line 103
  - `method` `DesktopController.monitors` — line 112
  - `method` `DesktopController.windows` — line 123
  - `method` `DesktopController._run` — line 151
  - `method` `DesktopController._windows_windows` — line 154
  - `method` `DesktopController._mac_windows` — line 169
  - `method` `DesktopController._linux_windows` — line 180
  - `method` `DesktopController.accessibility_tree` — line 193
  - `method` `DesktopController._windows_accessibility` — line 213
  - `method` `DesktopController._mac_accessibility` — line 236
  - `method` `DesktopController._linux_accessibility` — line 243
  - `method` `DesktopController._pyautogui` — line 261
  - `method` `DesktopController.click` — line 270
  - `method` `DesktopController.type_text` — line 276
  - `method` `DesktopController.hotkey` — line 282
  - `method` `DesktopController.move_mouse` — line 289
  - `method` `DesktopController.screenshot` — line 294
  - `method` `DesktopController.analyze_screen` — line 313
- imports:
  - `__future__`
  - `base64`
  - `dataclasses`
  - `json`
  - `living_assistant.security.security_utils`
  - `os`
  - `pathlib`
  - `platform`
  - `shutil`
  - `subprocess`
  - `tempfile`
  - `typing`

## `src/living_assistant/desktop/overlay.py`

- language: `py`
- size: 38476 bytes
- hash: `ee09d52569a2`
- symbols:
  - `function` `_get_active_window_title` — line 17
  - `class` `FloatingOverlay` — line 32
  - `method` `FloatingOverlay.__init__` — line 41
  - `method` `FloatingOverlay._build_ui` — line 107
  - `method` `FloatingOverlay._draw_eye` — line 273
  - `method` `FloatingOverlay._animate_eye` — line 325
  - `method` `FloatingOverlay._start_drag` — line 341
  - `method` `FloatingOverlay._on_drag` — line 345
  - `method` `FloatingOverlay._start_resize` — line 352
  - `method` `FloatingOverlay._on_resize` — line 361
  - `method` `FloatingOverlay._set_expanded` — line 380
  - `method` `FloatingOverlay._animate_overlay_geometry` — line 405
  - `method` `FloatingOverlay._toggle_expand` — line 428
  - `method` `FloatingOverlay._register_global_hotkey` — line 431
  - `method` `FloatingOverlay._poll_global_hotkey` — line 450
  - `method` `FloatingOverlay._show_command_palette` — line 470
  - `method` `FloatingOverlay._unregister_global_hotkey` — line 484
  - `method` `FloatingOverlay._shutdown` — line 493
  - `method` `FloatingOverlay._toggle_settings` — line 497
  - `method` `FloatingOverlay._settings_request` — line 506
  - `method` `FloatingOverlay._refresh_settings_backend` — line 515
  - `method` `FloatingOverlay._apply_settings_snapshot` — line 525
  - `method` `FloatingOverlay._apply_model_setting` — line 538
  - `method` `FloatingOverlay._change_model_backend` — line 544
  - `method` `FloatingOverlay._apply_voice_setting` — line 553
  - `method` `FloatingOverlay._change_voice_backend` — line 557
  - `method` `FloatingOverlay._start_focus_setting` — line 567
  - `method` `FloatingOverlay._stop_focus_setting` — line 574
  - `method` `FloatingOverlay._focus_backend` — line 577
  - `method` `FloatingOverlay._poll_context` — line 593
  - `method` `FloatingOverlay._append_message` — line 606
  - `method` `FloatingOverlay._on_enter_press` — line 637
  - `method` `FloatingOverlay._send_message` — line 642
  - `method` `FloatingOverlay._ask_active_screen` — line 651
  - `method` `FloatingOverlay._analyze_screen_backend` — line 665
  - `method` `FloatingOverlay._on_screen_analyzed` — line 685
  - `method` `FloatingOverlay._on_screen_analysis_error` — line 700
  - `method` `FloatingOverlay.show_inquiry` — line 709
  - `method` `FloatingOverlay._dismiss_inquiry` — line 717
  - `method` `FloatingOverlay._answer_inquiry` — line 721
  - `method` `FloatingOverlay._resolve_inquiry_backend` — line 729
  - `method` `FloatingOverlay._poll_approval_badge` — line 748
  - `method` `FloatingOverlay._set_pending_approval_count` — line 764
  - `method` `FloatingOverlay._poll_inquiries` — line 768
  - `method` `FloatingOverlay._query_backend` — line 791
  - `method` `FloatingOverlay._on_query_success` — line 807
  - `method` `FloatingOverlay._on_query_error` — line 811
  - `method` `FloatingOverlay.run` — line 815
  - `function` `start_overlay` — line 822
- imports:
  - `__future__`
  - `ctypes`
  - `json`
  - `threading`
  - `time`
  - `tkinter`
  - `urllib.request`

## `src/living_assistant/desktop/tray.py`

- language: `py`
- size: 2054 bytes
- hash: `3436883b3d9f`
- symbols:
  - `function` `run_tray` — line 5
- imports:
  - `__future__`
  - `threading`
  - `time`
  - `webbrowser`

## `src/living_assistant/desktop/voice.py`

- language: `py`
- size: 32450 bytes
- hash: `78cbcb6208b0`
- symbols:
  - `class` `VoiceEngine` — line 18
  - `method` `VoiceEngine._cfg` — line 39
  - `method` `VoiceEngine.enabled` — line 42
  - `method` `VoiceEngine.hands_free_enabled` — line 48
  - `method` `VoiceEngine._module_available` — line 57
  - `method` `VoiceEngine.status` — line 63
  - `method` `VoiceEngine.start_hands_free` — line 84
  - `method` `VoiceEngine.stop_hands_free` — line 128
  - `method` `VoiceEngine._ensure_microphone_approval` — line 139
  - `method` `VoiceEngine._import_audio` — line 150
  - `method` `VoiceEngine._write_wav` — line 159
  - `method` `VoiceEngine.record` — line 167
  - `method` `VoiceEngine.record_until_silence` — line 190
  - `method` `VoiceEngine._load_stt` — line 293
  - `method` `VoiceEngine.transcribe` — line 307
  - `method` `VoiceEngine._wake_model_paths` — line 338
  - `method` `VoiceEngine.download_wake_model` — line 372
  - `method` `VoiceEngine.clean_command_text` — line 401
  - `method` `VoiceEngine._load_wake_model` — line 420
  - `method` `VoiceEngine.listen_for_wake_word` — line 443
  - `method` `VoiceEngine.listen_for_command` — line 490
  - `method` `VoiceEngine.speak` — line 600
  - `method` `VoiceEngine.sleep` — line 668
- imports:
  - `__future__`
  - `collections`
  - `dataclasses`
  - `importlib.util`
  - `living_assistant.core.approval`
  - `living_assistant.core.config`
  - `living_assistant.core.workspace`
  - `math`
  - `pathlib`
  - `threading`
  - `time`
  - `wave`

## `src/living_assistant/desktop_intelligence.py`

- language: `py`
- size: 279 bytes
- hash: `e51ed535353e`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/evaluation.py`

- language: `py`
- size: 261 bytes
- hash: `3a0a79af64ca`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/event_bus.py`

- language: `py`
- size: 251 bytes
- hash: `c0cd6cd5d621`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/experience.py`

- language: `py`
- size: 261 bytes
- hash: `b92b369f1bb4`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/groups.py`

- language: `py`
- size: 249 bytes
- hash: `136c12f64a91`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/hardware.py`

- language: `py`
- size: 253 bytes
- hash: `3634b7fbe3d6`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/improvements.py`

- language: `py`
- size: 265 bytes
- hash: `b4291c597e0b`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/integrations/__init__.py`

- language: `py`
- size: 1094 bytes
- hash: `39f668c92626`
- imports:
  - `agency_agents`
  - `agentmemory`
  - `awesome_agent_tools`
  - `awesome_harness`
  - `browser_use`
  - `codebase_memory`
  - `cybersecurity_skills`
  - `diagram_design`
  - `edge0`
  - `external`
  - `graft`
  - `openmontage`
  - `openviking`
  - `scientific_skills`

## `src/living_assistant/integrations/agency_agents.py`

- language: `py`
- size: 4114 bytes
- hash: `d5ee2c76a194`
- symbols:
  - `class` `AgencyAgentsAdapter` — line 10
  - `method` `AgencyAgentsAdapter.__init__` — line 19
  - `method` `AgencyAgentsAdapter.list_categories` — line 26
  - `method` `AgencyAgentsAdapter.list_agents` — line 41
  - `method` `AgencyAgentsAdapter.get_agent` — line 62
  - `method` `AgencyAgentsAdapter.search_agents` — line 83
- imports:
  - `__future__`
  - `logging`
  - `pathlib`
  - `threading`
  - `typing`

## `src/living_assistant/integrations/agentmemory.py`

- language: `py`
- size: 9190 bytes
- hash: `c65e3e2eeca5`
- symbols:
  - `class` `AgentMemoryAdapter` — line 18
  - `method` `AgentMemoryAdapter.__init__` — line 30
  - `method` `AgentMemoryAdapter.available` — line 49
  - `method` `AgentMemoryAdapter._ping_server` — line 60
  - `method` `AgentMemoryAdapter.health` — line 69
  - `method` `AgentMemoryAdapter.recall` — line 88
  - `method` `AgentMemoryAdapter.save` — line 109
  - `method` `AgentMemoryAdapter.file_history` — line 132
  - `method` `AgentMemoryAdapter.smart_search` — line 145
  - `method` `AgentMemoryAdapter.list_memories` — line 164
  - `method` `AgentMemoryAdapter._call_api` — line 182
  - `method` `AgentMemoryAdapter._cli_recall` — line 207
  - `method` `AgentMemoryAdapter._resolve_cli_command` — line 230
- imports:
  - `__future__`
  - `importlib.util`
  - `json`
  - `living_assistant.security.security_utils`
  - `logging`
  - `pathlib`
  - `shutil`
  - `subprocess`
  - `sys`
  - `threading`
  - `typing`

## `src/living_assistant/integrations/awesome_agent_tools.py`

- language: `py`
- size: 1843 bytes
- hash: `51cd03bf0364`
- symbols:
  - `class` `AwesomeAgentToolsAdapter` — line 9
  - `method` `AwesomeAgentToolsAdapter.__init__` — line 12
  - `method` `AwesomeAgentToolsAdapter.read_reference` — line 19
  - `method` `AwesomeAgentToolsAdapter.list_categories` — line 36
- imports:
  - `__future__`
  - `logging`
  - `pathlib`
  - `typing`

## `src/living_assistant/integrations/awesome_harness.py`

- language: `py`
- size: 1219 bytes
- hash: `7df856743964`
- symbols:
  - `class` `AwesomeHarnessAdapter` — line 9
  - `method` `AwesomeHarnessAdapter.__init__` — line 12
  - `method` `AwesomeHarnessAdapter.read_reference` — line 19
- imports:
  - `__future__`
  - `logging`
  - `pathlib`
  - `typing`

## `src/living_assistant/integrations/browser_use.py`

- language: `py`
- size: 18779 bytes
- hash: `657cd4dd3260`
- symbols:
  - `class` `BrowserUseAdapter` — line 20
  - `method` `BrowserUseAdapter.__init__` — line 43
  - `method` `BrowserUseAdapter._repository_version` — line 76
  - `method` `BrowserUseAdapter._imports` — line 86
  - `method` `BrowserUseAdapter.available` — line 140
  - `method` `BrowserUseAdapter._bounded_text` — line 154
  - `method` `BrowserUseAdapter._safe_error` — line 161
  - `method` `BrowserUseAdapter._safe_call` — line 168
  - `method` `BrowserUseAdapter._sha256` — line 182
  - `method` `BrowserUseAdapter._path_is_within` — line 190
  - `method` `BrowserUseAdapter._verify_download` — line 197
  - `method` `BrowserUseAdapter._capture_download_state` — line 237
  - `method` `BrowserUseAdapter._download_results` — line 267
  - `method` `BrowserUseAdapter._history_result` — line 277
  - `method` `BrowserUseAdapter._execute` — line 333
  - `method` `BrowserUseAdapter._run_coroutine_factory` — line 401
  - `method` `BrowserUseAdapter.run` — line 422
- imports:
  - `__future__`
  - `asyncio`
  - `concurrent.futures`
  - `hashlib`
  - `importlib`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `sys`
  - `threading`
  - `time`
  - `tomllib`
  - `typing`

## `src/living_assistant/integrations/codebase_memory.py`

- language: `py`
- size: 6328 bytes
- hash: `cf23e404307a`
- symbols:
  - `class` `CodebaseMemoryAdapter` — line 16
  - `method` `CodebaseMemoryAdapter.__init__` — line 28
  - `method` `CodebaseMemoryAdapter.available` — line 43
  - `method` `CodebaseMemoryAdapter._resolve_executable` — line 54
  - `method` `CodebaseMemoryAdapter.index_repository` — line 87
  - `method` `CodebaseMemoryAdapter.get_architecture` — line 91
  - `method` `CodebaseMemoryAdapter.query_graph` — line 95
  - `method` `CodebaseMemoryAdapter.find_callers` — line 101
  - `method` `CodebaseMemoryAdapter.find_callees` — line 107
  - `method` `CodebaseMemoryAdapter.manage_adr` — line 113
  - `method` `CodebaseMemoryAdapter._run_command` — line 133
- imports:
  - `__future__`
  - `json`
  - `living_assistant.security.security_utils`
  - `logging`
  - `pathlib`
  - `shutil`
  - `subprocess`
  - `threading`
  - `typing`

## `src/living_assistant/integrations/cybersecurity_skills.py`

- language: `py`
- size: 16107 bytes
- hash: `d719c6425b94`
- symbols:
  - `class` `CybersecuritySkillsAdapter` — line 53
  - `method` `CybersecuritySkillsAdapter.__init__` — line 62
  - `method` `CybersecuritySkillsAdapter.available` — line 77
  - `method` `CybersecuritySkillsAdapter._ensure_index` — line 83
  - `method` `CybersecuritySkillsAdapter.get_catalog_info` — line 118
  - `method` `CybersecuritySkillsAdapter.search_skills` — line 133
  - `method` `CybersecuritySkillsAdapter.get_skill` — line 187
  - `method` `CybersecuritySkillsAdapter.audit_prompt_injection` — line 245
  - `method` `CybersecuritySkillsAdapter.threat_model_component` — line 321
- imports:
  - `__future__`
  - `json`
  - `living_assistant.security.security_utils`
  - `logging`
  - `os`
  - `pathlib`
  - `re`
  - `threading`
  - `typing`
  - `yaml`

## `src/living_assistant/integrations/diagram_design.py`

- language: `py`
- size: 20890 bytes
- hash: `a8d928fa2e00`
- symbols:
  - `class` `DiagramDesignAdapter` — line 65
  - `method` `DiagramDesignAdapter.__init__` — line 75
  - `method` `DiagramDesignAdapter._resolve_paths` — line 85
  - `method` `DiagramDesignAdapter.available` — line 104
  - `method` `DiagramDesignAdapter.list_types` — line 111
  - `method` `DiagramDesignAdapter.extract_mermaid` — line 119
  - `method` `DiagramDesignAdapter.extract_drawio` — line 161
  - `method` `DiagramDesignAdapter.extract_excalidraw` — line 189
  - `method` `DiagramDesignAdapter.validate_diagram` — line 219
  - `method` `DiagramDesignAdapter.generate_html` — line 272
  - `method` `DiagramDesignAdapter.export_svg` — line 375
  - `method` `DiagramDesignAdapter._get_script` — line 400
  - `method` `DiagramDesignAdapter._run_proc` — line 408
- imports:
  - `__future__`
  - `json`
  - `living_assistant.security.security_utils`
  - `logging`
  - `os`
  - `pathlib`
  - `re`
  - `shutil`
  - `subprocess`
  - `sys`
  - `tempfile`
  - `threading`
  - `typing`

## `src/living_assistant/integrations/edge0.py`

- language: `py`
- size: 3133 bytes
- hash: `919d4b0f60f1`
- symbols:
  - `class` `Edge0Adapter` — line 17
  - `method` `Edge0Adapter.__init__` — line 22
  - `method` `Edge0Adapter._sdk` — line 30
  - `method` `Edge0Adapter.list_models` — line 50
  - `method` `Edge0Adapter.generate` — line 62
  - `method` `Edge0Adapter.chat` — line 77
- imports:
  - `__future__`
  - `importlib.util`
  - `logging`
  - `pathlib`
  - `sys`
  - `threading`
  - `typing`

## `src/living_assistant/integrations/external.py`

- language: `py`
- size: 7600 bytes
- hash: `5b2456e1112a`
- symbols:
  - `class` `IntegrationSpec` — line 12
  - `function` `_path_status` — line 61
  - `class` `ExternalIntegrationRegistry` — line 68
  - `method` `ExternalIntegrationRegistry.__init__` — line 76
  - `method` `ExternalIntegrationRegistry._enabled` — line 80
  - `method` `ExternalIntegrationRegistry.status` — line 84
  - `method` `ExternalIntegrationRegistry.role_status` — line 155
  - `method` `ExternalIntegrationRegistry.environment_status` — line 158
- imports:
  - `__future__`
  - `dataclasses`
  - `importlib.util`
  - `os`
  - `pathlib`
  - `shutil`
  - `typing`

## `src/living_assistant/integrations/graft.py`

- language: `py`
- size: 21892 bytes
- hash: `9d6572288a59`
- symbols:
  - `class` `GraftAdapter` — line 36
  - `method` `GraftAdapter.__init__` — line 46
  - `method` `GraftAdapter._resolve_binary` — line 70
  - `method` `GraftAdapter.available` — line 99
  - `method` `GraftAdapter._init_embedded_db` — line 112
  - `method` `GraftAdapter.query` — line 156
  - `method` `GraftAdapter.retrieve` — line 168
  - `method` `GraftAdapter.insert` — line 180
  - `method` `GraftAdapter.explore` — line 201
  - `method` `GraftAdapter.list_memories` — line 213
  - `method` `GraftAdapter.delete` — line 224
  - `method` `GraftAdapter.stats` — line 235
  - `method` `GraftAdapter._run_cli` — line 250
  - `method` `GraftAdapter._embedded_insert` — line 291
  - `method` `GraftAdapter._embedded_query` — line 318
  - `method` `GraftAdapter._embedded_retrieve` — line 346
  - `method` `GraftAdapter._embedded_explore` — line 357
  - `method` `GraftAdapter._embedded_list` — line 400
  - `method` `GraftAdapter._embedded_delete` — line 412
  - `method` `GraftAdapter._embedded_stats` — line 424
  - `method` `GraftAdapter._embedded_search` — line 439
- imports:
  - `__future__`
  - `json`
  - `living_assistant.security.security_utils`
  - `logging`
  - `os`
  - `pathlib`
  - `re`
  - `shutil`
  - `sqlite3`
  - `subprocess`
  - `threading`
  - `time`
  - `typing`

## `src/living_assistant/integrations/openmontage.py`

- language: `py`
- size: 3841 bytes
- hash: `47b9ecbbf416`
- symbols:
  - `class` `OpenMontageAdapter` — line 17
  - `method` `OpenMontageAdapter.__init__` — line 22
  - `method` `OpenMontageAdapter._sdk` — line 30
  - `method` `OpenMontageAdapter.list_pipelines` — line 54
  - `method` `OpenMontageAdapter.get_pipeline` — line 63
  - `method` `OpenMontageAdapter.list_tools` — line 72
  - `method` `OpenMontageAdapter.execute_tool` — line 85
- imports:
  - `__future__`
  - `importlib.util`
  - `logging`
  - `pathlib`
  - `sys`
  - `threading`
  - `typing`

## `src/living_assistant/integrations/openviking.py`

- language: `py`
- size: 9315 bytes
- hash: `a1349f22d51b`
- symbols:
  - `class` `OpenVikingAdapter` — line 18
  - `method` `OpenVikingAdapter.__init__` — line 29
  - `method` `OpenVikingAdapter._sdk` — line 52
  - `method` `OpenVikingAdapter._ensure_client` — line 71
  - `method` `OpenVikingAdapter._safe` — line 99
  - `method` `OpenVikingAdapter.available` — line 113
  - `method` `OpenVikingAdapter.health` — line 120
  - `method` `OpenVikingAdapter.recall` — line 128
  - `method` `OpenVikingAdapter.remember` — line 154
  - `method` `OpenVikingAdapter.search` — line 180
  - `method` `OpenVikingAdapter.capture_session` — line 205
- imports:
  - `__future__`
  - `importlib.util`
  - `logging`
  - `pathlib`
  - `sys`
  - `threading`
  - `typing`

## `src/living_assistant/integrations/scientific_skills.py`

- language: `py`
- size: 5110 bytes
- hash: `aadb24c70751`
- symbols:
  - `class` `ScientificSkillsAdapter` — line 11
  - `method` `ScientificSkillsAdapter.__init__` — line 20
  - `method` `ScientificSkillsAdapter._ensure_index` — line 30
  - `method` `ScientificSkillsAdapter.search_skills` — line 65
  - `method` `ScientificSkillsAdapter.get_skill` — line 102
- imports:
  - `__future__`
  - `logging`
  - `pathlib`
  - `threading`
  - `typing`
  - `yaml`

## `src/living_assistant/learning/__init__.py`

- language: `py`
- size: 53 bytes
- hash: `4fd27a6eb242`

## `src/living_assistant/learning/canary.py`

- language: `py`
- size: 21326 bytes
- hash: `f987f2e8145b`
- symbols:
  - `function` `_now` — line 50
  - `function` `_json` — line 54
  - `function` `_decode` — line 58
  - `function` `_free_port` — line 63
  - `function` `_host_command_argv` — line 69
  - `class` `CanaryStore` — line 84
  - `method` `CanaryStore.__init__` — line 85
  - `method` `CanaryStore.create` — line 91
  - `method` `CanaryStore.update` — line 97
  - `method` `CanaryStore.get` — line 103
  - `method` `CanaryStore.list` — line 109
  - `method` `CanaryStore.latest_for_evaluation` — line 116
  - `function` `_process_tree_stats` — line 121
  - `function` `_health_probe` — line 133
  - `function` `_summarize` — line 142
  - `function` `compare_canary` — line 154
  - `class` `CanaryEngine` — line 171
  - `method` `CanaryEngine.__init__` — line 172
  - `method` `CanaryEngine._profile_value` — line 179
  - `method` `CanaryEngine.status` — line 184
  - `method` `CanaryEngine._run_host_service` — line 187
  - `method` `CanaryEngine._run_container_service` — line 230
  - `method` `CanaryEngine.run` — line 254
- imports:
  - `__future__`
  - `datetime`
  - `httpx`
  - `json`
  - `living_assistant.core.approval`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.core.workspace`
  - `living_assistant.learning.evaluation`
  - `living_assistant.learning.improvements`
  - `living_assistant.security.sandbox`
  - `living_assistant.security.security_policy`
  - `os`
  - `pathlib`
  - `psutil`
  - `shlex`
  - `shutil`
  - `socket`
  - `sqlite3`
  - `statistics`
  - `subprocess`
  - `time`
  - `uuid`

## `src/living_assistant/learning/eval_engine.py`

- language: `py`
- size: 40055 bytes
- hash: `0255bc6437d3`
- symbols:
  - `class` `_RepairEvaluationAuthorization` — line 24
  - `method` `_RepairEvaluationAuthorization.__init__` — line 32
  - `function` `_sha_text` — line 53
  - `function` `_git` — line 56
  - `function` `_repo_root` — line 73
  - `function` `_reset_eval_worktree` — line 82
  - `function` `_copy_project` — line 90
  - `class` `EvaluationEngine` — line 117
  - `method` `EvaluationEngine.__init__` — line 118
  - `method` `EvaluationEngine._default_repetitions` — line 131
  - `method` `EvaluationEngine._warmup_runs` — line 137
  - `method` `EvaluationEngine.create_suite` — line 143
  - `method` `EvaluationEngine._resolve_plan` — line 171
  - `method` `EvaluationEngine._create_repair_authorization` — line 243
  - `method` `EvaluationEngine._consume_repair_authorization` — line 251
  - `method` `EvaluationEngine.sandbox_status` — line 277
  - `method` `EvaluationEngine._measure` — line 280
  - `method` `EvaluationEngine.evaluate` — line 292
  - `method` `EvaluationEngine.promote` — line 488
  - `method` `EvaluationEngine.revert_promotion` — line 548
  - `method` `EvaluationEngine.cleanup_branch` — line 586
- imports:
  - `__future__`
  - `eval_measure`
  - `eval_store`
  - `hashlib`
  - `json`
  - `living_assistant.core.approval`
  - `living_assistant.core.workspace`
  - `living_assistant.learning.improvements`
  - `living_assistant.security.sandbox`
  - `living_assistant.security.security_policy`
  - `os`
  - `pathlib`
  - `psutil`
  - `shutil`
  - `subprocess`
  - `time`

## `src/living_assistant/learning/eval_measure.py`

- language: `py`
- size: 7120 bytes
- hash: `8ea3eb20572b`
- symbols:
  - `function` `_kill_tree` — line 16
  - `function` `measure_command` — line 38
  - `function` `_aggregate_runs` — line 119
  - `function` `compare_benchmark` — line 130
- imports:
  - `__future__`
  - `living_assistant.learning.regression_detection`
  - `living_assistant.security.sandbox`
  - `living_assistant.security.security_policy`
  - `pathlib`
  - `psutil`
  - `shlex`
  - `statistics`
  - `subprocess`
  - `tempfile`
  - `time`

## `src/living_assistant/learning/eval_store.py`

- language: `py`
- size: 8625 bytes
- hash: `cc921667c4ce`
- symbols:
  - `function` `_now` — line 63
  - `function` `_json` — line 66
  - `function` `_decode` — line 69
  - `class` `EvaluationStore` — line 75
  - `method` `EvaluationStore.__init__` — line 76
  - `method` `EvaluationStore._ensure_suite_columns` — line 84
  - `method` `EvaluationStore.upsert_suite` — line 96
  - `method` `EvaluationStore.get_suite` — line 120
  - `method` `EvaluationStore.list_suites` — line 129
  - `method` `EvaluationStore.delete_suite` — line 133
  - `method` `EvaluationStore.create_evaluation` — line 138
  - `method` `EvaluationStore.update` — line 149
  - `method` `EvaluationStore.get` — line 161
  - `method` `EvaluationStore.list` — line 170
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `pathlib`
  - `sqlite3`
  - `uuid`

## `src/living_assistant/learning/evaluation.py`

- language: `py`
- size: 621 bytes
- hash: `30ef954b2489`
- imports:
  - `eval_engine`
  - `eval_measure`
  - `eval_store`
  - `living_assistant.core.config`

## `src/living_assistant/learning/experience.py`

- language: `py`
- size: 27634 bytes
- hash: `a999645c8f7e`

## `src/living_assistant/learning/improvements.py`

- language: `py`
- size: 14787 bytes
- hash: `7be006158e1c`
- symbols:
  - `function` `_assistant_repo_root_for` — line 35
  - `function` `is_protected_core_path` — line 50
  - `function` `_sha` — line 73
  - `class` `ImprovementStore` — line 76
  - `method` `ImprovementStore.__init__` — line 77
  - `method` `ImprovementStore.create` — line 84
  - `method` `ImprovementStore.get` — line 95
  - `method` `ImprovementStore.list` — line 106
  - `method` `ImprovementStore.set_status` — line 121
  - `class` `ImprovementEngine` — line 126
  - `method` `ImprovementEngine.__init__` — line 127
  - `method` `ImprovementEngine.context` — line 134
  - `method` `ImprovementEngine.propose` — line 185
  - `method` `ImprovementEngine.apply` — line 212
  - `method` `ImprovementEngine.rollback` — line 248
  - `method` `ImprovementEngine.reject` — line 276
- imports:
  - `__future__`
  - `ast`
  - `datetime`
  - `hashlib`
  - `json`
  - `living_assistant.core.approval`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.core.workspace`
  - `living_assistant.learning.patch_engine`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `sqlite3`
  - `typing`
  - `uuid`

## `src/living_assistant/learning/knowledge_gap_detection.py`

- language: `py`
- size: 6657 bytes
- hash: `525b1514ef64`
- symbols:
  - `function` `_task_tokens` — line 19
  - `class` `KnowledgeGapDetector` — line 27
  - `method` `KnowledgeGapDetector.__init__` — line 30
  - `method` `KnowledgeGapDetector._similarity` — line 38
  - `method` `KnowledgeGapDetector.detect` — line 43
- imports:
  - `__future__`
  - `collections`
  - `datetime`
  - `living_assistant.learning.experience`
  - `living_assistant.security.security_utils`
  - `re`
  - `typing`

## `src/living_assistant/learning/patch_engine.py`

- language: `py`
- size: 3212 bytes
- hash: `c5e4fee51f4a`
- symbols:
  - `class` `ASTSafePatchEngine` — line 8
  - `method` `ASTSafePatchEngine._symbols` — line 12
  - `method` `ASTSafePatchEngine.analyze` — line 27
- imports:
  - `__future__`
  - `ast`
  - `difflib`
  - `pathlib`

## `src/living_assistant/learning/regression_detection.py`

- language: `py`
- size: 4808 bytes
- hash: `c62de4d33817`
- symbols:
  - `function` `_clean` — line 8
  - `function` `_robust_sigma` — line 22
  - `function` `detect_metric_regression` — line 38
- imports:
  - `__future__`
  - `math`
  - `statistics`
  - `typing`

## `src/living_assistant/learning/repair_loop.py`

- language: `py`
- size: 12678 bytes
- hash: `448a76c92d67`
- symbols:
  - `class` `AutonomousRepairLoop` — line 16
  - `method` `AutonomousRepairLoop.__init__` — line 26
  - `method` `AutonomousRepairLoop._repair_payload` — line 46
  - `method` `AutonomousRepairLoop._failure_context` — line 73
  - `method` `AutonomousRepairLoop._plan_arguments` — line 90
  - `method` `AutonomousRepairLoop.run` — line 104
- imports:
  - `__future__`
  - `collections.abc`
  - `json`
  - `living_assistant.core.approval`
  - `living_assistant.learning.eval_engine`
  - `living_assistant.learning.improvements`
  - `living_assistant.security.security_utils`
  - `re`
  - `typing`

## `src/living_assistant/learning/run_history.py`

- language: `py`
- size: 10026 bytes
- hash: `07bb20ff9236`
- symbols:
  - `class` `RunHistoryStore` — line 44
  - `method` `RunHistoryStore.__init__` — line 47
  - `method` `RunHistoryStore._now` — line 56
  - `method` `RunHistoryStore._safe_metadata` — line 60
  - `method` `RunHistoryStore.record` — line 76
  - `method` `RunHistoryStore.start_run` — line 110
  - `method` `RunHistoryStore.record_tool` — line 124
  - `method` `RunHistoryStore.finish_run` — line 139
  - `method` `RunHistoryStore.get_event` — line 150
  - `method` `RunHistoryStore._time_range` — line 163
  - `method` `RunHistoryStore.query` — line 205
  - `method` `RunHistoryStore.prune` — line 245
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `re`
  - `typing`
  - `uuid`

## `src/living_assistant/memory.py`

- language: `py`
- size: 245 bytes
- hash: `cf759eb273d8`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/model_provider.py`

- language: `py`
- size: 261 bytes
- hash: `6508a2d8153a`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/models.py`

- language: `py`
- size: 245 bytes
- hash: `382af649e260`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/notifications.py`

- language: `py`
- size: 263 bytes
- hash: `5b7564e5f4d3`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/observer.py`

- language: `py`
- size: 253 bytes
- hash: `d8d1c6a36344`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/orchestrator.py`

- language: `py`
- size: 261 bytes
- hash: `f1cff405faf8`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/orchestrator_teams.py`

- language: `py`
- size: 273 bytes
- hash: `70789c0169f9`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/overlay.py`

- language: `py`
- size: 253 bytes
- hash: `36f75643dea2`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/personal_state.py`

- language: `py`
- size: 261 bytes
- hash: `b6fbdea8a988`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/platform_hardening.py`

- language: `py`
- size: 273 bytes
- hash: `7f47b38eba14`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/prompts.py`

- language: `py`
- size: 251 bytes
- hash: `24eb49eb50b6`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/quarantine.py`

- language: `py`
- size: 261 bytes
- hash: `6748aa1f8a5b`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/release_manager.py`

- language: `py`
- size: 267 bytes
- hash: `230dc86aba53`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/resource_manager.py`

- language: `py`
- size: 269 bytes
- hash: `57fb5657f4f5`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/routines.py`

- language: `py`
- size: 253 bytes
- hash: `63d32d762aea`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/runtime.py`

- language: `py`
- size: 247 bytes
- hash: `91af3b495db7`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/sandbox.py`

- language: `py`
- size: 255 bytes
- hash: `067b8f32db08`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/security/__init__.py`

- language: `py`
- size: 53 bytes
- hash: `e8d85cc8fd53`

## `src/living_assistant/security/api_auth.py`

- language: `py`
- size: 1193 bytes
- hash: `ad28aa4a3c2b`
- symbols:
  - `function` `ensure_api_token` — line 7
  - `function` `get_api_token` — line 30
- imports:
  - `living_assistant.core.config`
  - `os`
  - `pathlib`
  - `secrets`
  - `string`

## `src/living_assistant/security/keyring_vault.py`

- language: `py`
- size: 10761 bytes
- hash: `7a67ce16a931`
- symbols:
  - `function` `_machine_entropy` — line 23
  - `class` `MemoryVault` — line 34
  - `method` `MemoryVault.__init__` — line 37
  - `method` `MemoryVault.get_password` — line 40
  - `method` `MemoryVault.set_password` — line 43
  - `method` `MemoryVault.delete_password` — line 48
  - `method` `MemoryVault.list_keys` — line 54
  - `class` `EncryptedFileVault` — line 58
  - `method` `EncryptedFileVault.__init__` — line 61
  - `method` `EncryptedFileVault._derive_keys` — line 65
  - `method` `EncryptedFileVault._xor_keystream` — line 75
  - `method` `EncryptedFileVault._read_vault` — line 89
  - `method` `EncryptedFileVault._write_vault` — line 113
  - `method` `EncryptedFileVault.get_password` — line 133
  - `method` `EncryptedFileVault.set_password` — line 137
  - `method` `EncryptedFileVault.delete_password` — line 144
  - `method` `EncryptedFileVault.list_keys` — line 152
  - `class` `KeyringVault` — line 157
  - `method` `KeyringVault.__init__` — line 160
  - `method` `KeyringVault._detect_keyring` — line 172
  - `method` `KeyringVault.backend_type` — line 187
  - `method` `KeyringVault.status` — line 196
  - `method` `KeyringVault.get_password` — line 211
  - `method` `KeyringVault.set_password` — line 226
  - `method` `KeyringVault.delete_password` — line 244
  - `method` `KeyringVault.get_secret` — line 260
  - `method` `KeyringVault.set_secret` — line 263
  - `method` `KeyringVault.delete_secret` — line 266
  - `method` `KeyringVault.list_secrets` — line 269
  - `function` `get_keyring_vault` — line 278
- imports:
  - `__future__`
  - `base64`
  - `dataclasses`
  - `hashlib`
  - `hmac`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.security.security_utils`
  - `logging`
  - `os`
  - `pathlib`
  - `platform`
  - `secrets`
  - `typing`

## `src/living_assistant/security/quarantine.py`

- language: `py`
- size: 5698 bytes
- hash: `97542aebabce`
- symbols:
  - `function` `_sanitize_source_url` — line 21
  - `function` `sha256_file` — line 31
  - `function` `download_risk_reasons` — line 38
  - `function` `is_risky_download` — line 45
  - `class` `QuarantineVault` — line 50
  - `method` `QuarantineVault.__post_init__` — line 53
  - `method` `QuarantineVault._load` — line 58
  - `method` `QuarantineVault._save` — line 62
  - `method` `QuarantineVault.reserve` — line 64
  - `method` `QuarantineVault.register` — line 70
  - `method` `QuarantineVault.list` — line 84
  - `method` `QuarantineVault.get` — line 87
  - `method` `QuarantineVault.verify` — line 89
  - `method` `QuarantineVault.record_scan` — line 97
  - `method` `QuarantineVault.mark_released` — line 109
- imports:
  - `__future__`
  - `dataclasses`
  - `datetime`
  - `hashlib`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `pathlib`
  - `time`
  - `urllib.parse`
  - `uuid`

## `src/living_assistant/security/safe_commands.py`

- language: `py`
- size: 4640 bytes
- hash: `85ad70a9314e`
- symbols:
  - `class` `CommandExplanation` — line 12
  - `method` `CommandExplanation.to_dict` — line 23
  - `function` `_first_executable` — line 35
  - `function` `explain_command` — line 46
- imports:
  - `__future__`
  - `dataclasses`
  - `living_assistant.security.security_policy`
  - `os`
  - `pathlib`
  - `shlex`

## `src/living_assistant/security/sandbox.py`

- language: `py`
- size: 12487 bytes
- hash: `5e3d87ca50ca`
- symbols:
  - `function` `sanitized_env` — line 23
  - `function` `_size_bytes` — line 36
  - `class` `SandboxSpec` — line 46
  - `method` `SandboxSpec.public` — line 55
  - `class` `ContainerRuntime` — line 59
  - `method` `ContainerRuntime.__init__` — line 61
  - `method` `ContainerRuntime._detect` — line 66
  - `method` `ContainerRuntime.status` — line 71
  - `method` `ContainerRuntime._base_run_argv` — line 82
  - `method` `ContainerRuntime._stats` — line 107
  - `method` `ContainerRuntime.image_info` — line 124
  - `method` `ContainerRuntime.run_command` — line 133
  - `method` `ContainerRuntime.create_internal_network` — line 177
  - `method` `ContainerRuntime.remove_network` — line 186
  - `method` `ContainerRuntime.start_service` — line 193
  - `method` `ContainerRuntime.service_stats` — line 216
  - `method` `ContainerRuntime.logs` — line 220
  - `method` `ContainerRuntime.stop` — line 228
- imports:
  - `__future__`
  - `dataclasses`
  - `json`
  - `living_assistant.security.security_policy`
  - `os`
  - `pathlib`
  - `psutil`
  - `re`
  - `shlex`
  - `shutil`
  - `subprocess`
  - `tempfile`
  - `time`
  - `uuid`

## `src/living_assistant/security/security_guardian.py`

- language: `py`
- size: 42312 bytes
- hash: `e04cca20f3f9`
- symbols:
  - `function` `_now` — line 71
  - `function` `_json_hash` — line 75
  - `function` `_run` — line 80
  - `function` `_redact_cmdline` — line 92
  - `function` `_redact_text` — line 98
  - `function` `_redact_obj` — line 104
  - `function` `sha256_file` — line 111
  - `function` `_small_file_hash` — line 118
  - `function` `startup_inventory` — line 125
  - `function` `firewall_status` — line 182
  - `function` `encryption_status` — line 201
  - `function` `update_posture` — line 226
  - `function` `antivirus_posture` — line 245
  - `function` `inspect_process` — line 256
  - `function` `score_process_record` — line 295
  - `function` `process_triage` — line 310
  - `function` `network_activity_summary` — line 330
  - `function` `file_signature` — line 352
  - `function` `_parse_json_stdout` — line 368
  - `function` `evaluate_security_posture` — line 375
  - `class` `SecurityGuardian` — line 411
  - `method` `SecurityGuardian.__post_init__` — line 416
  - `method` `SecurityGuardian._state_get` — line 423
  - `method` `SecurityGuardian._state_set` — line 429
  - `method` `SecurityGuardian.record_finding` — line 433
  - `method` `SecurityGuardian.findings` — line 445
  - `method` `SecurityGuardian.resolve_finding` — line 458
  - `method` `SecurityGuardian._resolve_findings_with_key` — line 461
  - `method` `SecurityGuardian.posture` — line 472
  - `method` `SecurityGuardian.posture_scan` — line 480
  - `method` `SecurityGuardian.cached_posture` — line 488
  - `method` `SecurityGuardian.baseline_status` — line 491
  - `method` `SecurityGuardian.summary` — line 498
  - `method` `SecurityGuardian.process_triage` — line 504
  - `method` `SecurityGuardian.network_activity` — line 512
  - `method` `SecurityGuardian.listener_snapshot` — line 516
  - `method` `SecurityGuardian.capture_network_baseline` — line 534
  - `method` `SecurityGuardian.check_network_baseline` — line 538
  - `method` `SecurityGuardian.capture_startup_baseline` — line 555
  - `method` `SecurityGuardian.check_startup_baseline` — line 559
  - `method` `SecurityGuardian._snapshot_path` — line 574
  - `method` `SecurityGuardian.add_integrity_baseline` — line 595
  - `method` `SecurityGuardian._baseline_row` — line 603
  - `method` `SecurityGuardian.list_integrity_baselines` — line 609
  - `method` `SecurityGuardian.remove_integrity_baseline` — line 612
  - `method` `SecurityGuardian.check_integrity_baseline` — line 615
  - `method` `SecurityGuardian.check_all_integrity` — line 630
  - `method` `SecurityGuardian.refresh_integrity_baseline` — line 633
  - `method` `SecurityGuardian.periodic_scan` — line 638
  - `method` `SecurityGuardian.scan_path_antivirus` — line 669
  - `method` `SecurityGuardian.terminate_user_process` — line 684
- imports:
  - `__future__`
  - `dataclasses`
  - `datetime`
  - `hashlib`
  - `ipaddress`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sessions`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.system.platform_hardening`
  - `os`
  - `pathlib`
  - `platform`
  - `psutil`
  - `re`
  - `shutil`
  - `socket`
  - `sqlite3`
  - `subprocess`
  - `typing`
  - `uuid`

## `src/living_assistant/security/security_policy.py`

- language: `py`
- size: 8408 bytes
- hash: `77e11b20d975`
- symbols:
  - `class` `Risk` — line 7
  - `class` `Decision` — line 20
  - `function` `_safe_read_command` — line 70
  - `function` `classify_command` — line 76
  - `function` `_strip_sql_comments` — line 111
  - `function` `_single_statement` — line 206
  - `function` `is_read_only_sql` — line 213
  - `function` `sanitize_external_observation` — line 236
- imports:
  - `__future__`
  - `dataclasses`
  - `enum`
  - `re`

## `src/living_assistant/security/security_sensors.py`

- language: `py`
- size: 48934 bytes
- hash: `006c3292027f`
- symbols:
  - `function` `parse_auditd_text` — line 76
  - `function` `collect_linux_audit` — line 109
  - `function` `_read_jsonl` — line 127
  - `function` `dns_events_from` — line 140
  - `function` `_looks_algorithmic_domain` — line 152
  - `function` `summarize_dns` — line 163
  - `function` `correlate_security_events` — line 170
  - `function` `usb_inventory` — line 200
  - `function` `_chromium_extension_roots` — line 243
  - `function` `browser_extension_inventory` — line 258
  - `function` `_manifest_for_path` — line 296
  - `class` `RansomwareBehaviorDetector` — line 316
  - `method` `RansomwareBehaviorDetector.__post_init__` — line 321
  - `method` `RansomwareBehaviorDetector.observe` — line 324
  - `class` `SecuritySensorPlatform` — line 360
  - `method` `SecuritySensorPlatform.__init__` — line 361
  - `method` `SecuritySensorPlatform._state_get` — line 367
  - `method` `SecuritySensorPlatform._state_set` — line 373
  - `method` `SecuritySensorPlatform.status` — line 377
  - `method` `SecuritySensorPlatform.collect_events` — line 389
  - `method` `SecuritySensorPlatform.dns_context` — line 404
  - `method` `SecuritySensorPlatform.correlations` — line 417
  - `method` `SecuritySensorPlatform.tls_context` — line 442
  - `method` `SecuritySensorPlatform._yara_backend` — line 451
  - `method` `SecuritySensorPlatform.yara_scan` — line 459
  - `method` `SecuritySensorPlatform.reputation_hash` — line 490
  - `method` `SecuritySensorPlatform.reputation_file` — line 509
  - `method` `SecuritySensorPlatform.reputation_process` — line 514
  - `method` `SecuritySensorPlatform._signature_fields` — line 524
  - `method` `SecuritySensorPlatform.assess_binary` — line 538
  - `method` `SecuritySensorPlatform.trust_binary` — line 550
  - `method` `SecuritySensorPlatform.check_trusted_binaries` — line 560
  - `method` `SecuritySensorPlatform.capture_usb_baseline` — line 569
  - `method` `SecuritySensorPlatform.check_usb` — line 576
  - `method` `SecuritySensorPlatform.capture_extension_baseline` — line 583
  - `method` `SecuritySensorPlatform.check_extensions` — line 590
  - `method` `SecuritySensorPlatform.capture_backup_baseline` — line 601
  - `method` `SecuritySensorPlatform.list_backup_baselines` — line 609
  - `method` `SecuritySensorPlatform.check_backup_baseline` — line 615
  - `method` `SecuritySensorPlatform.observe_file_events` — line 627
  - `method` `SecuritySensorPlatform._network_isolation_commands` — line 633
  - `method` `SecuritySensorPlatform.isolate_network` — line 657
  - `method` `SecuritySensorPlatform.restore_network` — line 682
  - `method` `SecuritySensorPlatform.periodic_scan` — line 696
- imports:
  - `__future__`
  - `collections`
  - `dataclasses`
  - `datetime`
  - `hashlib`
  - `httpx`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.security.security_guardian`
  - `math`
  - `os`
  - `pathlib`
  - `platform`
  - `re`
  - `sensor_shared`
  - `sensors_macos`
  - `sensors_windows`
  - `shutil`
  - `subprocess`
  - `time`
  - `typing`

## `src/living_assistant/security/security_utils.py`

- language: `py`
- size: 8575 bytes
- hash: `09a51f6f3850`
- symbols:
  - `function` `is_sensitive_path` — line 25
  - `function` `redact_secrets` — line 46
  - `function` `_resolved_ips` — line 79
  - `function` `_non_public_ip` — line 95
  - `function` `url_network_scope` — line 106
  - `function` `resolve_url_target` — line 138
  - `function` `is_loopback_http_url` — line 172
  - `function` `is_local_model_endpoint` — line 185
  - `function` `safe_display_url` — line 189
- imports:
  - `__future__`
  - `ipaddress`
  - `pathlib`
  - `re`
  - `socket`
  - `urllib.parse`

## `src/living_assistant/security/sensor_shared.py`

- language: `py`
- size: 349 bytes
- hash: `1926c69d98ff`
- symbols:
  - `function` `_safe_json` — line 7
  - `function` `_event_time` — line 13
- imports:
  - `__future__`
  - `json`
  - `living_assistant.security.security_guardian`

## `src/living_assistant/security/sensors_macos.py`

- language: `py`
- size: 1375 bytes
- hash: `9150ccda1dcd`
- symbols:
  - `function` `collect_macos_unified_log` — line 9
- imports:
  - `__future__`
  - `living_assistant.security.security_guardian`
  - `platform`
  - `sensor_shared`
  - `shutil`

## `src/living_assistant/security/sensors_windows.py`

- language: `py`
- size: 5767 bytes
- hash: `14cfe1d17a70`
- symbols:
  - `function` `normalize_sysmon_event` — line 12
  - `function` `_powershell_event_script` — line 43
  - `function` `normalize_windows_security_event` — line 58
  - `function` `collect_windows_eventlog` — line 73
- imports:
  - `__future__`
  - `living_assistant.security.security_guardian`
  - `platform`
  - `sensor_shared`

## `src/living_assistant/security/verifier.py`

- language: `py`
- size: 2915 bytes
- hash: `693eac7b70ce`
- symbols:
  - `class` `VerificationResult` — line 7
  - `class` `Verifier` — line 25
  - `method` `Verifier.__init__` — line 26
  - `method` `Verifier.verify` — line 31
- imports:
  - `contextlib`
  - `json`
  - `living_assistant.core.model_provider`
  - `pydantic`
  - `typing`

## `src/living_assistant/security_guardian.py`

- language: `py`
- size: 275 bytes
- hash: `1592c27db728`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/security_policy.py`

- language: `py`
- size: 271 bytes
- hash: `ac4600ec3949`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/security_sensors.py`

- language: `py`
- size: 273 bytes
- hash: `bf070305e395`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/security_utils.py`

- language: `py`
- size: 269 bytes
- hash: `92b743123658`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/sessions.py`

- language: `py`
- size: 249 bytes
- hash: `f4372e1466a5`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/skills.py`

- language: `py`
- size: 116 bytes
- hash: `aea15e197d80`
- imports:
  - `living_assistant.skills`

## `src/living_assistant/skills/__init__.py`

- language: `py`
- size: 1491 bytes
- hash: `590999e73dbb`
- imports:
  - `living_assistant.core.skills`
  - `living_assistant.skills.adapters`
  - `living_assistant.skills.collections`
  - `living_assistant.skills.creator`
  - `living_assistant.skills.extractor`
  - `living_assistant.skills.guards`
  - `living_assistant.skills.manager`
  - `living_assistant.skills.manifest`
  - `living_assistant.skills.package`
  - `living_assistant.skills.runner`
  - `living_assistant.skills.store`

## `src/living_assistant/skills/adapters.py`

- language: `py`
- size: 11692 bytes
- hash: `72e693913f27`
- symbols:
  - `class` `PortableToolAdapter` — line 13
  - `method` `PortableToolAdapter.__init__` — line 18
  - `method` `PortableToolAdapter.set_step_context` — line 39
  - `method` `PortableToolAdapter._resolve` — line 42
  - `method` `PortableToolAdapter.files_list` — line 50
  - `method` `PortableToolAdapter.files_read` — line 75
  - `method` `PortableToolAdapter.files_move` — line 82
  - `method` `PortableToolAdapter.files_write` — line 182
  - `method` `PortableToolAdapter.documents_extract` — line 193
  - `method` `PortableToolAdapter.notifications_show` — line 216
  - `method` `PortableToolAdapter.undo_action` — line 229
- imports:
  - `__future__`
  - `living_assistant.core.workspace`
  - `living_assistant.skills.extractor`
  - `living_assistant.skills.guards`
  - `os`
  - `pathlib`
  - `shutil`
  - `typing`

## `src/living_assistant/skills/collections.py`

- language: `py`
- size: 4908 bytes
- hash: `bf6ebc533744`
- symbols:
  - `class` `ExternalSkillCollections` — line 16
  - `method` `ExternalSkillCollections.__init__` — line 25
  - `method` `ExternalSkillCollections.scan_collections` — line 29
  - `method` `ExternalSkillCollections.import_skill` — line 63
- imports:
  - `__future__`
  - `living_assistant.skills.manifest`
  - `living_assistant.skills.package`
  - `living_assistant.skills.store`
  - `os`
  - `pathlib`
  - `typing`

## `src/living_assistant/skills/creator.py`

- language: `py`
- size: 11180 bytes
- hash: `b1cb27e6ce34`
- symbols:
  - `class` `SkillCreator` — line 21
  - `method` `SkillCreator.__init__` — line 24
  - `method` `SkillCreator._generate_skill_id` — line 36
  - `method` `SkillCreator._build_deterministic_draft` — line 43
  - `method` `SkillCreator.create_draft` — line 241
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.skills.manifest`
  - `living_assistant.skills.package`
  - `living_assistant.skills.store`
  - `living_assistant.tools.registry`
  - `re`
  - `typing`

## `src/living_assistant/skills/evaluator.py`

- language: `py`
- size: 9870 bytes
- hash: `705fceeb4a5a`
- symbols:
  - `class` `DeclarativeEvaluationError` — line 8
  - `function` `_resolve_context_path` — line 12
  - `function` `interpolate_variables` — line 29
  - `class` `_SafeConditionVisitor` — line 61
  - `method` `_SafeConditionVisitor.__init__` — line 93
  - `method` `_SafeConditionVisitor.visit` — line 96
  - `method` `_SafeConditionVisitor.visit_Expression` — line 103
  - `method` `_SafeConditionVisitor.visit_Constant` — line 106
  - `method` `_SafeConditionVisitor.visit_Name` — line 109
  - `method` `_SafeConditionVisitor.visit_Attribute` — line 119
  - `method` `_SafeConditionVisitor.visit_Subscript` — line 125
  - `method` `_SafeConditionVisitor.visit_Index` — line 133
  - `method` `_SafeConditionVisitor.visit_UnaryOp` — line 136
  - `method` `_SafeConditionVisitor.visit_BoolOp` — line 144
  - `method` `_SafeConditionVisitor.visit_BinOp` — line 157
  - `method` `_SafeConditionVisitor.visit_Compare` — line 166
  - `method` `_SafeConditionVisitor._apply_cmp` — line 176
  - `function` `evaluate_condition` — line 200
  - `function` `validate_workflow_contract` — line 228
- imports:
  - `__future__`
  - `ast`
  - `re`
  - `typing`

## `src/living_assistant/skills/examples.py`

- language: `py`
- size: 7407 bytes
- hash: `6637769d2210`
- symbols:
  - `function` `get_daily_briefing_manifest` — line 15
  - `function` `get_downloads_organizer_manifest` — line 62
  - `function` `get_invoice_organizer_manifest` — line 110
  - `function` `seed_reference_skills` — line 165
- imports:
  - `__future__`
  - `living_assistant.skills.manifest`
  - `living_assistant.skills.package`
  - `pathlib`

## `src/living_assistant/skills/extractor.py`

- language: `py`
- size: 13280 bytes
- hash: `b20e6b01ea36`
- symbols:
  - `class` `_HTMLTextExtractor` — line 10
  - `method` `_HTMLTextExtractor.__init__` — line 11
  - `method` `_HTMLTextExtractor.handle_data` — line 15
  - `method` `_HTMLTextExtractor.get_text` — line 19
  - `class` `DocumentExtractor` — line 23
  - `method` `DocumentExtractor.sanitize_for_path` — line 55
  - `method` `DocumentExtractor.extract_text` — line 64
  - `method` `DocumentExtractor.extract_invoice_fields` — line 121
- imports:
  - `__future__`
  - `hashlib`
  - `html.parser`
  - `pathlib`
  - `re`
  - `typing`

## `src/living_assistant/skills/guards.py`

- language: `py`
- size: 5696 bytes
- hash: `5d00f76b0df6`
- symbols:
  - `class` `SkillPermissionViolation` — line 13
  - `class` `SkillPermissionGuard` — line 17
  - `method` `SkillPermissionGuard.__init__` — line 20
  - `method` `SkillPermissionGuard.check_tool_allowlist` — line 28
  - `method` `SkillPermissionGuard.validate_path` — line 37
  - `method` `SkillPermissionGuard.check_network` — line 96
  - `method` `SkillPermissionGuard.check_subprocess` — line 104
- imports:
  - `__future__`
  - `living_assistant.core.approval`
  - `living_assistant.core.workspace`
  - `living_assistant.security.security_utils`
  - `living_assistant.skills.manifest`
  - `os`
  - `pathlib`
  - `typing`

## `src/living_assistant/skills/manager.py`

- language: `py`
- size: 12194 bytes
- hash: `a523866cf7ee`
- symbols:
  - `class` `SkillManager` — line 22
  - `method` `SkillManager.__init__` — line 25
  - `method` `SkillManager._seed_builtins_if_needed` — line 49
  - `method` `SkillManager.list_skills` — line 69
  - `method` `SkillManager.get_skill` — line 91
  - `method` `SkillManager.create_draft` — line 112
  - `method` `SkillManager.update_skill` — line 115
  - `method` `SkillManager.activate_skill` — line 136
  - `method` `SkillManager.disable_skill` — line 169
  - `method` `SkillManager.archive_skill` — line 172
  - `method` `SkillManager.rollback_skill` — line 175
  - `method` `SkillManager.export_skill` — line 182
  - `method` `SkillManager.import_skill_archive` — line 189
  - `method` `SkillManager.execute_skill` — line 195
  - `method` `SkillManager.undo_execution` — line 226
  - `method` `SkillManager.reconcile_execution` — line 254
  - `method` `SkillManager.match_active_skills` — line 258
  - `method` `SkillManager.get_orchestrator_summary` — line 271
- imports:
  - `__future__`
  - `datetime`
  - `living_assistant.core.approval`
  - `living_assistant.core.workspace`
  - `living_assistant.skills.creator`
  - `living_assistant.skills.examples`
  - `living_assistant.skills.manifest`
  - `living_assistant.skills.package`
  - `living_assistant.skills.runner`
  - `living_assistant.skills.store`
  - `living_assistant.tools.registry`
  - `pathlib`
  - `typing`

## `src/living_assistant/skills/manifest.py`

- language: `py`
- size: 8559 bytes
- hash: `f2c0b3c7baa5`
- symbols:
  - `class` `SkillPermissionScope` — line 14
  - `method` `SkillPermissionScope.permission_hash` — line 22
  - `class` `SkillStep` — line 36
  - `class` `SkillLimits` — line 54
  - `class` `SkillProvenance` — line 60
  - `class` `SkillExample` — line 67
  - `class` `SkillManifest` — line 73
  - `method` `SkillManifest.validate_id` — line 94
  - `method` `SkillManifest.validate_version` — line 102
  - `method` `SkillManifest.validate_against_tools` — line 108
  - `method` `SkillManifest.to_json` — line 123
  - `method` `SkillManifest.from_json` — line 127
  - `function` `convert_legacy_skill` — line 133
- imports:
  - `__future__`
  - `hashlib`
  - `json`
  - `pydantic`
  - `re`
  - `typing`

## `src/living_assistant/skills/package.py`

- language: `py`
- size: 8531 bytes
- hash: `d7dc780c85ea`
- symbols:
  - `function` `default_skills_dir` — line 15
  - `class` `SkillPackage` — line 22
  - `method` `SkillPackage.__init__` — line 25
  - `method` `SkillPackage.skill_id` — line 31
  - `method` `SkillPackage.version` — line 35
  - `method` `SkillPackage.load` — line 39
  - `method` `SkillPackage.save` — line 55
  - `method` `SkillPackage.deterministic_hash` — line 77
  - `method` `SkillPackage.create_snapshot` — line 96
  - `method` `SkillPackage.export_zip` — line 106
  - `method` `SkillPackage.import_zip` — line 117
- imports:
  - `__future__`
  - `io`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.skills.manifest`
  - `os`
  - `pathlib`
  - `shutil`
  - `typing`
  - `zipfile`

## `src/living_assistant/skills/runner.py`

- language: `py`
- size: 11669 bytes
- hash: `f8503617b68d`
- symbols:
  - `class` `SkillExecutionError` — line 16
  - `class` `SkillExecutor` — line 20
  - `method` `SkillExecutor.__init__` — line 25
  - `method` `SkillExecutor.cancel_execution` — line 40
  - `method` `SkillExecutor._execute_single_tool_call` — line 43
  - `method` `SkillExecutor.execute` — line 88
- imports:
  - `__future__`
  - `datetime`
  - `living_assistant.core.workspace`
  - `living_assistant.skills.adapters`
  - `living_assistant.skills.evaluator`
  - `living_assistant.skills.guards`
  - `living_assistant.skills.manifest`
  - `living_assistant.skills.store`
  - `living_assistant.tools.registry`
  - `time`
  - `typing`

## `src/living_assistant/skills/store.py`

- language: `py`
- size: 19025 bytes
- hash: `9a829690f200`
- symbols:
  - `class` `SkillStore` — line 87
  - `method` `SkillStore.__init__` — line 90
  - `method` `SkillStore.register_skill` — line 105
  - `method` `SkillStore.save_version` — line 126
  - `method` `SkillStore.get_lifecycle` — line 142
  - `method` `SkillStore.set_state` — line 146
  - `method` `SkillStore.approve_skill` — line 158
  - `method` `SkillStore.is_approved` — line 177
  - `method` `SkillStore.invalidate_approval` — line 198
  - `method` `SkillStore.list_skills` — line 211
  - `method` `SkillStore.get_version` — line 222
  - `method` `SkillStore.get_versions` — line 228
  - `method` `SkillStore.rollback_version` — line 235
  - `method` `SkillStore.record_execution_start` — line 254
  - `method` `SkillStore.record_execution_finish` — line 267
  - `method` `SkillStore.record_undo_action` — line 285
  - `method` `SkillStore.get_undo_actions` — line 294
  - `method` `SkillStore.get_executions` — line 305
  - `method` `SkillStore.record_action_planned` — line 324
  - `method` `SkillStore.record_action_started` — line 361
  - `method` `SkillStore.record_action_succeeded` — line 369
  - `method` `SkillStore.record_action_failed` — line 377
  - `method` `SkillStore.record_action_uncertain` — line 385
  - `method` `SkillStore.get_action_records` — line 393
  - `method` `SkillStore.reconcile_interrupted_run` — line 406
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.skills.manifest`
  - `pathlib`
  - `sqlite3`
  - `typing`
  - `uuid`

## `src/living_assistant/skills/tools.py`

- language: `py`
- size: 3513 bytes
- hash: `6656600e3bb5`
- symbols:
  - `function` `build_skill_tools` — line 8
- imports:
  - `__future__`
  - `living_assistant.skills.manager`
  - `living_assistant.tools.base`
  - `typing`

## `src/living_assistant/sqlite_utils.py`

- language: `py`
- size: 257 bytes
- hash: `057090df8d52`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/storage_utils.py`

- language: `py`
- size: 259 bytes
- hash: `47ccc846662a`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/supervisors/__init__.py`

- language: `py`
- size: 0 bytes
- hash: `e3b0c44298fc`

## `src/living_assistant/supervisors/development.py`

- language: `py`
- size: 4152 bytes
- hash: `c1627b6bd268`
- symbols:
  - `class` `DevelopmentSupervisor` — line 35
  - `method` `DevelopmentSupervisor.__init__` — line 36
  - `method` `DevelopmentSupervisor._execute_specialist` — line 41
  - `method` `DevelopmentSupervisor.dispatch` — line 76
- imports:
  - `__future__`
  - `concurrent.futures`
  - `json`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.models`
  - `logging`
  - `typing`

## `src/living_assistant/supervisors/executive.py`

- language: `py`
- size: 2730 bytes
- hash: `de0db565c756`
- symbols:
  - `class` `ExecutiveSupervisor` — line 27
  - `method` `ExecutiveSupervisor.__init__` — line 28
  - `method` `ExecutiveSupervisor._model_lease` — line 33
  - `method` `ExecutiveSupervisor.route` — line 40
- imports:
  - `__future__`
  - `contextlib`
  - `json`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.models`

## `src/living_assistant/supervisors/knowledge.py`

- language: `py`
- size: 3712 bytes
- hash: `68f00da14982`
- symbols:
  - `class` `KnowledgeSupervisor` — line 31
  - `method` `KnowledgeSupervisor.__init__` — line 32
  - `method` `KnowledgeSupervisor._execute_specialist` — line 37
  - `method` `KnowledgeSupervisor.dispatch` — line 72
- imports:
  - `__future__`
  - `concurrent.futures`
  - `json`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.models`
  - `logging`
  - `typing`

## `src/living_assistant/supervisors/operations.py`

- language: `py`
- size: 3818 bytes
- hash: `24d8a1a98528`
- symbols:
  - `class` `OperationsSupervisor` — line 32
  - `method` `OperationsSupervisor.__init__` — line 33
  - `method` `OperationsSupervisor._execute_specialist` — line 38
  - `method` `OperationsSupervisor.dispatch` — line 73
- imports:
  - `__future__`
  - `concurrent.futures`
  - `json`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.models`
  - `logging`
  - `typing`

## `src/living_assistant/supervisors/personal.py`

- language: `py`
- size: 3774 bytes
- hash: `815b105239ae`
- symbols:
  - `class` `PersonalSupervisor` — line 32
  - `method` `PersonalSupervisor.__init__` — line 33
  - `method` `PersonalSupervisor._execute_specialist` — line 38
  - `method` `PersonalSupervisor.dispatch` — line 73
- imports:
  - `__future__`
  - `concurrent.futures`
  - `json`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.models`
  - `logging`
  - `typing`

## `src/living_assistant/supervisors/security.py`

- language: `py`
- size: 3814 bytes
- hash: `ab124a6d379c`
- symbols:
  - `class` `SecuritySupervisor` — line 32
  - `method` `SecuritySupervisor.__init__` — line 33
  - `method` `SecuritySupervisor._execute_specialist` — line 38
  - `method` `SecuritySupervisor.dispatch` — line 73
- imports:
  - `__future__`
  - `concurrent.futures`
  - `json`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.models`
  - `logging`
  - `typing`

## `src/living_assistant/supervisors/upgrade.py`

- language: `py`
- size: 3697 bytes
- hash: `ef53a32fd3f3`
- symbols:
  - `class` `UpgradeSupervisor` — line 31
  - `method` `UpgradeSupervisor.__init__` — line 32
  - `method` `UpgradeSupervisor._execute_specialist` — line 37
  - `method` `UpgradeSupervisor.dispatch` — line 72
- imports:
  - `__future__`
  - `concurrent.futures`
  - `json`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.models`
  - `logging`
  - `typing`

## `src/living_assistant/system/__init__.py`

- language: `py`
- size: 51 bytes
- hash: `29f2ffae3c25`

## `src/living_assistant/system/article_extractor.py`

- language: `py`
- size: 5554 bytes
- hash: `e8c1e50a12ab`
- symbols:
  - `class` `ArticleExtractor` — line 16
  - `method` `ArticleExtractor.__init__` — line 22
  - `method` `ArticleExtractor.extract` — line 25
  - `method` `ArticleExtractor._extract_title_tag` — line 117
  - `method` `ArticleExtractor._fallback_html_strip` — line 125
  - `function` `get_article_extractor` — line 143
- imports:
  - `__future__`
  - `hashlib`
  - `living_assistant.security.security_policy`
  - `living_assistant.security.security_utils`
  - `logging`
  - `pathlib`
  - `re`
  - `typing`
  - `urllib.parse`

## `src/living_assistant/system/codebase_index.py`

- language: `py`
- size: 24179 bytes
- hash: `f4c48c0493c9`
- symbols:
  - `class` `CodeChunk` — line 45
  - `class` `CodebaseIndex` — line 53
  - `method` `CodebaseIndex.__init__` — line 63
  - `method` `CodebaseIndex._init_db` — line 87
  - `method` `CodebaseIndex._project_id` — line 118
  - `method` `CodebaseIndex._is_binary` — line 122
  - `method` `CodebaseIndex._iter_source_files` — line 131
  - `method` `CodebaseIndex._bounded_chunks` — line 155
  - `method` `CodebaseIndex._python_chunks` — line 183
  - `method` `CodebaseIndex._markdown_chunks` — line 209
  - `method` `CodebaseIndex._generic_chunks` — line 228
  - `method` `CodebaseIndex._chunks_for_file` — line 250
  - `method` `CodebaseIndex._features` — line 271
  - `method` `CodebaseIndex._cosine` — line 313
  - `method` `CodebaseIndex._dump_vector` — line 319
  - `method` `CodebaseIndex._load_vector` — line 323
  - `method` `CodebaseIndex.index_project` — line 330
  - `method` `CodebaseIndex.status` — line 400
  - `method` `CodebaseIndex.search` — line 419
  - `method` `CodebaseIndex.incremental_update` — line 466
- imports:
  - `__future__`
  - `ast`
  - `dataclasses`
  - `hashlib`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.core.workspace`
  - `living_assistant.security.security_utils`
  - `math`
  - `os`
  - `pathlib`
  - `re`
  - `time`
  - `typing`

## `src/living_assistant/system/config_reload.py`

- language: `py`
- size: 5220 bytes
- hash: `81925ef3a51c`
- symbols:
  - `class` `ConfigReloader` — line 38
  - `method` `ConfigReloader.__init__` — line 45
  - `method` `ConfigReloader._hash_file` — line 56
  - `method` `ConfigReloader._set_mapping_in_place` — line 65
  - `method` `ConfigReloader._apply` — line 73
  - `method` `ConfigReloader.poll` — line 108
- imports:
  - `__future__`
  - `copy`
  - `hashlib`
  - `living_assistant.core.config`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `typing`

## `src/living_assistant/system/daemon.py`

- language: `py`
- size: 23340 bytes
- hash: `07427d454db2`
- symbols:
  - `class` `NervousSystem` — line 16
  - `method` `NervousSystem.__init__` — line 18
  - `method` `NervousSystem._on_config_reload` — line 32
  - `method` `NervousSystem._ports` — line 57
  - `method` `NervousSystem._process_events` — line 60
  - `method` `NervousSystem._todo_events` — line 87
  - `method` `NervousSystem.tick` — line 94
  - `method` `NervousSystem._event_message` — line 263
  - `method` `NervousSystem.run_forever` — line 297
- imports:
  - `__future__`
  - `httpx`
  - `living_assistant.core.config`
  - `living_assistant.core.memory`
  - `living_assistant.security.security_utils`
  - `living_assistant.system.config_reload`
  - `living_assistant.system.notifications`
  - `living_assistant.system.platform_hardening`
  - `living_assistant.system.routines`
  - `living_assistant.system.watchers`
  - `living_assistant.tools.security`
  - `living_assistant.tools.shell`
  - `psutil`
  - `signal`
  - `threading`
  - `time`
  - `traceback`

## `src/living_assistant/system/disk_cache.py`

- language: `py`
- size: 7399 bytes
- hash: `ef03c57c446f`
- symbols:
  - `class` `MemoryCacheFallback` — line 17
  - `method` `MemoryCacheFallback.__init__` — line 20
  - `method` `MemoryCacheFallback.get` — line 25
  - `method` `MemoryCacheFallback.set` — line 38
  - `method` `MemoryCacheFallback.delete` — line 43
  - `method` `MemoryCacheFallback.clear` — line 49
  - `method` `MemoryCacheFallback.volume` — line 55
  - `method` `MemoryCacheFallback.__len__` — line 58
  - `class` `DiskCacheManager` — line 62
  - `method` `DiskCacheManager.__init__` — line 72
  - `method` `DiskCacheManager._init_backend` — line 78
  - `method` `DiskCacheManager.backend` — line 90
  - `method` `DiskCacheManager._format_key` — line 93
  - `method` `DiskCacheManager.get` — line 97
  - `method` `DiskCacheManager.set` — line 106
  - `method` `DiskCacheManager.delete` — line 124
  - `method` `DiskCacheManager.clear` — line 132
  - `method` `DiskCacheManager.stats` — line 158
  - `method` `DiskCacheManager.cached` — line 171
  - `function` `get_disk_cache` — line 202
- imports:
  - `__future__`
  - `functools`
  - `hashlib`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.security.security_utils`
  - `logging`
  - `pathlib`
  - `time`
  - `typing`

## `src/living_assistant/system/environment.py`

- language: `py`
- size: 16619 bytes
- hash: `facff5621661`
- symbols:
  - `class` `PlatformPaths` — line 35
  - `method` `PlatformPaths.data_dir` — line 41
  - `method` `PlatformPaths.config_dir` — line 45
  - `method` `PlatformPaths.cache_dir` — line 49
  - `method` `PlatformPaths.log_dir` — line 53
  - `method` `PlatformPaths.state_dir` — line 57
  - `method` `PlatformPaths.venvs_dir` — line 61
  - `method` `PlatformPaths.ensure_dirs` — line 64
  - `method` `PlatformPaths.migrate_from_legacy` — line 83
  - `class` `UVEnvironmentManager` — line 124
  - `method` `UVEnvironmentManager.__init__` — line 127
  - `method` `UVEnvironmentManager.uv_path` — line 132
  - `method` `UVEnvironmentManager.has_uv` — line 136
  - `method` `UVEnvironmentManager.backend` — line 140
  - `method` `UVEnvironmentManager.status` — line 143
  - `method` `UVEnvironmentManager._resolve_env_dir` — line 153
  - `method` `UVEnvironmentManager.get_python_executable` — line 159
  - `method` `UVEnvironmentManager.create_environment` — line 178
  - `method` `UVEnvironmentManager.install` — line 220
  - `method` `UVEnvironmentManager.run` — line 287
  - `method` `UVEnvironmentManager.run_ephemeral` — line 385
  - `function` `get_platform_paths` — line 472
  - `function` `get_environment_manager` — line 480
- imports:
  - `__future__`
  - `dataclasses`
  - `hashlib`
  - `json`
  - `living_assistant.security.security_utils`
  - `logging`
  - `os`
  - `pathlib`
  - `platformdirs`
  - `re`
  - `shutil`
  - `subprocess`
  - `sys`
  - `typing`

## `src/living_assistant/system/groups.py`

- language: `py`
- size: 8739 bytes
- hash: `7c0f9c024d31`
- symbols:
  - `class` `ProjectGroupRegistry` — line 9
  - `method` `ProjectGroupRegistry.__init__` — line 10
  - `method` `ProjectGroupRegistry._load` — line 14
  - `method` `ProjectGroupRegistry._save` — line 18
  - `method` `ProjectGroupRegistry.add` — line 20
  - `method` `ProjectGroupRegistry.set_desired_state` — line 43
  - `method` `ProjectGroupRegistry.list` — line 49
  - `method` `ProjectGroupRegistry.get` — line 50
  - `method` `ProjectGroupRegistry.remove` — line 53
  - `class` `ProjectGroupController` — line 56
  - `method` `ProjectGroupController.__init__` — line 57
  - `method` `ProjectGroupController.plan` — line 60
  - `method` `ProjectGroupController.start` — line 90
  - `method` `ProjectGroupController.health` — line 121
  - `method` `ProjectGroupController.health_all` — line 135
  - `method` `ProjectGroupController.stop` — line 138
- imports:
  - `__future__`
  - `concurrent.futures`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `living_assistant.security.security_policy`
  - `pathlib`
  - `time`

## `src/living_assistant/system/hardware.py`

- language: `py`
- size: 3216 bytes
- hash: `db272a14ecea`
- symbols:
  - `class` `HardwareInfo` — line 11
  - `method` `HardwareInfo.to_dict` — line 25
  - `function` `_nvidia_info` — line 29
  - `function` `_apple_silicon` — line 58
  - `function` `detect_hardware` — line 62
  - `function` `choose_profile` — line 88
- imports:
  - `__future__`
  - `dataclasses`
  - `platform`
  - `psutil`
  - `shutil`
  - `subprocess`

## `src/living_assistant/system/model_usage.py`

- language: `py`
- size: 9900 bytes
- hash: `ad2ddedcfeb4`
- symbols:
  - `class` `ModelUsageStore` — line 31
  - `method` `ModelUsageStore.__init__` — line 39
  - `method` `ModelUsageStore._now` — line 51
  - `method` `ModelUsageStore._bounded_identifier` — line 55
  - `method` `ModelUsageStore._as_nonnegative_int` — line 62
  - `method` `ModelUsageStore._extract_tokens` — line 72
  - `method` `ModelUsageStore._maybe_prune` — line 95
  - `method` `ModelUsageStore.record_response` — line 104
  - `method` `ModelUsageStore.summary` — line 157
  - `method` `ModelUsageStore.prune` — line 235
- imports:
  - `__future__`
  - `datetime`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `math`
  - `pathlib`
  - `threading`
  - `typing`

## `src/living_assistant/system/notifications.py`

- language: `py`
- size: 7462 bytes
- hash: `cdb74bbea6d0`
- symbols:
  - `class` `Notifier` — line 10
  - `method` `Notifier.__init__` — line 11
  - `method` `Notifier._load_queue` — line 20
  - `method` `Notifier._save_queue` — line 28
  - `method` `Notifier.is_quiet` — line 32
  - `method` `Notifier._enqueue` — line 38
  - `method` `Notifier._send_now` — line 50
  - `method` `Notifier._play_sound` — line 81
  - `method` `Notifier.send` — line 116
  - `method` `Notifier.queued` — line 126
  - `method` `Notifier.flush` — line 129
- imports:
  - `__future__`
  - `datetime`
  - `hashlib`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `living_assistant.security.security_utils`
  - `os`
  - `pathlib`
  - `platform`
  - `shutil`
  - `subprocess`
  - `threading`
  - `uuid`

## `src/living_assistant/system/observer.py`

- language: `py`
- size: 8861 bytes
- hash: `d0239f2e5c9b`
- symbols:
  - `function` `_get_active_window_text` — line 16
  - `class` `ProactiveInquiry` — line 32
  - `method` `ProactiveInquiry.to_dict` — line 40
  - `class` `ProactiveScreenObserver` — line 44
  - `method` `ProactiveScreenObserver.__init__` — line 47
  - `method` `ProactiveScreenObserver.start` — line 66
  - `method` `ProactiveScreenObserver.stop` — line 73
  - `method` `ProactiveScreenObserver._run_loop` — line 78
  - `method` `ProactiveScreenObserver._tick` — line 86
  - `method` `ProactiveScreenObserver.trigger_inquiry` — line 127
  - `method` `ProactiveScreenObserver.get_pending_inquiries` — line 150
  - `method` `ProactiveScreenObserver.resolve_inquiry` — line 154
- imports:
  - `__future__`
  - `ctypes`
  - `datetime`
  - `living_assistant.core.event_bus`
  - `living_assistant.learning.experience`
  - `threading`
  - `time`
  - `typing`
  - `uuid`

## `src/living_assistant/system/onboarding.py`

- language: `py`
- size: 4675 bytes
- hash: `8fe78f92caae`
- symbols:
  - `class` `OnboardingManager` — line 16
  - `method` `OnboardingManager.__init__` — line 19
  - `method` `OnboardingManager.status` — line 23
  - `method` `OnboardingManager.allowed_connector_capabilities` — line 35
  - `method` `OnboardingManager.complete` — line 39
- imports:
  - `__future__`
  - `living_assistant.connectors.connectors`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `pathlib`
  - `re`
  - `time`
  - `typing`
  - `yaml`

## `src/living_assistant/system/peer_agents.py`

- language: `py`
- size: 15408 bytes
- hash: `cbe4a71bfbb1`
- symbols:
  - `class` `PeerAgentManager` — line 26
  - `method` `PeerAgentManager.__init__` — line 29
  - `method` `PeerAgentManager.enabled` — line 57
  - `method` `PeerAgentManager._load_identity` — line 60
  - `method` `PeerAgentManager._trusted_ids` — line 72
  - `method` `PeerAgentManager._token` — line 75
  - `method` `PeerAgentManager._allowed_roles` — line 79
  - `method` `PeerAgentManager._decode_properties` — line 84
  - `method` `PeerAgentManager._record_service` — line 92
  - `method` `PeerAgentManager._remove_service` — line 127
  - `method` `PeerAgentManager.ensure_started` — line 134
  - `method` `PeerAgentManager.stop` — line 194
  - `method` `PeerAgentManager.poll_events` — line 212
  - `method` `PeerAgentManager.list_peers` — line 219
  - `method` `PeerAgentManager._score` — line 230
  - `method` `PeerAgentManager._select_peer` — line 233
  - `method` `PeerAgentManager.delegate` — line 249
  - `method` `PeerAgentManager.accept_delegation` — line 292
- imports:
  - `__future__`
  - `hmac`
  - `httpx`
  - `ipaddress`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `living_assistant.security.security_policy`
  - `living_assistant.security.security_utils`
  - `os`
  - `pathlib`
  - `socket`
  - `threading`
  - `time`
  - `typing`
  - `urllib.parse`
  - `uuid`

## `src/living_assistant/system/platform_hardening.py`

- language: `py`
- size: 12688 bytes
- hash: `c99056de9298`
- symbols:
  - `class` `PlatformStatus` — line 17
  - `method` `PlatformStatus.to_dict` — line 30
  - `function` `is_elevated` — line 34
  - `function` `_windows_registry_dword` — line 46
  - `function` `windows_developer_mode` — line 58
  - `function` `windows_long_paths_enabled` — line 66
  - `function` `is_link_like` — line 75
  - `function` `link_target_description` — line 94
  - `function` `iter_tree_without_link_traversal` — line 102
  - `function` `_create_windows_junction` — line 125
  - `function` `create_portable_link` — line 168
  - `function` `probe_link_capability` — line 233
  - `function` `_probe_hardlink` — line 248
  - `function` `detect_user_service_backend` — line 260
  - `function` `platform_status` — line 271
  - `class` `SleepResumeMonitor` — line 288
  - `method` `SleepResumeMonitor.__init__` — line 295
  - `method` `SleepResumeMonitor.observe` — line 300
  - `function` `service_status` — line 317
- imports:
  - `__future__`
  - `ctypes`
  - `dataclasses`
  - `json`
  - `os`
  - `pathlib`
  - `platform`
  - `shutil`
  - `stat`
  - `subprocess`
  - `tempfile`
  - `time`

## `src/living_assistant/system/project_auditor.py`

- language: `py`
- size: 11463 bytes
- hash: `b90988024071`
- symbols:
  - `function` `_decorated` — line 21
  - `function` `_call_name` — line 25
  - `class` `ProjectAuditor` — line 34
  - `method` `ProjectAuditor.__init__` — line 37
  - `method` `ProjectAuditor._files` — line 42
  - `method` `ProjectAuditor._dependency_audit` — line 62
  - `method` `ProjectAuditor._python_scan` — line 115
  - `method` `ProjectAuditor.audit` — line 196
- imports:
  - `__future__`
  - `ast`
  - `collections`
  - `json`
  - `living_assistant.core.workspace`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `re`
  - `tomllib`

## `src/living_assistant/system/release_manager.py`

- language: `py`
- size: 28218 bytes
- hash: `d440b3d06690`
- symbols:
  - `function` `utc_now` — line 23
  - `function` `sha256_file` — line 27
  - `function` `default_runtime_root` — line 35
  - `function` `default_data_root` — line 50
  - `function` `_atomic_json` — line 66
  - `function` `_safe_version` — line 81
  - `function` `_venv_python` — line 89
  - `function` `_venv_organism` — line 93
  - `function` `_copy_sqlite_consistently` — line 97
  - `function` `_snapshot_data_tree` — line 107
  - `function` `_restore_data_tree` — line 155
  - `function` `ensure_data_schema` — line 178
  - `function` `read_data_schema` — line 199
  - `function` `_service_action` — line 206
  - `function` `restart_user_service_if_installed` — line 253
  - `function` `remove_user_service` — line 257
  - `class` `InstallLayout` — line 262
  - `method` `InstallLayout.versions` — line 267
  - `method` `InstallLayout.bin` — line 269
  - `method` `InstallLayout.backups` — line 271
  - `method` `InstallLayout.state_file` — line 273
  - `class` `ReleaseManager` — line 276
  - `method` `ReleaseManager.__init__` — line 277
  - `method` `ReleaseManager._empty_state` — line 287
  - `method` `ReleaseManager.state` — line 290
  - `method` `ReleaseManager._write_state` — line 301
  - `method` `ReleaseManager._version_dir` — line 305
  - `method` `ReleaseManager._write_shims` — line 308
  - `method` `ReleaseManager.create_backup` — line 336
  - `method` `ReleaseManager._inspect_wheel_version` — line 343
  - `method` `ReleaseManager.install_wheel` — line 357
  - `method` `ReleaseManager.rollback` — line 420
  - `method` `ReleaseManager.remove_version` — line 438
  - `method` `ReleaseManager.uninstall_runtime` — line 450
  - `method` `ReleaseManager.verify` — line 466
  - `method` `ReleaseManager.status` — line 493
  - `function` `main` — line 507
- imports:
  - `__future__`
  - `dataclasses`
  - `datetime`
  - `hashlib`
  - `json`
  - `os`
  - `pathlib`
  - `platform`
  - `shlex`
  - `shutil`
  - `sqlite3`
  - `subprocess`
  - `sys`
  - `tempfile`
  - `venv`
  - `zipfile`

## `src/living_assistant/system/resource_manager.py`

- language: `py`
- size: 19230 bytes
- hash: `b38b9d94b3bb`
- symbols:
  - `class` `GPUVendorInterface` — line 11
  - `method` `GPUVendorInterface.query_runtime` — line 14
  - `class` `NvidiaSmiBackend` — line 19
  - `method` `NvidiaSmiBackend.__init__` — line 22
  - `method` `NvidiaSmiBackend.query_runtime` — line 25
  - `class` `AppleMlxBackend` — line 47
  - `method` `AppleMlxBackend.__init__` — line 50
  - `method` `AppleMlxBackend.query_runtime` — line 53
  - `class` `FallbackGPUBackend` — line 62
  - `method` `FallbackGPUBackend.__init__` — line 65
  - `method` `FallbackGPUBackend.query_runtime` — line 68
  - `class` `ModelRuntimePolicy` — line 73
  - `method` `ModelRuntimePolicy.to_dict` — line 85
  - `class` `ResourceManager` — line 89
  - `method` `ResourceManager.__init__` — line 90
  - `method` `ResourceManager._init_gpu_backend` — line 98
  - `method` `ResourceManager._nvidia_runtime` — line 105
  - `method` `ResourceManager._cpu_temperature_c` — line 108
  - `method` `ResourceManager.process_resource_snapshot` — line 125
  - `method` `ResourceManager.system_load_snapshot` — line 149
  - `method` `ResourceManager.set_interactive_mode` — line 170
  - `method` `ResourceManager.is_interactive_active` — line 177
  - `method` `ResourceManager.should_throttle_background_tasks` — line 181
  - `method` `ResourceManager.snapshot` — line 209
  - `method` `ResourceManager.thermal_pressure` — line 227
  - `method` `ResourceManager._select_model_policy` — line 242
  - `method` `ResourceManager.can_start_model` — line 336
  - `method` `ResourceManager.can_admit_model` — line 367
  - `method` `ResourceManager.model_runtime_status` — line 403
- imports:
  - `__future__`
  - `dataclasses`
  - `living_assistant.system.hardware`
  - `psutil`
  - `shutil`
  - `subprocess`

## `src/living_assistant/system/routines.py`

- language: `py`
- size: 5731 bytes
- hash: `fe47e14385de`
- symbols:
  - `function` `_parse_hhmm` — line 10
  - `class` `RoutineRegistry` — line 18
  - `method` `RoutineRegistry.__init__` — line 20
  - `method` `RoutineRegistry._load` — line 23
  - `method` `RoutineRegistry._save` — line 26
  - `method` `RoutineRegistry.add` — line 28
  - `method` `RoutineRegistry.list` — line 42
  - `method` `RoutineRegistry.get` — line 43
  - `method` `RoutineRegistry.remove` — line 45
  - `method` `RoutineRegistry.set_enabled` — line 47
  - `method` `RoutineRegistry._mark_run` — line 51
  - `method` `RoutineRegistry._clock_due` — line 56
  - `method` `RoutineRegistry.process` — line 67
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `pathlib`
  - `time`

## `src/living_assistant/system/scheduler.py`

- language: `py`
- size: 23619 bytes
- hash: `c7d768f958e5`
- symbols:
  - `class` `ScheduledTaskStore` — line 19
  - `method` `ScheduledTaskStore.__init__` — line 22
  - `method` `ScheduledTaskStore._init_db` — line 28
  - `method` `ScheduledTaskStore.save_task` — line 53
  - `method` `ScheduledTaskStore.get_task` — line 94
  - `method` `ScheduledTaskStore.list_tasks` — line 102
  - `method` `ScheduledTaskStore.delete_task` — line 117
  - `method` `ScheduledTaskStore.mark_executed` — line 124
  - `method` `ScheduledTaskStore.mark_missed` — line 137
  - `method` `ScheduledTaskStore.get_overdue_tasks` — line 150
  - `method` `ScheduledTaskStore._format_row` — line 163
  - `class` `LivingScheduler` — line 176
  - `method` `LivingScheduler.__init__` — line 182
  - `method` `LivingScheduler._init_scheduler` — line 197
  - `method` `LivingScheduler._register_default_handlers` — line 207
  - `method` `LivingScheduler.register_action_handler` — line 211
  - `method` `LivingScheduler.start` — line 217
  - `method` `LivingScheduler.stop` — line 227
  - `method` `LivingScheduler.is_running` — line 237
  - `method` `LivingScheduler._handle_notify_action` — line 240
  - `method` `LivingScheduler._handle_todo_action` — line 251
  - `method` `LivingScheduler._execute_task` — line 257
  - `method` `LivingScheduler.schedule_reminder` — line 287
  - `method` `LivingScheduler.schedule_cron` — line 330
  - `method` `LivingScheduler.schedule_interval` — line 379
  - `method` `LivingScheduler.cancel_task` — line 421
  - `method` `LivingScheduler.list_tasks` — line 430
  - `method` `LivingScheduler.recover_missed_tasks` — line 433
  - `method` `LivingScheduler.schedule_codebase_indexing` — line 456
  - `method` `LivingScheduler.schedule_briefings` — line 488
  - `method` `LivingScheduler._load_active_jobs_from_store` — line 534
  - `method` `LivingScheduler.stats` — line 576
  - `function` `get_scheduler` — line 590
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.security.security_utils`
  - `logging`
  - `pathlib`
  - `sqlite3`
  - `threading`
  - `time`
  - `typing`

## `src/living_assistant/system/watchdog_service.py`

- language: `py`
- size: 15200 bytes
- hash: `27d05ce0397c`
- symbols:
  - `class` `DebouncedEventHandler` — line 24
  - `method` `DebouncedEventHandler.__init__` — line 32
  - `method` `DebouncedEventHandler._should_ignore` — line 51
  - `method` `DebouncedEventHandler._record_event` — line 67
  - `method` `DebouncedEventHandler.on_created` — line 93
  - `method` `DebouncedEventHandler.on_modified` — line 97
  - `method` `DebouncedEventHandler.on_deleted` — line 101
  - `method` `DebouncedEventHandler.on_moved` — line 105
  - `method` `DebouncedEventHandler.collect_ready_events` — line 113
  - `method` `DebouncedEventHandler.clear` — line 160
  - `method` `DebouncedEventHandler.pending_count` — line 167
  - `class` `WatchdogObserverManager` — line 172
  - `method` `WatchdogObserverManager.__init__` — line 178
  - `method` `WatchdogObserverManager._check_watchdog_available` — line 188
  - `method` `WatchdogObserverManager.available` — line 199
  - `method` `WatchdogObserverManager.running` — line 203
  - `method` `WatchdogObserverManager.start` — line 207
  - `method` `WatchdogObserverManager.stop` — line 226
  - `method` `WatchdogObserverManager.add_watch` — line 241
  - `method` `WatchdogObserverManager.remove_watch` — line 295
  - `method` `WatchdogObserverManager.add_listener` — line 309
  - `method` `WatchdogObserverManager.remove_listener` — line 314
  - `method` `WatchdogObserverManager.poll` — line 321
  - `method` `WatchdogObserverManager.rebaseline` — line 338
  - `method` `WatchdogObserverManager.stats` — line 345
  - `function` `get_watchdog_manager` — line 367
- imports:
  - `__future__`
  - `logging`
  - `pathlib`
  - `threading`
  - `time`
  - `typing`

## `src/living_assistant/system/watchers.py`

- language: `py`
- size: 7719 bytes
- hash: `09bfb6f222bf`
- symbols:
  - `class` `WatchRegistry` — line 8
  - `method` `WatchRegistry.__init__` — line 9
  - `method` `WatchRegistry._load` — line 24
  - `method` `WatchRegistry._save` — line 30
  - `method` `WatchRegistry.add` — line 33
  - `method` `WatchRegistry.remove` — line 59
  - `method` `WatchRegistry.list` — line 69
  - `method` `WatchRegistry.stop` — line 72
  - `method` `WatchRegistry.close` — line 76
  - `method` `WatchRegistry._scan` — line 80
  - `method` `WatchRegistry.rebaseline` — line 102
  - `method` `WatchRegistry.poll` — line 123
- imports:
  - `__future__`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `living_assistant.system.platform_hardening`
  - `pathlib`
  - `time`

## `src/living_assistant/system/workspace_snapshots.py`

- language: `py`
- size: 15080 bytes
- hash: `00bb4573faf9`
- symbols:
  - `class` `WorkspaceSnapshotManager` — line 41
  - `method` `WorkspaceSnapshotManager.__init__` — line 50
  - `method` `WorkspaceSnapshotManager.project_root_for` — line 82
  - `method` `WorkspaceSnapshotManager._safe_symlink` — line 96
  - `method` `WorkspaceSnapshotManager._iter_entries` — line 110
  - `method` `WorkspaceSnapshotManager.create_for_path` — line 121
  - `method` `WorkspaceSnapshotManager.create` — line 124
  - `method` `WorkspaceSnapshotManager._prune` — line 206
  - `method` `WorkspaceSnapshotManager.list` — line 219
  - `method` `WorkspaceSnapshotManager._lookup` — line 240
  - `method` `WorkspaceSnapshotManager._validate_members` — line 250
  - `method` `WorkspaceSnapshotManager._clear_managed_source` — line 264
  - `method` `WorkspaceSnapshotManager.restore` — line 289
- imports:
  - `__future__`
  - `datetime`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.core.workspace`
  - `living_assistant.security.security_utils`
  - `os`
  - `pathlib`
  - `shutil`
  - `tarfile`
  - `tempfile`
  - `uuid`

## `src/living_assistant/task_graph.py`

- language: `py`
- size: 257 bytes
- hash: `6480805e1f16`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/tools/__init__.py`

- language: `py`
- size: 52 bytes
- hash: `025cdef7005a`

## `src/living_assistant/tools/agencyagentstools.py`

- language: `py`
- size: 3076 bytes
- hash: `df0cd0496011`
- symbols:
  - `function` `build_agency_agents_tools` — line 9
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.agency_agents`
  - `typing`

## `src/living_assistant/tools/agentmemorytools.py`

- language: `py`
- size: 5926 bytes
- hash: `a3f4a78645eb`
- symbols:
  - `function` `build_agentmemory_tools` — line 7
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.agentmemory`

## `src/living_assistant/tools/awesome_agent_tools_tools.py`

- language: `py`
- size: 1284 bytes
- hash: `c436567d31c4`
- symbols:
  - `function` `build_awesome_agent_tools` — line 8
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.awesome_agent_tools`
  - `typing`

## `src/living_assistant/tools/awesome_harnesstools.py`

- language: `py`
- size: 825 bytes
- hash: `492b286d0438`
- symbols:
  - `function` `build_awesome_harness_tools` — line 8
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.awesome_harness`
  - `typing`

## `src/living_assistant/tools/base.py`

- language: `py`
- size: 483 bytes
- hash: `8293d80dc503`
- symbols:
  - `class` `Tool` — line 6
  - `method` `Tool.ollama_schema` — line 12
- imports:
  - `__future__`
  - `dataclasses`
  - `typing`

## `src/living_assistant/tools/briefingtools.py`

- language: `py`
- size: 604 bytes
- hash: `6ed5e4891053`
- symbols:
  - `function` `build_briefing_tools` — line 5
- imports:
  - `__future__`
  - `base`

## `src/living_assistant/tools/browsertools.py`

- language: `py`
- size: 3264 bytes
- hash: `6dd3ddd276dd`
- symbols:
  - `function` `build_browser_tools` — line 5
- imports:
  - `__future__`
  - `base`
  - `living_assistant.desktop.browser`

## `src/living_assistant/tools/calendartools.py`

- language: `py`
- size: 1777 bytes
- hash: `d155e9b13d0d`
- symbols:
  - `function` `build_calendar_tools` — line 5
- imports:
  - `__future__`
  - `base`

## `src/living_assistant/tools/codebasememorytools.py`

- language: `py`
- size: 5318 bytes
- hash: `39225f35cc98`
- symbols:
  - `function` `build_codebase_memory_tools` — line 7
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.codebase_memory`

## `src/living_assistant/tools/connectortools.py`

- language: `py`
- size: 1122 bytes
- hash: `41759d9a436a`
- symbols:
  - `function` `build_connector_tools` — line 6
- imports:
  - `__future__`
  - `base`
  - `json`

## `src/living_assistant/tools/database.py`

- language: `py`
- size: 19206 bytes
- hash: `fc09e32ffe98`
- symbols:
  - `function` `_dsn` — line 10
  - `function` `_sqlite_readonly_connection` — line 18
  - `function` `_sql_query` — line 31
  - `function` `_sql_tokens` — line 79
  - `function` `_identifier_value` — line 89
  - `function` `_is_identifier_token` — line 99
  - `function` `_cte_names` — line 108
  - `function` `_referenced_sql_tables` — line 147
  - `function` `_database_alias_policy` — line 215
  - `function` `_allowed_table_names` — line 222
  - `function` `_sensitive_column_names` — line 229
  - `function` `_select_expressions` — line 244
  - `function` `_expression_alias` — line 286
  - `function` `_expression_identifiers` — line 310
  - `function` `_redact_sql_result` — line 325
  - `function` `_redact_mongo_document` — line 378
  - `function` `_contains_forbidden_mongo_operator` — line 394
  - `function` `_mongo_find` — line 406
  - `function` `build_database_tools` — line 422
- imports:
  - `__future__`
  - `base`
  - `living_assistant.core.approval`
  - `living_assistant.security.security_policy`
  - `living_assistant.security.security_utils`
  - `os`
  - `re`
  - `sqlite3`
  - `urllib.parse`

## `src/living_assistant/tools/desktop.py`

- language: `py`
- size: 6186 bytes
- hash: `c7a27d9c1cfc`
- symbols:
  - `function` `_clipboard_read_impl` — line 9
  - `function` `_clipboard_write_impl` — line 17
  - `function` `_screenshot_impl` — line 25
  - `function` `build_desktop_tools` — line 39
- imports:
  - `__future__`
  - `base`
  - `living_assistant.core.approval`
  - `living_assistant.core.workspace`
  - `pathlib`
  - `webbrowser`

## `src/living_assistant/tools/diagramtools.py`

- language: `py`
- size: 7455 bytes
- hash: `471aa476687e`
- symbols:
  - `function` `build_diagram_tools` — line 9
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.diagram_design`
  - `typing`

## `src/living_assistant/tools/edge0tools.py`

- language: `py`
- size: 3068 bytes
- hash: `b959d60e1e25`
- symbols:
  - `function` `build_edge0_tools` — line 10
- imports:
  - `__future__`
  - `base`
  - `json`
  - `living_assistant.integrations.edge0`
  - `typing`

## `src/living_assistant/tools/experiencetools.py`

- language: `py`
- size: 3511 bytes
- hash: `c2780ddceaf2`
- symbols:
  - `function` `build_experience_tools` — line 7
- imports:
  - `__future__`
  - `base`
  - `living_assistant.learning.experience`
  - `living_assistant.learning.knowledge_gap_detection`

## `src/living_assistant/tools/filesystem.py`

- language: `py`
- size: 7758 bytes
- hash: `55d5ef10bdff`
- symbols:
  - `function` `_preview` — line 15
  - `function` `_approval_for_sensitive` — line 23
  - `function` `build_filesystem_tools` — line 38
- imports:
  - `__future__`
  - `base`
  - `difflib`
  - `living_assistant.core.approval`
  - `living_assistant.core.workspace`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `re`
  - `typing`

## `src/living_assistant/tools/gittools.py`

- language: `py`
- size: 6851 bytes
- hash: `2dbed6b53159`
- symbols:
  - `function` `_git` — line 10
  - `function` `_is_repo` — line 15
  - `function` `_workspace_repo_cwd` — line 23
  - `function` `build_git_tools` — line 54
- imports:
  - `__future__`
  - `base`
  - `living_assistant.core.approval`
  - `living_assistant.core.workspace`
  - `living_assistant.security.security_utils`
  - `pathlib`
  - `subprocess`

## `src/living_assistant/tools/grafttools.py`

- language: `py`
- size: 6228 bytes
- hash: `3f6bd75e5077`
- symbols:
  - `function` `build_graft_tools` — line 9
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.graft`
  - `typing`

## `src/living_assistant/tools/grouptools.py`

- language: `py`
- size: 1305 bytes
- hash: `d9dbfa9d3efc`
- symbols:
  - `function` `build_group_tools` — line 6
- imports:
  - `__future__`
  - `base`
  - `living_assistant.system.groups`

## `src/living_assistant/tools/historytools.py`

- language: `py`
- size: 817 bytes
- hash: `788d5ece74b6`
- symbols:
  - `function` `build_run_history_tools` — line 7
- imports:
  - `__future__`
  - `base`
  - `living_assistant.learning.run_history`

## `src/living_assistant/tools/improvementtools.py`

- language: `py`
- size: 6639 bytes
- hash: `d852f7917c6f`
- symbols:
  - `function` `build_improvement_tools` — line 9
- imports:
  - `__future__`
  - `base`
  - `living_assistant.learning.canary`
  - `living_assistant.learning.evaluation`
  - `living_assistant.learning.improvements`
  - `living_assistant.learning.repair_loop`

## `src/living_assistant/tools/openmontagetools.py`

- language: `py`
- size: 3513 bytes
- hash: `b49c089a7478`
- symbols:
  - `function` `build_openmontage_tools` — line 10
- imports:
  - `__future__`
  - `base`
  - `json`
  - `living_assistant.integrations.openmontage`
  - `typing`

## `src/living_assistant/tools/peertools.py`

- language: `py`
- size: 1121 bytes
- hash: `652c7864184d`
- symbols:
  - `function` `build_peer_tools` — line 6
- imports:
  - `__future__`
  - `base`

## `src/living_assistant/tools/personal.py`

- language: `py`
- size: 3145 bytes
- hash: `892b69cade16`
- symbols:
  - `function` `build_personal_tools` — line 8
- imports:
  - `__future__`
  - `base`
  - `living_assistant.core.memory`
  - `living_assistant.system.notifications`
  - `platform`
  - `psutil`

## `src/living_assistant/tools/personalstate.py`

- language: `py`
- size: 854 bytes
- hash: `82c7fbade1c3`
- symbols:
  - `function` `build_personal_state_tools` — line 5
- imports:
  - `__future__`
  - `base`

## `src/living_assistant/tools/planning.py`

- language: `py`
- size: 3518 bytes
- hash: `97d2954a2067`
- symbols:
  - `function` `build_planning_tools` — line 6
- imports:
  - `base`
  - `living_assistant.agents.task_graph`
  - `pathlib`
  - `typing`

## `src/living_assistant/tools/projects.py`

- language: `py`
- size: 12805 bytes
- hash: `15fffd10f1e3`
- symbols:
  - `function` `detect_project` — line 20
  - `class` `ProjectRegistry` — line 65
  - `method` `ProjectRegistry.__init__` — line 66
  - `method` `ProjectRegistry._load_raw` — line 72
  - `method` `ProjectRegistry._save` — line 78
  - `method` `ProjectRegistry._migrate` — line 81
  - `method` `ProjectRegistry._clean_env` — line 104
  - `method` `ProjectRegistry.add` — line 117
  - `method` `ProjectRegistry.update` — line 140
  - `method` `ProjectRegistry.list` — line 158
  - `method` `ProjectRegistry.get` — line 161
  - `method` `ProjectRegistry.remove` — line 165
  - `function` `build_project_tools` — line 169
- imports:
  - `__future__`
  - `base`
  - `json`
  - `living_assistant.core.approval`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `living_assistant.core.workspace`
  - `living_assistant.security.security_utils`
  - `living_assistant.system.codebase_index`
  - `living_assistant.system.project_auditor`
  - `pathlib`
  - `re`
  - `time`
  - `typing`

## `src/living_assistant/tools/registry.py`

- language: `py`
- size: 1314 bytes
- hash: `9113f324e5a4`
- symbols:
  - `class` `ToolRegistry` — line 8
  - `method` `ToolRegistry.__init__` — line 11
  - `method` `ToolRegistry.register` — line 16
  - `method` `ToolRegistry.extend` — line 27
  - `method` `ToolRegistry.get` — line 31
  - `method` `ToolRegistry.all` — line 34
  - `method` `ToolRegistry.names` — line 37
  - `method` `ToolRegistry.__len__` — line 40
  - `method` `ToolRegistry.__iter__` — line 43
- imports:
  - `__future__`
  - `base`
  - `collections.abc`

## `src/living_assistant/tools/routinetools.py`

- language: `py`
- size: 2706 bytes
- hash: `d9fbf07c0665`
- symbols:
  - `function` `build_routine_tools` — line 5
- imports:
  - `__future__`
  - `base`

## `src/living_assistant/tools/schedulertools.py`

- language: `py`
- size: 4958 bytes
- hash: `27c1d84d0ecb`
- symbols:
  - `function` `build_scheduler_tools` — line 7
- imports:
  - `__future__`
  - `base`
  - `typing`

## `src/living_assistant/tools/scientific_skillstools.py`

- language: `py`
- size: 2346 bytes
- hash: `da76aa08c500`
- symbols:
  - `function` `build_scientific_skills_tools` — line 9
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.scientific_skills`
  - `typing`

## `src/living_assistant/tools/security.py`

- language: `py`
- size: 12241 bytes
- hash: `73167c501790`
- symbols:
  - `function` `_conn_name` — line 10
  - `function` `audit_local` — line 17
  - `function` `antivirus_status` — line 45
  - `function` `build_security_tools` — line 49
- imports:
  - `__future__`
  - `base`
  - `living_assistant.core.approval`
  - `living_assistant.core.workspace`
  - `living_assistant.security.security_guardian`
  - `living_assistant.security.security_sensors`
  - `platform`
  - `psutil`
  - `shutil`
  - `socket`
  - `subprocess`

## `src/living_assistant/tools/securityskills_tools.py`

- language: `py`
- size: 4387 bytes
- hash: `f3cf43e2c3c0`
- symbols:
  - `function` `build_security_skills_tools` — line 9
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.cybersecurity_skills`
  - `typing`

## `src/living_assistant/tools/sessiontools.py`

- language: `py`
- size: 792 bytes
- hash: `ff486ff43f1c`
- symbols:
  - `function` `build_session_tools` — line 5
- imports:
  - `__future__`
  - `base`

## `src/living_assistant/tools/shell.py`

- language: `py`
- size: 18816 bytes
- hash: `530983a68080`
- symbols:
  - `class` `ProcessRegistry` — line 18
  - `method` `ProcessRegistry.__init__` — line 19
  - `method` `ProcessRegistry._load` — line 25
  - `method` `ProcessRegistry._save` — line 32
  - `method` `ProcessRegistry._process_matches` — line 37
  - `method` `ProcessRegistry._spawn` — line 48
  - `method` `ProcessRegistry.start` — line 64
  - `method` `ProcessRegistry.list` — line 100
  - `method` `ProcessRegistry.get` — line 110
  - `method` `ProcessRegistry.stop` — line 115
  - `method` `ProcessRegistry.restart` — line 142
  - `method` `ProcessRegistry.tail` — line 171
  - `function` `build_shell_tools` — line 183
- imports:
  - `__future__`
  - `base`
  - `json`
  - `living_assistant.core.approval`
  - `living_assistant.core.config`
  - `living_assistant.core.storage_utils`
  - `living_assistant.core.workspace`
  - `living_assistant.security.safe_commands`
  - `living_assistant.security.security_policy`
  - `living_assistant.security.security_utils`
  - `os`
  - `pathlib`
  - `platform`
  - `psutil`
  - `subprocess`
  - `tempfile`
  - `threading`
  - `time`
  - `typing`
  - `uuid`

## `src/living_assistant/tools/vikingtools.py`

- language: `py`
- size: 5133 bytes
- hash: `a353c2697a56`
- symbols:
  - `function` `build_viking_tools` — line 7
- imports:
  - `__future__`
  - `base`
  - `living_assistant.integrations.openviking`

## `src/living_assistant/tools/voicetools.py`

- language: `py`
- size: 1408 bytes
- hash: `7da64e76e79a`
- symbols:
  - `function` `build_voice_tools` — line 5
- imports:
  - `__future__`
  - `base`
  - `living_assistant.desktop.voice`

## `src/living_assistant/tools/webtools.py`

- language: `py`
- size: 35294 bytes
- hash: `32e3442c956b`
- symbols:
  - `class` `_NetworkGate` — line 37
  - `method` `_NetworkGate.__init__` — line 38
  - `function` `build_web_tools` — line 43
- imports:
  - `__future__`
  - `base`
  - `collections`
  - `datetime`
  - `hashlib`
  - `httpx`
  - `living_assistant.core.approval`
  - `living_assistant.core.config`
  - `living_assistant.core.workspace`
  - `living_assistant.desktop.browser`
  - `living_assistant.security.quarantine`
  - `living_assistant.security.security_policy`
  - `living_assistant.security.security_utils`
  - `os`
  - `pathlib`
  - `sqlite3`
  - `threading`
  - `time`
  - `typing`
  - `urllib.parse`

## `src/living_assistant/tray.py`

- language: `py`
- size: 247 bytes
- hash: `62e3a9ae3102`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/verifier.py`

- language: `py`
- size: 257 bytes
- hash: `dbb600a338ff`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/voice.py`

- language: `py`
- size: 249 bytes
- hash: `4ceba4c87ce4`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/watchers.py`

- language: `py`
- size: 253 bytes
- hash: `e4e92f168d95`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/webui/index.html`

- language: `html`
- size: 953 bytes
- hash: `268835c3d3c3`

## `src/living_assistant/webui/package-lock.json`

- language: `json`
- size: 69504 bytes
- hash: `f873cda18c0f`

## `src/living_assistant/webui/package.json`

- language: `json`
- size: 685 bytes
- hash: `1ae8be914643`

## `src/living_assistant/webui/src/chart_loader.js`

- language: `js`
- size: 2415 bytes
- hash: `a89474b14a1b`
- symbols:
  - `function` `installedPlotly` — line 6
  - `function` `loadScript` — line 15
  - `function` `loadPlotly` — line 53

## `src/living_assistant/webui/src/main.js`

- language: `js`
- size: 59390 bytes
- hash: `0ee69a2bfd89`
- symbols:
  - `class` `App` — line 106
  - `class` `ResourceChart` — line 746
  - `function` `cx` — line 13
  - `function` `safeText` — line 15
  - `function` `fmtBytes` — line 16
  - `function` `hashPage` — line 24
  - `function` `makeSessionId` — line 28
  - `function` `tokenizeInline` — line 34
  - `function` `renderPrismToken` — line 55
  - `function` `CodeBlock` — line 64
  - `function` `Markdown` — line 71
  - `function` `UsageTable` — line 815
  - `function` `ModelTable` — line 834
  - `function` `ApprovalList` — line 854
  - `function` `ActivityList` — line 868
  - `function` `ItemList` — line 880
  - `function` `statusBadge` — line 395
  - `function` `statusBadge` — line 544
  - `function` `trace` — line 771
- imports:
  - `./chart_loader.js`
  - `./resource_chart_data.js`

## `src/living_assistant/webui/src/resource_chart_data.js`

- language: `js`
- size: 2097 bytes
- hash: `96bfd2157da4`
- symbols:
  - `function` `finiteNumber` — line 2
  - `function` `percentMetric` — line 7
  - `function` `makeResourceSample` — line 13
  - `function` `resourceSeries` — line 34
  - `function` `roundedPercent` — line 42
  - `function` `resourceSampleLabel` — line 47

## `src/living_assistant/webui/src/styles.css`

- language: `css`
- size: 262 bytes
- hash: `450d4594da35`

## `src/living_assistant/webui/vite-dist/assets/index-C8GrKIUi.js`

- language: `js`
- size: 40425 bytes
- hash: `4e63b83964c1`

## `src/living_assistant/webui/vite-dist/index.html`

- language: `html`
- size: 1148 bytes
- hash: `fc8620b2d79f`

## `src/living_assistant/webui/vite.config.js`

- language: `js`
- size: 264 bytes
- hash: `249ecdfc90fb`
- imports:
  - `@vitejs/plugin-react`
  - `vite`

## `src/living_assistant/workspace.py`

- language: `py`
- size: 251 bytes
- hash: `21b654de5586`
- imports:
  - `importlib`
  - `sys`

