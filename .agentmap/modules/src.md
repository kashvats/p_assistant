# Module: src

> Generated navigation map. Source code is authoritative.

## `src/living_assistant/__init__.py`

- language: `py`
- size: 24 bytes
- hash: `7d0e9bad8349`

## `src/living_assistant/agents/__init__.py`

- language: `py`
- size: 263 bytes
- hash: `ebf79461f59b`
- imports:
  - `agents`

## `src/living_assistant/agents/agents.py`

- language: `py`
- size: 5339 bytes
- hash: `a6e12fbe119e`
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
- size: 6851 bytes
- hash: `b0737af6c5bb`
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

## `src/living_assistant/agents/orchestrator.py`

- language: `py`
- size: 20761 bytes
- hash: `39259a15bed5`
- symbols:
  - `class` `Orchestrator` — line 13
  - `method` `Orchestrator.__init__` — line 14
  - `method` `Orchestrator._delegate` — line 43
  - `method` `Orchestrator._model_lease` — line 63
  - `method` `Orchestrator._publish` — line 78
  - `method` `Orchestrator._history_start` — line 86
  - `method` `Orchestrator._history_tool` — line 95
  - `method` `Orchestrator._history_finish` — line 103
  - `method` `Orchestrator._record_model_usage` — line 111
  - `method` `Orchestrator._skill_context` — line 122
  - `method` `Orchestrator._session_context` — line 129
  - `method` `Orchestrator._project_hint` — line 156
  - `method` `Orchestrator._experience_context` — line 168
  - `method` `Orchestrator._finish` — line 173
  - `method` `Orchestrator._prepare` — line 178
  - `method` `Orchestrator._execute_tool` — line 197
  - `method` `Orchestrator.run` — line 219
  - `method` `Orchestrator.run_stream` — line 284
- imports:
  - `__future__`
  - `contextlib`
  - `json`
  - `living_assistant.agents.agents`
  - `living_assistant.agents.prompts`
  - `living_assistant.core.model_provider`
  - `living_assistant.core.skills`
  - `living_assistant.security.security_utils`
  - `living_assistant.system.resource_manager`
  - `living_assistant.tools.base`
  - `time`

## `src/living_assistant/agents/orchestrator_teams.py`

- language: `py`
- size: 4055 bytes
- hash: `96a85b92a20f`
- symbols:
  - `function` `dispatch_to_teams` — line 8
- imports:
  - `living_assistant.agents.aggregator`
  - `living_assistant.core.models`
  - `logging`

## `src/living_assistant/agents/prompts.py`

- language: `py`
- size: 4755 bytes
- hash: `3c00932e2743`

## `src/living_assistant/agents/task_graph.py`

- language: `py`
- size: 3723 bytes
- hash: `e064d2da4bcd`
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
- size: 252 bytes
- hash: `820acd5c7e7c`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/api.py`

- language: `py`
- size: 6098 bytes
- hash: `0eca893142a7`
- symbols:
  - `function` `_allowed_hostnames` — line 56
  - `function` `_host_only` — line 65
  - `function` `_origin_is_local_or_same` — line 72
  - `async-function` `local_api_boundary` — line 83
  - `function` `_rt` — line 104
  - `function` `_auth` — line 108
  - `function` `health` — line 122
  - `function` `status` — line 127
  - `function` `platform_status_endpoint` — line 142
  - `function` `platform_service_status_endpoint` — line 150
- routes:
  - `GET /health` → `health` — line 122
  - `GET /status` → `status` — line 127
  - `GET /platform/status` → `platform_status_endpoint` — line 142
  - `GET /platform/service-status` → `platform_service_status_endpoint` — line 150
- imports:
  - `__future__`
  - `fastapi`
  - `fastapi.responses`
  - `hmac`
  - `living_assistant.api_routes.assistant`
  - `living_assistant.api_routes.desktop`
  - `living_assistant.api_routes.improvements`
  - `living_assistant.api_routes.integrations`
  - `living_assistant.api_routes.models`
  - `living_assistant.api_routes.peers`
  - `living_assistant.api_routes.personal`
  - `living_assistant.api_routes.schemas`
  - `living_assistant.api_routes.security`
  - `living_assistant.api_routes.ui`
  - `living_assistant.api_routes.workspace`
  - `living_assistant.core.runtime`
  - `living_assistant.security.api_auth`
  - `living_assistant.system.platform_hardening`
  - `os`
  - `urllib.parse`

## `src/living_assistant/api_auth.py`

- language: `py`
- size: 252 bytes
- hash: `90d1e094c748`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/api_routes/__init__.py`

- language: `py`
- size: 57 bytes
- hash: `8c9bd15c60ec`

## `src/living_assistant/api_routes/assistant.py`

- language: `py`
- size: 2778 bytes
- hash: `a2b439dcff36`
- symbols:
  - `function` `_sse` — line 14
  - `function` `ask` — line 30
  - `function` `activity` — line 49
  - `function` `activity_stream` — line 59
  - `function` `chat_stream` — line 88
- routes:
  - `POST /ask` → `ask` — line 30
  - `GET /activity` → `activity` — line 49
  - `GET /activity/stream` → `activity_stream` — line 59
  - `POST /chat/stream` → `chat_stream` — line 88
- imports:
  - `__future__`
  - `fastapi`
  - `fastapi.responses`
  - `json`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`

## `src/living_assistant/api_routes/dependencies.py`

- language: `py`
- size: 543 bytes
- hash: `3cb72904a27a`
- symbols:
  - `function` `runtime` — line 6
  - `function` `authorize` — line 14
- imports:
  - `__future__`
  - `living_assistant.core.runtime`

## `src/living_assistant/api_routes/desktop.py`

- language: `py`
- size: 1078 bytes
- hash: `fa7568c5cc3b`
- symbols:
  - `function` `desktop_status` — line 12
  - `function` `desktop_monitors` — line 18
  - `function` `desktop_windows` — line 24
  - `function` `desktop_analyze_screen` — line 30
- routes:
  - `GET /desktop/status` → `desktop_status` — line 12
  - `GET /desktop/monitors` → `desktop_monitors` — line 18
  - `GET /desktop/windows` → `desktop_windows` — line 24
  - `POST /desktop/analyze-screen` → `desktop_analyze_screen` — line 30
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`

## `src/living_assistant/api_routes/improvements.py`

- language: `py`
- size: 8239 bytes
- hash: `2e308bd64176`
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
- size: 3097 bytes
- hash: `4f8d2c0cc74f`
- symbols:
  - `function` `voice_status` — line 18
  - `function` `voice_enabled` — line 29
  - `function` `browser_sessions` — line 44
  - `function` `browser_session_start` — line 50
  - `function` `browser_session_navigate` — line 64
  - `function` `browser_session_interact` — line 74
  - `function` `browser_session_close` — line 89
  - `function` `connectors` — line 98
  - `function` `connector_status` — line 104
  - `function` `connector_call` — line 113
- routes:
  - `GET /voice/status` → `voice_status` — line 18
  - `POST /voice/enabled` → `voice_enabled` — line 29
  - `GET /browser/sessions` → `browser_sessions` — line 44
  - `POST /browser/sessions` → `browser_session_start` — line 50
  - `POST /browser/sessions/{name}/navigate` → `browser_session_navigate` — line 64
  - `POST /browser/sessions/{name}/interact` → `browser_session_interact` — line 74
  - `DELETE /browser/sessions/{name}` → `browser_session_close` — line 89
  - `GET /connectors` → `connectors` — line 98
  - `GET /connectors/{name}/status` → `connector_status` — line 104
  - `POST /connectors/{name}/call` → `connector_call` — line 113
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`

## `src/living_assistant/api_routes/models.py`

- language: `py`
- size: 3040 bytes
- hash: `b3e5910c32b9`
- symbols:
  - `function` `model_status` — line 13
  - `function` `model_select` — line 24
  - `function` `model_preload` — line 47
  - `function` `model_unload` — line 56
  - `function` `model_local_catalog` — line 65
  - `function` `model_pull` — line 71
  - `function` `model_delete` — line 80
  - `function` `model_usage` — line 88
- routes:
  - `GET /models/status` → `model_status` — line 13
  - `POST /models/select` → `model_select` — line 24
  - `POST /models/preload` → `model_preload` — line 47
  - `POST /models/unload` → `model_unload` — line 56
  - `GET /models/local` → `model_local_catalog` — line 65
  - `POST /models/pull` → `model_pull` — line 71
  - `POST /models/delete` → `model_delete` — line 80
  - `GET /models/usage` → `model_usage` — line 88
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`
  - `living_assistant.api_routes.schemas`
  - `living_assistant.core.model_provider`

## `src/living_assistant/api_routes/peers.py`

- language: `py`
- size: 884 bytes
- hash: `18d764665a5b`
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
- size: 4340 bytes
- hash: `35dc07d65ec1`
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
- size: 4061 bytes
- hash: `b497d793b45f`
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
  - `class` `DesktopAnalyzeRequest` — line 155
  - `class` `PeerDelegateRequest` — line 163
- imports:
  - `__future__`
  - `pydantic`

## `src/living_assistant/api_routes/security.py`

- language: `py`
- size: 13055 bytes
- hash: `905c5401ba11`
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

## `src/living_assistant/api_routes/ui.py`

- language: `py`
- size: 2527 bytes
- hash: `fe24ca5aef79`
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
- size: 1117 bytes
- hash: `57f28f14d7e4`
- symbols:
  - `function` `projects` — line 11
  - `function` `groups` — line 17
  - `function` `processes` — line 23
  - `function` `watches` — line 29
  - `function` `skills` — line 35
  - `function` `routines` — line 41
- routes:
  - `GET /projects` → `projects` — line 11
  - `GET /groups` → `groups` — line 17
  - `GET /processes` → `processes` — line 23
  - `GET /watches` → `watches` — line 29
  - `GET /skills` → `skills` — line 35
  - `GET /routines` → `routines` — line 41
- imports:
  - `__future__`
  - `fastapi`
  - `living_assistant.api_routes.dependencies`

## `src/living_assistant/approval.py`

- language: `py`
- size: 244 bytes
- hash: `758c1780d8cc`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/approval_ui.py`

- language: `py`
- size: 256 bytes
- hash: `7ebc4a35f39f`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/briefing.py`

- language: `py`
- size: 244 bytes
- hash: `eb4a2fe46f07`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/browser.py`

- language: `py`
- size: 248 bytes
- hash: `d2ef2c52857e`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/calendar_store.py`

- language: `py`
- size: 256 bytes
- hash: `c542c5d0cea7`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/canary.py`

- language: `py`
- size: 248 bytes
- hash: `83881b9cd559`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/cli/__init__.py`

- language: `py`
- size: 225 bytes
- hash: `ba1d8e73d2c5`
- imports:
  - `commands`

## `src/living_assistant/cli/commands.py`

- language: `py`
- size: 62679 bytes
- hash: `f34aa738324e`
- symbols:
  - `function` `onboard` — line 60
  - `function` `doctor` — line 122
  - `function` `platform_status_cmd` — line 158
  - `function` `platform_link_probe` — line 163
  - `function` `platform_service_status` — line 168
  - `function` `release_status` — line 174
  - `function` `release_verify` — line 178
  - `function` `release_backup` — line 183
  - `function` `release_rollback` — line 187
  - `function` `release_remove_version` — line 191
  - `function` `model_status` — line 195
  - `function` `model_preload` — line 201
  - `function` `model_unload` — line 207
  - `function` `model_sleep` — line 212
  - `function` `ask` — line 218
  - `function` `chat` — line 226
  - `function` `daemon` — line 242
  - `function` `tick` — line 249
  - `function` `serve` — line 256
  - `function` `tray` — line 263
  - `function` `project_add` — line 273
  - `function` `project_list` — line 288
  - `function` `project_detect` — line 295
  - `function` `project_audit` — line 300
  - `function` `project_snapshot` — line 307
  - `function` `project_snapshots` — line 313
  - `function` `project_snapshot_restore` — line 320
  - `function` `project_run` — line 335
  - `function` `project_test` — line 346
  - `function` `project_processes` — line 358
  - `function` `project_logs` — line 362
  - `function` `project_restart` — line 367
  - `function` `project_stop` — line 374
  - `function` `group_add` — line 377
  - `function` `group_list` — line 389
  - `function` `group_plan` — line 392
  - `function` `group_run` — line 395
  - `function` `group_stop` — line 399
  - `function` `approval_list` — line 402
  - `function` `approval_approve` — line 406
  - `function` `approval_deny` — line 409
  - `function` `approval_ui` — line 412
  - `function` `watch_add` — line 421
  - `function` `watch_list` — line 425
  - `function` `watch_remove` — line 428
  - `function` `skill_add` — line 431
  - `function` `skill_list` — line 436
  - `function` `skill_remove` — line 439
  - `function` `todo_add` — line 442
  - `function` `todo_list` — line 446
  - `function` `todo_done` — line 449
  - `function` `quarantine_list` — line 452
  - `function` `quarantine_release` — line 455
  - `function` `quarantine_inspect` — line 466
  - `function` `quarantine_scan` — line 472
  - `function` `git_status` — line 481
  - `function` `git_diff` — line 487
  - `function` `desktop_screenshot` — line 493
  - `function` `desktop_clipboard_read` — line 500
  - `function` `desktop_status` — line 507
  - `function` `desktop_monitors` — line 511
  - `function` `desktop_windows` — line 515
  - `function` `desktop_accessibility` — line 519
  - `function` `desktop_click` — line 523
  - `function` `desktop_type` — line 527
  - `function` `desktop_hotkey` — line 531
  - `function` `desktop_analyze_screen` — line 535
  - `function` `security_audit` — line 539
  - `function` `security_av_status` — line 542
  - `function` `security_posture` — line 545
  - `function` `security_findings` — line 549
  - `function` `security_resolve` — line 553
  - `function` `security_initialize` — line 557
  - `function` `security_startup_inventory` — line 564
  - `function` `security_startup_capture` — line 567
  - `function` `security_startup_check` — line 570
  - `function` `security_network_capture` — line 573
  - `function` `security_network_check` — line 576
  - `function` `security_process` — line 579
  - `function` `security_process_triage` — line 582
  - `function` `security_network_activity` — line 585
  - `function` `security_file_signature` — line 588
  - `function` `security_baseline_add` — line 591
  - `function` `security_baseline_list` — line 596
  - `function` `security_baseline_check` — line 599
  - `function` `security_baseline_refresh` — line 602
  - `function` `security_baseline_remove` — line 605
  - `function` `security_contain_process` — line 608
  - `function` `security_sensor_status` — line 612
  - `function` `security_events` — line 615
  - `function` `security_correlate` — line 618
  - `function` `security_dns` — line 621
  - `function` `security_tls_context` — line 624
  - `function` `security_yara` — line 627
  - `function` `security_reputation` — line 631
  - `function` `security_reputation_process` — line 634
  - `function` `security_binary_assess` — line 637
  - `function` `security_binary_trust` — line 640
  - `function` `security_binary_check` — line 643
  - `function` `security_usb_check` — line 646
  - `function` `security_usb_capture` — line 649
  - `function` `security_extensions_check` — line 652
  - `function` `security_extensions_capture` — line 655
  - `function` `security_backup_capture` — line 658
  - `function` `security_backup_list` — line 661
  - `function` `security_backup_check` — line 664
  - `function` `security_network_isolate` — line 667
  - `function` `security_network_restore` — line 670
  - `function` `browser_live` — line 675
  - `function` `browser_sessions` — line 708
  - `function` `browser_start` — line 712
  - `function` `browser_snapshot` — line 718
  - `function` `browser_navigate` — line 722
  - `function` `browser_click` — line 726
  - `function` `browser_fill` — line 730
  - `function` `browser_close` — line 734
  - `function` `voice_status` — line 738
  - `function` `voice_record` — line 743
  - `function` `voice_record_utterance` — line 748
  - `function` `voice_transcribe` — line 757
  - `function` `voice_wake` — line 765
  - `function` `voice_wake_model_download` — line 776
  - `function` `voice_ask` — line 784
  - `function` `voice_presence` — line 802
  - `function` `routine_list` — line 865
  - `function` `routine_add_event_notify` — line 869
  - `function` `routine_add_interval_notify` — line 874
  - `function` `routine_add_interval_todo` — line 879
  - `function` `routine_add_daily_notify` — line 884
  - `function` `routine_add_daily_todo` — line 889
  - `function` `routine_add_weekly_notify` — line 894
  - `function` `routine_add_prompt` — line 899
  - `function` `routine_enable` — line 906
  - `function` `routine_disable` — line 910
  - `function` `routine_remove` — line 914
  - `function` `improve_list` — line 918
  - `function` `improve_show` — line 922
  - `function` `improve_propose` — line 926
  - `function` `improve_apply` — line 933
  - `function` `improve_rollback` — line 937
  - `function` `improve_reject` — line 941
  - `function` `improve_suite_add` — line 945
  - `function` `improve_suite_list` — line 960
  - `function` `improve_suite_remove` — line 964
  - `function` `improve_evaluate` — line 968
  - `function` `improve_evaluations` — line 984
  - `function` `improve_report` — line 988
  - `function` `improve_sandbox_status` — line 993
  - `function` `improve_canary_run` — line 998
  - `function` `improve_canaries` — line 1008
  - `function` `improve_canary_report` — line 1012
  - `function` `improve_promote` — line 1016
  - `function` `improve_revert_promotion` — line 1020
  - `function` `improve_cleanup_evaluation` — line 1024
  - `function` `calendar_add` — line 1029
  - `function` `calendar_list` — line 1033
  - `function` `calendar_upcoming` — line 1037
  - `function` `calendar_cancel` — line 1041
  - `function` `calendar_export` — line 1045
  - `function` `personal_status` — line 1050
  - `function` `personal_quiet` — line 1054
  - `function` `personal_quiet_off` — line 1058
  - `function` `personal_focus` — line 1062
  - `function` `personal_focus_off` — line 1066
  - `function` `personal_flush_notifications` — line 1070
  - `function` `briefing_now` — line 1074
  - `function` `session_list` — line 1081
  - `function` `session_show` — line 1085
  - `function` `session_search` — line 1089
  - `function` `session_delete` — line 1093
  - `function` `integration_list` — line 1098
  - `function` `integration_providers` — line 1102
  - `function` `integration_add` — line 1107
  - `function` `integration_status` — line 1118
  - `function` `integration_call` — line 1122
  - `function` `integration_auth` — line 1131
  - `function` `integration_clear_credentials` — line 1155
  - `function` `integration_enable` — line 1163
  - `function` `integration_disable` — line 1167
  - `function` `integration_remove` — line 1171
  - `function` `experience_add` — line 1176
  - `function` `experience_list` — line 1192
  - `function` `experience_show` — line 1197
  - `function` `experience_search` — line 1201
  - `function` `experience_confirm` — line 1205
  - `function` `experience_verify` — line 1210
  - `function` `experience_reject` — line 1214
  - `function` `experience_supersede` — line 1218
  - `function` `experience_episodes` — line 1222
  - `function` `experience_patterns` — line 1226
  - `function` `experience_stats` — line 1230
  - `function` `experience_maintenance` — line 1234
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
- size: 2790 bytes
- hash: `9bdd99f2a277`
- imports:
  - `__future__`
  - `rich.console`
  - `typer`

## `src/living_assistant/config.py`

- language: `py`
- size: 240 bytes
- hash: `6bd82a905663`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/connector_credentials.py`

- language: `py`
- size: 282 bytes
- hash: `d7a2fc8efcd4`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/connector_oauth.py`

- language: `py`
- size: 270 bytes
- hash: `31fc1312340a`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/connectors/__init__.py`

- language: `py`
- size: 270 bytes
- hash: `0956d15cda6d`
- imports:
  - `connectors`
  - `mobile_bridge`

## `src/living_assistant/connectors/connector_credentials.py`

- language: `py`
- size: 3605 bytes
- hash: `df41dafeb76e`
- symbols:
  - `function` `_norm` — line 14
  - `class` `CredentialStore` — line 19
  - `method` `CredentialStore.prefix_for` — line 26
  - `method` `CredentialStore.env` — line 29
  - `method` `CredentialStore._keyring` — line 33
  - `method` `CredentialStore.load_bundle` — line 42
  - `method` `CredentialStore.save_bundle` — line 55
  - `method` `CredentialStore.delete_bundle` — line 64
  - `method` `CredentialStore.secret` — line 73
  - `method` `CredentialStore.status` — line 85
  - `method` `CredentialStore.safe_error` — line 101
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
- size: 10238 bytes
- hash: `260020d5f19c`
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
- size: 24393 bytes
- hash: `947e3d458ed8`
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
- size: 8861 bytes
- hash: `cab35c0fb026`
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
- size: 48 bytes
- hash: `db571169f5e3`

## `src/living_assistant/core/approval.py`

- language: `py`
- size: 7651 bytes
- hash: `11bd0cb5ccbd`
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
- size: 6724 bytes
- hash: `7b1cadadd68d`
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
- size: 4890 bytes
- hash: `5c4ce581daa8`
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
- size: 2812 bytes
- hash: `abb27eee963b`
- symbols:
  - `function` `_expand_env` — line 10
  - `function` `source_root` — line 23
  - `function` `data_dir` — line 32
  - `function` `user_config_path` — line 44
  - `function` `active_config_path` — line 48
  - `function` `project_root` — line 60
  - `function` `_default_config_text` — line 69
  - `function` `load_config` — line 76
- imports:
  - `__future__`
  - `importlib`
  - `os`
  - `pathlib`
  - `platformdirs`
  - `re`
  - `yaml`

## `src/living_assistant/core/event_bus.py`

- language: `py`
- size: 4639 bytes
- hash: `1a5d2a1fd749`
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
- size: 5789 bytes
- hash: `351ec168527d`
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
- size: 42878 bytes
- hash: `f13b3a22f60e`
- symbols:
  - `class` `ModelError` — line 15
  - `class` `OllamaProvider` — line 19
  - `method` `OllamaProvider.__post_init__` — line 25
  - `method` `OllamaProvider._client` — line 38
  - `method` `OllamaProvider._validate_model_name` — line 42
  - `method` `OllamaProvider.available_models` — line 61
  - `method` `OllamaProvider.model_inventory` — line 64
  - `method` `OllamaProvider.model_size_bytes` — line 79
  - `method` `OllamaProvider.running_models` — line 89
  - `method` `OllamaProvider.pull` — line 100
  - `method` `OllamaProvider.delete` — line 120
  - `method` `OllamaProvider.preload` — line 140
  - `method` `OllamaProvider.chat_stream` — line 154
  - `method` `OllamaProvider.chat` — line 183
  - `method` `OllamaProvider.unload` — line 201
  - `class` `AirLLMProvider` — line 209
  - `method` `AirLLMProvider.__init__` — line 225
  - `method` `AirLLMProvider.is_airllm_model` — line 254
  - `method` `AirLLMProvider.normalize_model` — line 258
  - `method` `AirLLMProvider.external_name` — line 267
  - `method` `AirLLMProvider._airllm_module` — line 270
  - `method` `AirLLMProvider._load_model` — line 278
  - `method` `AirLLMProvider._prompt` — line 315
  - `method` `AirLLMProvider._sequence_length` — line 348
  - `method` `AirLLMProvider.available_models` — line 360
  - `method` `AirLLMProvider.model_inventory` — line 364
  - `method` `AirLLMProvider.model_size_bytes` — line 375
  - `method` `AirLLMProvider.running_models` — line 383
  - `method` `AirLLMProvider.preload` — line 390
  - `method` `AirLLMProvider.chat` — line 395
  - `method` `AirLLMProvider.chat_stream` — line 457
  - `method` `AirLLMProvider.unload` — line 464
  - `class` `CompositeModelProvider` — line 478
  - `method` `CompositeModelProvider.__init__` — line 481
  - `method` `CompositeModelProvider._route` — line 489
  - `method` `CompositeModelProvider.available_models` — line 494
  - `method` `CompositeModelProvider.model_inventory` — line 504
  - `method` `CompositeModelProvider.model_size_bytes` — line 515
  - `method` `CompositeModelProvider.running_models` — line 519
  - `method` `CompositeModelProvider.preload` — line 529
  - `method` `CompositeModelProvider.chat_stream` — line 533
  - `method` `CompositeModelProvider.chat` — line 540
  - `method` `CompositeModelProvider.unload` — line 545
  - `class` `ModelManager` — line 550
  - `method` `ModelManager.__init__` — line 558
  - `method` `ModelManager._publish` — line 575
  - `method` `ModelManager._model_sem` — line 582
  - `method` `ModelManager._touch_locked` — line 590
  - `method` `ModelManager._evict_one_locked` — line 604
  - `method` `ModelManager._prepare_locked` — line 627
  - `method` `ModelManager.activate` — line 681
  - `method` `ModelManager.effective_keep_alive` — line 686
  - `method` `ModelManager._wait_for_thermal_slot` — line 691
  - `method` `ModelManager.lease` — line 717
  - `method` `ModelManager._ollama_provider` — line 749
  - `method` `ModelManager.local_model_catalog` — line 756
  - `method` `ModelManager.pull_local_model` — line 831
  - `method` `ModelManager.delete_local_model` — line 838
  - `method` `ModelManager.preload` — line 856
  - `method` `ModelManager.unload` — line 862
  - `method` `ModelManager.sleep` — line 875
  - `method` `ModelManager.sync_running_models` — line 890
  - `method` `ModelManager.status` — line 917
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
- size: 2283 bytes
- hash: `a0d0c6774c27`
- symbols:
  - `class` `ExecutivePlan` — line 4
  - `class` `ProposedMutation` — line 12
  - `class` `SpecialistResponse` — line 18
- imports:
  - `pydantic`
  - `typing`

## `src/living_assistant/core/personal_state.py`

- language: `py`
- size: 6108 bytes
- hash: `2773682d8575`
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
- size: 15800 bytes
- hash: `4f999738a1cb`
- symbols:
  - `class` `Runtime` — line 72
  - `method` `Runtime.dispatch` — line 112
  - `function` `get_runtime` — line 126
  - `function` `build_runtime` — line 133
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
  - `living_assistant.system.resource_manager`

## `src/living_assistant/core/sessions.py`

- language: `py`
- size: 7676 bytes
- hash: `e8c139942e96`
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
- size: 2850 bytes
- hash: `896cb9f727e6`
- symbols:
  - `class` `Skill` — line 10
  - `class` `SkillRegistry` — line 16
  - `method` `SkillRegistry.__init__` — line 18
  - `method` `SkillRegistry._load` — line 33
  - `method` `SkillRegistry._save` — line 39
  - `method` `SkillRegistry.add` — line 42
  - `method` `SkillRegistry.remove` — line 55
  - `method` `SkillRegistry.list` — line 58
  - `method` `SkillRegistry.match` — line 61
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

## `src/living_assistant/core/sqlite_utils.py`

- language: `py`
- size: 4935 bytes
- hash: `d27fa85202fa`
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
  - `method` `ThreadLocalSQLite.__getattr__` — line 126
- imports:
  - `__future__`
  - `pathlib`
  - `sqlite3`
  - `threading`

## `src/living_assistant/core/storage_utils.py`

- language: `py`
- size: 1356 bytes
- hash: `9b5903e5164c`
- symbols:
  - `function` `atomic_write_text` — line 9
  - `function` `atomic_write_json` — line 41
- imports:
  - `__future__`
  - `json`
  - `os`
  - `pathlib`
  - `tempfile`

## `src/living_assistant/core/workspace.py`

- language: `py`
- size: 2206 bytes
- hash: `3aae3d171878`
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
- size: 244 bytes
- hash: `91c37aeb2455`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/default_config.yaml`

- language: `yaml`
- size: 8783 bytes
- hash: `335b36614c11`

## `src/living_assistant/default_skills.json`

- language: `json`
- size: 1717 bytes
- hash: `923ebf485f83`

## `src/living_assistant/desktop/__init__.py`

- language: `py`
- size: 51 bytes
- hash: `fce320ce8e55`

## `src/living_assistant/desktop/approval_ui.py`

- language: `py`
- size: 2279 bytes
- hash: `59eb46f19399`
- symbols:
  - `function` `run_approval_ui` — line 4
- imports:
  - `__future__`

## `src/living_assistant/desktop/browser.py`

- language: `py`
- size: 27867 bytes
- hash: `f770b3901c57`
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
- size: 18027 bytes
- hash: `a4cfbd5a225c`
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
- size: 37647 bytes
- hash: `dbc17fba5ef7`
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
- size: 2012 bytes
- hash: `b39b543c487f`
- symbols:
  - `function` `run_tray` — line 5
- imports:
  - `__future__`
  - `threading`
  - `time`
  - `webbrowser`

## `src/living_assistant/desktop/voice.py`

- language: `py`
- size: 29139 bytes
- hash: `0367fdfca79b`
- symbols:
  - `class` `VoiceEngine` — line 18
  - `method` `VoiceEngine._cfg` — line 37
  - `method` `VoiceEngine.enabled` — line 40
  - `method` `VoiceEngine.hands_free_enabled` — line 46
  - `method` `VoiceEngine._module_available` — line 55
  - `method` `VoiceEngine.status` — line 61
  - `method` `VoiceEngine._ensure_microphone_approval` — line 81
  - `method` `VoiceEngine._import_audio` — line 92
  - `method` `VoiceEngine._write_wav` — line 101
  - `method` `VoiceEngine.record` — line 109
  - `method` `VoiceEngine.record_until_silence` — line 132
  - `method` `VoiceEngine._load_stt` — line 235
  - `method` `VoiceEngine.transcribe` — line 249
  - `method` `VoiceEngine._wake_model_paths` — line 280
  - `method` `VoiceEngine.download_wake_model` — line 314
  - `method` `VoiceEngine.clean_command_text` — line 343
  - `method` `VoiceEngine._load_wake_model` — line 362
  - `method` `VoiceEngine.listen_for_wake_word` — line 385
  - `method` `VoiceEngine.listen_for_command` — line 432
  - `method` `VoiceEngine.speak` — line 542
  - `method` `VoiceEngine.sleep` — line 610
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
- size: 274 bytes
- hash: `9a35d9c4d6e3`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/evaluation.py`

- language: `py`
- size: 256 bytes
- hash: `a1c401a697c8`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/event_bus.py`

- language: `py`
- size: 246 bytes
- hash: `76b5c60af46b`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/experience.py`

- language: `py`
- size: 256 bytes
- hash: `a9d63c07df82`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/groups.py`

- language: `py`
- size: 244 bytes
- hash: `45f066ef6a39`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/hardware.py`

- language: `py`
- size: 248 bytes
- hash: `a01a163a4b8f`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/improvements.py`

- language: `py`
- size: 260 bytes
- hash: `fc5ed8236923`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/learning/__init__.py`

- language: `py`
- size: 52 bytes
- hash: `e755ede6797e`

## `src/living_assistant/learning/canary.py`

- language: `py`
- size: 21000 bytes
- hash: `5eefae43d1b6`
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
- size: 39450 bytes
- hash: `6293108bf299`
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
- size: 6952 bytes
- hash: `e97659bf3aff`
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
- size: 8449 bytes
- hash: `b5e82a06876c`
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
- size: 602 bytes
- hash: `a70731a8290c`
- imports:
  - `eval_engine`
  - `eval_measure`
  - `eval_store`
  - `living_assistant.core.config`

## `src/living_assistant/learning/experience.py`

- language: `py`
- size: 26494 bytes
- hash: `0c238af780d2`
- symbols:
  - `function` `_now` — line 67
  - `function` `_redact` — line 71
  - `function` `_safe_json` — line 75
  - `function` `_norm` — line 95
  - `function` `_fingerprint` — line 99
  - `function` `_tokens` — line 104
  - `class` `ExperienceEngine` — line 109
  - `method` `ExperienceEngine.__init__` — line 116
  - `method` `ExperienceEngine._row` — line 140
  - `method` `ExperienceEngine.get` — line 151
  - `method` `ExperienceEngine.list` — line 154
  - `method` `ExperienceEngine.effective_confidence` — line 163
  - `method` `ExperienceEngine._conflicts` — line 176
  - `method` `ExperienceEngine._mark_conflicts` — line 185
  - `method` `ExperienceEngine.record` — line 190
  - `method` `ExperienceEngine.confirm` — line 226
  - `method` `ExperienceEngine.verify` — line 236
  - `method` `ExperienceEngine.reject` — line 253
  - `method` `ExperienceEngine.supersede` — line 261
  - `method` `ExperienceEngine.search` — line 267
  - `method` `ExperienceEngine.context_for` — line 289
  - `method` `ExperienceEngine.result_success` — line 323
  - `method` `ExperienceEngine.record_episode` — line 330
  - `method` `ExperienceEngine.learn_from_trace` — line 339
  - `method` `ExperienceEngine._failure_signature` — line 362
  - `method` `ExperienceEngine.failure_patterns` — line 376
  - `method` `ExperienceEngine.episodes` — line 389
  - `method` `ExperienceEngine.maintenance` — line 396
  - `method` `ExperienceEngine.stats` — line 442
- imports:
  - `__future__`
  - `datetime`
  - `hashlib`
  - `json`
  - `living_assistant.core.config`
  - `living_assistant.core.sqlite_utils`
  - `living_assistant.security.security_utils`
  - `math`
  - `pathlib`
  - `re`
  - `sqlite3`
  - `typing`
  - `uuid`

## `src/living_assistant/learning/improvements.py`

- language: `py`
- size: 14507 bytes
- hash: `d29e1b3fe3c0`
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
- size: 6512 bytes
- hash: `e23461f9e513`
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
- size: 3120 bytes
- hash: `76b1d61aef04`
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
- size: 4692 bytes
- hash: `fb02d4e9bad7`
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
- size: 12419 bytes
- hash: `033338674617`
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
- size: 9776 bytes
- hash: `4eee9df47209`
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
- size: 240 bytes
- hash: `60f1a169a53d`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/model_provider.py`

- language: `py`
- size: 256 bytes
- hash: `fd0396c698e5`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/models.py`

- language: `py`
- size: 240 bytes
- hash: `acd2d221b29b`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/notifications.py`

- language: `py`
- size: 258 bytes
- hash: `a255f3ec2bd1`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/observer.py`

- language: `py`
- size: 248 bytes
- hash: `e7dd22aed160`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/orchestrator.py`

- language: `py`
- size: 256 bytes
- hash: `916d16dc3056`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/orchestrator_teams.py`

- language: `py`
- size: 268 bytes
- hash: `8d27b031ae4e`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/overlay.py`

- language: `py`
- size: 248 bytes
- hash: `236630c0d1f6`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/personal_state.py`

- language: `py`
- size: 256 bytes
- hash: `83836529262d`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/platform_hardening.py`

- language: `py`
- size: 268 bytes
- hash: `9001d593eacd`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/prompts.py`

- language: `py`
- size: 246 bytes
- hash: `6c7bb925e097`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/quarantine.py`

- language: `py`
- size: 256 bytes
- hash: `ec887a364fa7`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/release_manager.py`

- language: `py`
- size: 262 bytes
- hash: `88999c7b5952`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/resource_manager.py`

- language: `py`
- size: 264 bytes
- hash: `0119d29d1f25`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/routines.py`

- language: `py`
- size: 248 bytes
- hash: `1397945dc430`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/runtime.py`

- language: `py`
- size: 242 bytes
- hash: `7b032f4b910b`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/sandbox.py`

- language: `py`
- size: 250 bytes
- hash: `87cf2ac51319`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/security/__init__.py`

- language: `py`
- size: 52 bytes
- hash: `3b2fc361499d`

## `src/living_assistant/security/api_auth.py`

- language: `py`
- size: 1161 bytes
- hash: `b95391da8dc2`
- symbols:
  - `function` `ensure_api_token` — line 7
  - `function` `get_api_token` — line 30
- imports:
  - `living_assistant.core.config`
  - `os`
  - `pathlib`
  - `secrets`
  - `string`

## `src/living_assistant/security/quarantine.py`

- language: `py`
- size: 5583 bytes
- hash: `e60ba359c454`
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
- size: 4537 bytes
- hash: `997302238abb`
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
- size: 12253 bytes
- hash: `6b66f475ce62`
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
- size: 41608 bytes
- hash: `c3db2d188fa1`
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
- size: 8165 bytes
- hash: `1f688cfb470f`
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
- size: 48207 bytes
- hash: `3883591f9dec`
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
- size: 8375 bytes
- hash: `6e1682cac0a9`
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
- size: 332 bytes
- hash: `01d10de9de72`
- symbols:
  - `function` `_safe_json` — line 7
  - `function` `_event_time` — line 13
- imports:
  - `__future__`
  - `json`
  - `living_assistant.security.security_guardian`

## `src/living_assistant/security/sensors_macos.py`

- language: `py`
- size: 1353 bytes
- hash: `45272620048d`
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
- size: 5677 bytes
- hash: `6723a30fe356`
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
- size: 2854 bytes
- hash: `c3581d90e130`
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
- size: 270 bytes
- hash: `92c4ec85ef4a`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/security_policy.py`

- language: `py`
- size: 266 bytes
- hash: `5559e0209e6f`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/security_sensors.py`

- language: `py`
- size: 268 bytes
- hash: `0bef830e4478`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/security_utils.py`

- language: `py`
- size: 264 bytes
- hash: `40613db42b10`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/sessions.py`

- language: `py`
- size: 244 bytes
- hash: `8cd7c56dffc1`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/skills.py`

- language: `py`
- size: 240 bytes
- hash: `dbffab8da461`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/sqlite_utils.py`

- language: `py`
- size: 252 bytes
- hash: `5058ed64bf81`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/storage_utils.py`

- language: `py`
- size: 254 bytes
- hash: `a55ee68db67c`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/supervisors/__init__.py`

- language: `py`
- size: 0 bytes
- hash: `e3b0c44298fc`

## `src/living_assistant/supervisors/development.py`

- language: `py`
- size: 4062 bytes
- hash: `7cbcade40cad`
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
- size: 2663 bytes
- hash: `4194c6ecf33f`
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
- size: 3626 bytes
- hash: `3b49c84cc0a0`
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
- size: 3731 bytes
- hash: `53dbcfd7b33b`
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
- size: 3687 bytes
- hash: `c1b16f1468dc`
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
- size: 3727 bytes
- hash: `0c14e8935966`
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
- size: 3611 bytes
- hash: `8f932878b01d`
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
- size: 50 bytes
- hash: `636dd93c0d5b`

## `src/living_assistant/system/codebase_index.py`

- language: `py`
- size: 18830 bytes
- hash: `5a8187cb09c0`
- symbols:
  - `class` `CodeChunk` — line 45
  - `class` `CodebaseIndex` — line 53
  - `method` `CodebaseIndex.__init__` — line 63
  - `method` `CodebaseIndex._init_db` — line 85
  - `method` `CodebaseIndex._project_id` — line 116
  - `method` `CodebaseIndex._is_binary` — line 120
  - `method` `CodebaseIndex._iter_source_files` — line 129
  - `method` `CodebaseIndex._bounded_chunks` — line 153
  - `method` `CodebaseIndex._python_chunks` — line 181
  - `method` `CodebaseIndex._markdown_chunks` — line 207
  - `method` `CodebaseIndex._generic_chunks` — line 226
  - `method` `CodebaseIndex._chunks_for_file` — line 248
  - `method` `CodebaseIndex._features` — line 269
  - `method` `CodebaseIndex._cosine` — line 294
  - `method` `CodebaseIndex._dump_vector` — line 300
  - `method` `CodebaseIndex._load_vector` — line 304
  - `method` `CodebaseIndex.index_project` — line 311
  - `method` `CodebaseIndex.status` — line 377
  - `method` `CodebaseIndex.search` — line 396
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
- size: 5077 bytes
- hash: `b04dd7646edb`
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
- size: 21594 bytes
- hash: `8ee3d0d48c26`
- symbols:
  - `class` `NervousSystem` — line 16
  - `method` `NervousSystem.__init__` — line 18
  - `method` `NervousSystem._on_config_reload` — line 32
  - `method` `NervousSystem._ports` — line 57
  - `method` `NervousSystem._process_events` — line 60
  - `method` `NervousSystem._todo_events` — line 87
  - `method` `NervousSystem.tick` — line 94
  - `method` `NervousSystem._event_message` — line 242
  - `method` `NervousSystem.run_forever` — line 276
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

## `src/living_assistant/system/groups.py`

- language: `py`
- size: 8589 bytes
- hash: `c2c9917adb3d`
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
- size: 3118 bytes
- hash: `819e4a4a551d`
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
- size: 9656 bytes
- hash: `bcbe9437863d`
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
- size: 7319 bytes
- hash: `786663fdf110`
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
- size: 8635 bytes
- hash: `cbdaa7f325fa`
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
- size: 4565 bytes
- hash: `461fb3bc5505`
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
- size: 15091 bytes
- hash: `31e359399fad`
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
- size: 11244 bytes
- hash: `5d54fe0781dd`
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
- size: 27683 bytes
- hash: `d7e4eb81a421`
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
- size: 12608 bytes
- hash: `e69678efe36b`
- symbols:
  - `class` `ModelRuntimePolicy` — line 11
  - `method` `ModelRuntimePolicy.to_dict` — line 22
  - `class` `ResourceManager` — line 26
  - `method` `ResourceManager.__init__` — line 27
  - `method` `ResourceManager._nvidia_runtime` — line 33
  - `method` `ResourceManager._cpu_temperature_c` — line 53
  - `method` `ResourceManager.snapshot` — line 66
  - `method` `ResourceManager.thermal_pressure` — line 83
  - `method` `ResourceManager._select_model_policy` — line 98
  - `method` `ResourceManager.can_start_model` — line 179
  - `method` `ResourceManager.can_admit_model` — line 210
  - `method` `ResourceManager.model_runtime_status` — line 246
- imports:
  - `__future__`
  - `dataclasses`
  - `living_assistant.system.hardware`
  - `psutil`
  - `shutil`
  - `subprocess`

## `src/living_assistant/system/routines.py`

- language: `py`
- size: 5636 bytes
- hash: `29492d07905c`
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

## `src/living_assistant/system/watchers.py`

- language: `py`
- size: 5865 bytes
- hash: `31dbbdb3d262`
- symbols:
  - `class` `WatchRegistry` — line 8
  - `method` `WatchRegistry.__init__` — line 9
  - `method` `WatchRegistry._load` — line 15
  - `method` `WatchRegistry._save` — line 21
  - `method` `WatchRegistry.add` — line 24
  - `method` `WatchRegistry.remove` — line 39
  - `method` `WatchRegistry.list` — line 47
  - `method` `WatchRegistry._scan` — line 51
  - `method` `WatchRegistry.rebaseline` — line 73
  - `method` `WatchRegistry.poll` — line 92
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
- size: 14739 bytes
- hash: `200f4880acd2`
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
- size: 252 bytes
- hash: `493301438fdc`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/tools/__init__.py`

- language: `py`
- size: 52 bytes
- hash: `025cdef7005a`

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
- size: 2611 bytes
- hash: `b4984e3c5f91`
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

## `src/living_assistant/tools/connectortools.py`

- language: `py`
- size: 1105 bytes
- hash: `2f8f6c90ff4b`
- symbols:
  - `function` `build_connector_tools` — line 6
- imports:
  - `__future__`
  - `base`
  - `json`

## `src/living_assistant/tools/database.py`

- language: `py`
- size: 18722 bytes
- hash: `ec16433c4be1`
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
- size: 6105 bytes
- hash: `f23a6cd43e5d`
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

## `src/living_assistant/tools/experiencetools.py`

- language: `py`
- size: 3468 bytes
- hash: `71172dc855eb`
- symbols:
  - `function` `build_experience_tools` — line 7
- imports:
  - `__future__`
  - `base`
  - `living_assistant.learning.experience`
  - `living_assistant.learning.knowledge_gap_detection`

## `src/living_assistant/tools/filesystem.py`

- language: `py`
- size: 7618 bytes
- hash: `33713bbad6cd`
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
- size: 6713 bytes
- hash: `73f0f3cb2d5d`
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

## `src/living_assistant/tools/grouptools.py`

- language: `py`
- size: 1289 bytes
- hash: `979b5741b352`
- symbols:
  - `function` `build_group_tools` — line 6
- imports:
  - `__future__`
  - `base`
  - `living_assistant.system.groups`

## `src/living_assistant/tools/historytools.py`

- language: `py`
- size: 794 bytes
- hash: `f0fb319f711f`
- symbols:
  - `function` `build_run_history_tools` — line 7
- imports:
  - `__future__`
  - `base`
  - `living_assistant.learning.run_history`

## `src/living_assistant/tools/improvementtools.py`

- language: `py`
- size: 6527 bytes
- hash: `4d9bea563b1e`
- symbols:
  - `function` `build_improvement_tools` — line 9
- imports:
  - `__future__`
  - `base`
  - `living_assistant.learning.canary`
  - `living_assistant.learning.evaluation`
  - `living_assistant.learning.improvements`
  - `living_assistant.learning.repair_loop`

## `src/living_assistant/tools/peertools.py`

- language: `py`
- size: 1092 bytes
- hash: `dd9846ffe296`
- symbols:
  - `function` `build_peer_tools` — line 6
- imports:
  - `__future__`
  - `base`

## `src/living_assistant/tools/personal.py`

- language: `py`
- size: 3085 bytes
- hash: `3f3c1fe7020c`
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
- size: 3431 bytes
- hash: `68760c5c0b01`
- symbols:
  - `function` `build_planning_tools` — line 6
- imports:
  - `base`
  - `living_assistant.agents.task_graph`
  - `pathlib`
  - `typing`

## `src/living_assistant/tools/projects.py`

- language: `py`
- size: 12554 bytes
- hash: `2f64bce916b8`
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
- size: 1270 bytes
- hash: `60fec7cea5ea`
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

## `src/living_assistant/tools/security.py`

- language: `py`
- size: 12105 bytes
- hash: `f1f08dd80ec8`
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
- size: 18453 bytes
- hash: `1ffa09bce5e1`
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

## `src/living_assistant/tools/voicetools.py`

- language: `py`
- size: 1376 bytes
- hash: `81a1f28b4622`
- symbols:
  - `function` `build_voice_tools` — line 5
- imports:
  - `__future__`
  - `base`
  - `living_assistant.desktop.voice`

## `src/living_assistant/tools/webtools.py`

- language: `py`
- size: 31050 bytes
- hash: `2f4ef1bc1902`
- symbols:
  - `class` `_NetworkGate` — line 36
  - `method` `_NetworkGate.__init__` — line 37
  - `function` `build_web_tools` — line 42
- imports:
  - `__future__`
  - `base`
  - `collections`
  - `datetime`
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
- size: 242 bytes
- hash: `4868bf0cf08e`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/verifier.py`

- language: `py`
- size: 252 bytes
- hash: `5cc8e78dd15d`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/voice.py`

- language: `py`
- size: 244 bytes
- hash: `841a03391215`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/watchers.py`

- language: `py`
- size: 248 bytes
- hash: `5aee4408913f`
- imports:
  - `importlib`
  - `sys`

## `src/living_assistant/webui/index.html`

- language: `html`
- size: 930 bytes
- hash: `14bf7c30afba`

## `src/living_assistant/webui/package.json`

- language: `json`
- size: 661 bytes
- hash: `0200ff2ac484`

## `src/living_assistant/webui/src/chart_loader.js`

- language: `js`
- size: 2346 bytes
- hash: `435d98b054bc`
- symbols:
  - `function` `installedPlotly` — line 6
  - `function` `loadScript` — line 15
  - `function` `loadPlotly` — line 53

## `src/living_assistant/webui/src/main.js`

- language: `js`
- size: 34857 bytes
- hash: `7a8b2a40dce5`
- symbols:
  - `class` `App` — line 106
  - `class` `ResourceChart` — line 326
  - `function` `cx` — line 13
  - `function` `safeText` — line 15
  - `function` `fmtBytes` — line 16
  - `function` `hashPage` — line 24
  - `function` `makeSessionId` — line 28
  - `function` `tokenizeInline` — line 34
  - `function` `renderPrismToken` — line 55
  - `function` `CodeBlock` — line 64
  - `function` `Markdown` — line 71
  - `function` `UsageTable` — line 395
  - `function` `ModelTable` — line 414
  - `function` `ApprovalList` — line 434
  - `function` `ActivityList` — line 448
  - `function` `ItemList` — line 460
  - `function` `trace` — line 351
- imports:
  - `./chart_loader.js`
  - `./resource_chart_data.js`

## `src/living_assistant/webui/src/resource_chart_data.js`

- language: `js`
- size: 2041 bytes
- hash: `64a66e0d4b7b`
- symbols:
  - `function` `finiteNumber` — line 2
  - `function` `percentMetric` — line 7
  - `function` `makeResourceSample` — line 13
  - `function` `resourceSeries` — line 34
  - `function` `roundedPercent` — line 42
  - `function` `resourceSampleLabel` — line 47

## `src/living_assistant/webui/src/styles.css`

- language: `css`
- size: 249 bytes
- hash: `bad2ee2ef6b4`

## `src/living_assistant/webui/vite.config.js`

- language: `js`
- size: 252 bytes
- hash: `7289cd99fb20`
- imports:
  - `@vitejs/plugin-react`
  - `vite`

## `src/living_assistant/workspace.py`

- language: `py`
- size: 246 bytes
- hash: `cdebba0ed7fa`
- imports:
  - `importlib`
  - `sys`

