# Module: tests

> Generated navigation map. Source code is authoritative.

## `tests/test_agents.py`

- language: `py`
- size: 199 bytes
- hash: `f31810e2e66b`
- symbols:
  - `function` `test_handoff_protocol` — line 3
- imports:
  - `living_assistant.agents`

## `tests/test_approval.py`

- language: `py`
- size: 2155 bytes
- hash: `cbdf30e2042a`
- symbols:
  - `function` `test_one_time_approval` — line 3
  - `function` `test_stale_pending_approval_expires_and_does_not_block_requeue` — line 12
  - `function` `test_preapproval_hash_ignores_boundary_whitespace_only` — line 29
  - `function` `test_preapproval_hash_preserves_internal_whitespace` — line 37
- imports:
  - `living_assistant.approval`

## `tests/test_approval_sound.py`

- language: `py`
- size: 2503 bytes
- hash: `9c6ca7cbb5dc`
- symbols:
  - `function` `test_notifier_plays_approval_sound_only_when_not_quiet` — line 5
  - `function` `test_pending_approval_sounds_once_for_new_gate` — line 22
  - `function` `test_preapproved_retry_does_not_sound_again` — line 35
  - `function` `test_sound_can_be_disabled` — line 48
- imports:
  - `living_assistant.core.approval`
  - `living_assistant.system.notifications`

## `tests/test_arch03_cli_package.py`

- language: `py`
- size: 1274 bytes
- hash: `3dc536ed9d67`
- symbols:
  - `function` `_command_tree` — line 6
  - `function` `test_cli_package_exposes_expected_root_contract` — line 19
- imports:
  - `__future__`
  - `living_assistant.cli`

## `tests/test_arch04_evaluation_split.py`

- language: `py`
- size: 1193 bytes
- hash: `e586c619fc45`
- symbols:
  - `function` `test_evaluation_compatibility_facade_preserves_public_symbols` — line 10
  - `function` `test_evaluation_responsibilities_live_in_split_modules` — line 19
- imports:
  - `__future__`
  - `living_assistant.evaluation`
  - `living_assistant.learning`
  - `living_assistant.learning.eval_engine`
  - `living_assistant.learning.eval_measure`
  - `living_assistant.learning.eval_store`

## `tests/test_arch05_sensor_split.py`

- language: `py`
- size: 786 bytes
- hash: `c8586fa6ed1c`
- symbols:
  - `function` `test_platform_sensor_collectors_are_split_but_public_contract_is_preserved` — line 7
- imports:
  - `__future__`
  - `living_assistant.security`
  - `living_assistant.security_sensors`

## `tests/test_arch06_store_injection.py`

- language: `py`
- size: 2224 bytes
- hash: `a26cde5d6947`
- symbols:
  - `function` `test_persistent_stores_keep_injectable_storage_paths` — line 51
- imports:
  - `__future__`
  - `inspect`
  - `living_assistant.connectors.connectors`
  - `living_assistant.core.approval`
  - `living_assistant.core.calendar_store`
  - `living_assistant.core.memory`
  - `living_assistant.core.personal_state`
  - `living_assistant.core.sessions`
  - `living_assistant.core.skills`
  - `living_assistant.learning.canary`
  - `living_assistant.learning.eval_store`
  - `living_assistant.learning.experience`
  - `living_assistant.learning.improvements`
  - `living_assistant.security.quarantine`
  - `living_assistant.security.security_guardian`
  - `living_assistant.security.security_sensors`
  - `living_assistant.system.groups`
  - `living_assistant.system.notifications`
  - `living_assistant.system.routines`
  - `living_assistant.system.watchers`
  - `living_assistant.tools.projects`
  - `living_assistant.tools.shell`

## `tests/test_arch07_tool_registry.py`

- language: `py`
- size: 758 bytes
- hash: `a48daa2665ab`
- symbols:
  - `function` `_tool` — line 9
  - `function` `test_registry_preserves_order_and_lookup` — line 13
  - `function` `test_registry_rejects_duplicate_names` — line 21
- imports:
  - `__future__`
  - `living_assistant.tools.base`
  - `living_assistant.tools.registry`
  - `pytest`

## `tests/test_architecture_api.py`

- language: `py`
- size: 1632 bytes
- hash: `ae685584044b`
- symbols:
  - `function` `test_api_is_split_into_domain_routers_without_duplicate_routes` — line 20
  - `function` `test_api_bootstrap_is_no_longer_the_monolithic_route_file` — line 55
- imports:
  - `__future__`
  - `living_assistant`
  - `living_assistant.api_routes`
  - `pathlib`

## `tests/test_architecture_domains.py`

- language: `py`
- size: 977 bytes
- hash: `d5e457020ac9`
- symbols:
  - `function` `test_domain_packages_own_representative_implementations_and_legacy_aliases_match` — line 4
  - `function` `test_agents_and_connectors_packages_preserve_legacy_public_symbols` — line 20
- imports:
  - `importlib`

## `tests/test_config_hot_reload.py`

- language: `py`
- size: 5421 bytes
- hash: `bf68d8024b9e`
- symbols:
  - `function` `seeded` — line 10
  - `function` `test_reloader_applies_safe_sections_and_reports_structural_restart` — line 17
  - `function` `test_invalid_yaml_fails_once_without_mutating_live_config` — line 40
  - `function` `test_connector_enabled_requires_restart_but_refresh_window_is_live` — line 51
  - `class` `Processes` — line 64
  - `method` `Processes.list` — line 65
  - `class` `Watches` — line 66
  - `method` `Watches.poll` — line 67
  - `method` `Watches.rebaseline` — line 68
  - `class` `Note` — line 69
  - `method` `Note.__init__` — line 70
  - `method` `Note.flush` — line 71
  - `method` `Note.send` — line 72
  - `method` `Note.is_quiet` — line 73
  - `function` `test_daemon_tick_applies_live_notification_config` — line 76
  - `function` `test_mobile_and_peer_runtime_objects_receive_reloaded_cfg` — line 100
- imports:
  - `living_assistant.core.config`
  - `living_assistant.core.memory`
  - `living_assistant.system.config_reload`
  - `living_assistant.system.daemon`
  - `pathlib`
  - `yaml`

## `tests/test_connector_background_refresh.py`

- language: `py`
- size: 3378 bytes
- hash: `b01ff62b85e8`
- symbols:
  - `class` `Approval` — line 9
  - `method` `Approval.request` — line 10
  - `class` `Processes` — line 14
  - `method` `Processes.list` — line 15
  - `class` `Watches` — line 18
  - `method` `Watches.poll` — line 19
  - `method` `Watches.rebaseline` — line 20
  - `class` `Note` — line 23
  - `method` `Note.__init__` — line 24
  - `method` `Note.flush` — line 25
  - `method` `Note.send` — line 26
  - `method` `Note.is_quiet` — line 27
  - `function` `test_manager_proactively_refreshes_only_enabled_expiring_google_and_microsoft` — line 30
  - `function` `test_daemon_runs_background_refresh_on_interval_and_surfaces_failure` — line 54
- imports:
  - `living_assistant.connector_credentials`
  - `living_assistant.connectors`
  - `living_assistant.daemon`
  - `living_assistant.memory`
  - `time`

## `tests/test_daemon_crash_recovery.py`

- language: `py`
- size: 2277 bytes
- hash: `7400ec2da696`
- symbols:
  - `class` `Processes` — line 6
  - `method` `Processes.list` — line 7
  - `class` `Watches` — line 8
  - `method` `Watches.poll` — line 9
  - `method` `Watches.rebaseline` — line 10
  - `class` `Note` — line 11
  - `method` `Note.__init__` — line 12
  - `method` `Note.flush` — line 13
  - `method` `Note.send` — line 14
  - `method` `Note.is_quiet` — line 15
  - `function` `test_run_forever_recovers_from_tick_exception_and_records_report` — line 18
  - `function` `test_installers_have_process_level_restart_policy` — line 49
- imports:
  - `living_assistant.daemon`
  - `living_assistant.memory`

## `tests/test_feat01_ast_patch_engine.py`

- language: `py`
- size: 3476 bytes
- hash: `10de69fbea75`
- symbols:
  - `function` `_engine` — line 9
  - `function` `test_ast_patch_allows_modifying_existing_function_without_deleting_neighbors` — line 20
  - `function` `test_ast_patch_blocks_accidental_function_deletion` — line 31
  - `function` `test_ast_patch_blocks_syntax_invalid_python` — line 42
  - `function` `test_ast_patch_tracks_methods_not_just_top_level_functions` — line 50
  - `function` `test_non_python_content_keeps_exact_file_diff_behavior` — line 60
  - `function` `test_apply_revalidates_stored_python_content_before_approval` — line 67
- imports:
  - `__future__`
  - `living_assistant.approval`
  - `living_assistant.improvements`
  - `living_assistant.learning.patch_engine`
  - `living_assistant.workspace`

## `tests/test_feat02_project_auditor.py`

- language: `py`
- size: 2073 bytes
- hash: `df3145a6eba9`
- symbols:
  - `function` `test_project_auditor_reports_dependencies_lint_dead_code_and_security_without_secret_values` — line 12
  - `function` `test_project_auditor_is_workspace_bounded` — line 36
  - `function` `test_project_audit_is_exposed_as_existing_project_tool_family` — line 46
- imports:
  - `__future__`
  - `json`
  - `living_assistant.system.project_auditor`
  - `living_assistant.tools.projects`
  - `living_assistant.workspace`
  - `pytest`

## `tests/test_feat03_repair_loop.py`

- language: `py`
- size: 8057 bytes
- hash: `d0290d73abb9`
- symbols:
  - `function` `_build` — line 12
  - `function` `_approve` — line 47
  - `function` `_failed_evaluation` — line 53
  - `function` `test_repair_loop_generates_and_evaluates_without_applying` — line 70
  - `function` `test_repair_loop_repeats_only_up_to_approved_bound` — line 101
  - `function` `test_repair_loop_revalidates_stored_commands_before_approval` — line 120
  - `function` `test_invalid_internal_authorization_cannot_bypass_evaluation_approval` — line 135
  - `function` `test_repair_authorization_is_bound_to_exact_plan` — line 151
  - `function` `test_improvement_tool_exposes_repair_only_when_loop_is_supplied` — line 178
- imports:
  - `__future__`
  - `living_assistant.approval`
  - `living_assistant.evaluation`
  - `living_assistant.improvements`
  - `living_assistant.learning.repair_loop`
  - `living_assistant.workspace`
  - `pathlib`

## `tests/test_feat04_regression_detection.py`

- language: `py`
- size: 2589 bytes
- hash: `f6d6e3c4a21e`
- symbols:
  - `function` `_agg` — line 7
  - `function` `test_stable_regression_beyond_budget_is_detected` — line 24
  - `function` `test_noisy_point_estimate_does_not_false_positive` — line 36
  - `function` `test_too_few_samples_falls_back_to_existing_budget_rule` — line 47
  - `function` `test_compare_benchmark_reports_statistical_details_for_latency_and_memory` — line 54
  - `function` `test_legacy_aggregate_without_raw_runs_preserves_percentage_behavior` — line 63
- imports:
  - `__future__`
  - `living_assistant.evaluation`
  - `living_assistant.learning.regression_detection`

## `tests/test_feat05_run_history.py`

- language: `py`
- size: 4468 bytes
- hash: `0631b6e9c94a`
- symbols:
  - `class` `FakeProvider` — line 12
  - `method` `FakeProvider.__init__` — line 13
  - `method` `FakeProvider.chat` — line 16
  - `method` `FakeProvider.unload` — line 30
  - `class` `Specialists` — line 34
  - `method` `Specialists.delegate` — line 35
  - `class` `NoPressure` — line 39
  - `method` `NoPressure.can_start_model` — line 40
  - `function` `test_run_history_persists_and_queries_last_tuesday` — line 44
  - `function` `test_run_history_redacts_tool_arguments_and_does_not_store_raw_result` — line 67
  - `function` `test_orchestrator_records_one_run_and_tool_action` — line 84
  - `function` `test_run_history_tool_supports_human_time_filter` — line 114
- imports:
  - `__future__`
  - `datetime`
  - `living_assistant.agents.orchestrator`
  - `living_assistant.learning.run_history`
  - `living_assistant.model_provider`
  - `living_assistant.tools.base`
  - `living_assistant.tools.historytools`

## `tests/test_feat06_knowledge_gaps.py`

- language: `py`
- size: 2999 bytes
- hash: `ef4e3135d1d3`
- symbols:
  - `function` `_engine` — line 8
  - `function` `test_recurring_failed_topic_surfaces_as_learning_opportunity` — line 15
  - `function` `test_single_failure_is_not_called_a_consistent_gap` — line 42
  - `function` `test_project_filter_keeps_unrelated_projects_separate` — line 50
  - `function` `test_gap_output_never_reintroduces_redacted_secret` — line 62
  - `function` `test_experience_tools_surface_knowledge_gap_detector` — line 72
- imports:
  - `__future__`
  - `living_assistant.learning.experience`
  - `living_assistant.learning.knowledge_gap_detection`
  - `living_assistant.tools.experiencetools`

## `tests/test_feat07_model_usage.py`

- language: `py`
- size: 7576 bytes
- hash: `46a42fcd8c0b`
- symbols:
  - `class` `_Specialists` — line 13
  - `method` `_Specialists.delegate` — line 14
  - `class` `_NonStreamingProvider` — line 18
  - `method` `_NonStreamingProvider.chat` — line 19
  - `class` `_StreamingProvider` — line 27
  - `method` `_StreamingProvider.chat_stream` — line 28
  - `class` `_MM` — line 38
  - `method` `_MM.__init__` — line 41
  - `method` `_MM.activate` — line 45
  - `method` `_MM.lease` — line 48
  - `method` `_MM.sleep` — line 52
  - `function` `test_model_usage_store_tracks_exact_provider_counts_and_session_filter` — line 56
  - `function` `test_orchestrator_records_non_streaming_usage_per_session` — line 93
  - `function` `test_orchestrator_records_streaming_final_usage_metadata` — line 109
  - `function` `test_specialist_usage_keeps_session_and_run_identity` — line 127
  - `function` `test_delegate_agent_propagates_internal_usage_identity_without_model_arguments` — line 162
  - `function` `test_model_usage_api_is_authenticated_and_returns_summary` — line 193
  - `function` `test_dashboard_exposes_model_usage_without_rendering_provider_html` — line 217
- imports:
  - `__future__`
  - `contextlib`
  - `fastapi.testclient`
  - `living_assistant.agents.agents`
  - `living_assistant.agents.orchestrator`
  - `living_assistant.system.model_usage`
  - `types`

## `tests/test_feat08_searxng.py`

- language: `py`
- size: 8523 bytes
- hash: `7090d79fdda9`
- symbols:
  - `function` `_tool_map` — line 8
  - `class` `_Response` — line 12
  - `method` `_Response.__init__` — line 13
  - `method` `_Response.raise_for_status` — line 18
  - `method` `_Response.json` — line 22
  - `class` `_Browser` — line 26
  - `method` `_Browser.__init__` — line 27
  - `method` `_Browser.search_web` — line 31
  - `method` `_Browser.search_images` — line 39
  - `function` `test_explicit_searxng_web_search_uses_json_api_without_api_key` — line 48
  - `function` `test_searxng_image_search_maps_image_fields` — line 108
  - `function` `test_auto_prefers_configured_searxng_before_browser` — line 166
  - `function` `test_auto_falls_back_to_browser_when_searxng_is_unavailable` — line 207
  - `function` `test_explicit_searxng_rejects_missing_or_credential_bearing_url` — line 249
  - `function` `test_default_config_supports_searxng_environment_override` — line 281
- imports:
  - `__future__`
  - `living_assistant.core.config`
  - `living_assistant.core.workspace`
  - `living_assistant.tools.webtools`

## `tests/test_feat09_safe_commands.py`

- language: `py`
- size: 5476 bytes
- hash: `78496d66a88c`
- symbols:
  - `function` `_handlers` — line 11
  - `class` `_Events` — line 15
  - `method` `_Events.__init__` — line 16
  - `method` `_Events.publish` — line 20
  - `function` `test_command_explainer_is_deterministic_and_does_not_echo_arguments` — line 27
  - `function` `test_run_command_publishes_preview_before_subprocess_execution` — line 48
  - `function` `test_command_approval_shows_explanation_and_exact_retry_still_consumes` — line 83
  - `function` `test_blocked_command_is_explained_but_never_executed` — line 117
  - `function` `test_start_process_approval_also_contains_command_explanation` — line 144
- imports:
  - `__future__`
  - `living_assistant.core.approval`
  - `living_assistant.core.workspace`
  - `living_assistant.security.safe_commands`
  - `living_assistant.tools.shell`
  - `types`

## `tests/test_feat10_airllm_provider.py`

- language: `py`
- size: 9642 bytes
- hash: `303ef5133c9d`
- symbols:
  - `class` `_FakeInputIds` — line 13
  - `method` `_FakeInputIds.__init__` — line 16
  - `method` `_FakeInputIds.cuda` — line 19
  - `class` `_FakeTokenizer` — line 24
  - `method` `_FakeTokenizer.__init__` — line 25
  - `method` `_FakeTokenizer.apply_chat_template` — line 31
  - `method` `_FakeTokenizer.__call__` — line 36
  - `method` `_FakeTokenizer.decode` — line 41
  - `class` `_FakeAirModel` — line 46
  - `method` `_FakeAirModel.__init__` — line 47
  - `method` `_FakeAirModel.generate` — line 51
  - `class` `_FakeAutoModel` — line 57
  - `method` `_FakeAutoModel.from_pretrained` — line 62
  - `function` `_reset_fake_model` — line 68
  - `function` `_install_fake_airllm` — line 73
  - `function` `test_airllm_is_lazy_optional_dependency` — line 84
  - `function` `test_airllm_uses_official_load_options_and_only_decodes_new_tokens` — line 103
  - `function` `test_airllm_rejects_unverified_tool_calling_before_loading` — line 148
  - `function` `test_airllm_stream_is_honest_single_final_chunk` — line 160
  - `function` `test_composite_routes_prefixed_models_without_changing_ollama_names` — line 172
  - `function` `test_airllm_extra_and_packaged_default_config_are_present` — line 251
  - `function` `test_runtime_enables_composite_provider_without_importing_airllm` — line 264
- imports:
  - `__future__`
  - `importlib`
  - `living_assistant.core.model_provider`
  - `living_assistant.model_provider`
  - `pytest`
  - `tomllib`
  - `types`

## `tests/test_feat11_codebase_rag.py`

- language: `py`
- size: 5183 bytes
- hash: `070d1689b796`
- symbols:
  - `function` `_build_index` — line 10
  - `function` `test_section_aware_python_index_and_semantic_identifier_retrieval` — line 18
  - `function` `test_markdown_heading_chunking_is_preserved` — line 45
  - `function` `test_sensitive_generated_binary_and_oversized_files_are_not_persisted` — line 57
  - `function` `test_index_persists_across_process_like_reopen` — line 85
  - `function` `test_project_tools_expose_index_search_and_status_without_duplicate_tool_family` — line 102
  - `function` `test_code_index_remains_workspace_bounded` — line 118
- imports:
  - `__future__`
  - `living_assistant.core.workspace`
  - `living_assistant.system.codebase_index`
  - `living_assistant.tools.projects`
  - `pathlib`

## `tests/test_feat12_workspace_snapshots.py`

- language: `py`
- size: 8032 bytes
- hash: `a4a371cdf4a9`
- symbols:
  - `class` `AllowApproval` — line 13
  - `method` `AllowApproval.__init__` — line 14
  - `method` `AllowApproval.request` — line 18
  - `function` `_manager` — line 23
  - `function` `test_snapshot_restore_recovers_source_and_preserves_generated_directories` — line 36
  - `function` `test_snapshot_metadata_never_exposes_archive_contents_or_credentials` — line 56
  - `function` `test_ai_write_file_snapshots_immediately_before_mutation` — line 73
  - `function` `test_ai_shell_command_snapshots_before_possible_workspace_mutation` — line 88
  - `function` `test_snapshot_failure_blocks_ai_file_mutation` — line 110
  - `function` `test_project_snapshot_restore_tool_is_approval_gated` — line 130
  - `function` `test_deepest_workspace_root_is_snapshotted_for_registered_project` — line 152
  - `function` `test_improvement_apply_creates_recoverable_workspace_snapshot` — line 161
  - `function` `test_snapshot_storage_inside_workspace_is_rejected` — line 187
  - `function` `test_cli_exposes_single_command_restore_path` — line 199
- imports:
  - `__future__`
  - `living_assistant.core.workspace`
  - `living_assistant.system.workspace_snapshots`
  - `living_assistant.tools.filesystem`
  - `living_assistant.tools.projects`
  - `living_assistant.tools.shell`
  - `pathlib`
  - `sys`

## `tests/test_feat13_model_manager_ui.py`

- language: `py`
- size: 7398 bytes
- hash: `d18057407792`
- symbols:
  - `class` `_Resources` — line 13
  - `method` `_Resources.__init__` — line 14
  - `method` `_Resources.snapshot` — line 29
  - `function` `provider` — line 34
  - `function` `test_local_catalog_reports_disk_and_labeled_vram` — line 60
  - `function` `test_local_model_pull_uses_existing_ollama_provider` — line 80
  - `function` `test_local_model_management_rejects_invalid_names` — line 92
  - `function` `test_local_model_delete_requires_confirmation_and_refuses_in_use` — line 98
  - `function` `test_model_router_exposes_local_pull_and_delete` — line 123
  - `function` `test_webui_contains_local_model_manager_without_unsafe_model_html` — line 158
  - `function` `test_ollama_provider_management_calls_expected_http_endpoints` — line 171
- imports:
  - `__future__`
  - `living_assistant.api_routes`
  - `living_assistant.api_routes.schemas`
  - `living_assistant.core.model_provider`
  - `pathlib`
  - `pytest`
  - `types`

## `tests/test_filesystem_search.py`

- language: `py`
- size: 1383 bytes
- hash: `7a90577c968e`
- symbols:
  - `function` `handlers` — line 5
  - `function` `test_search_files_supports_regex_and_extension_filter` — line 9
  - `function` `test_search_files_rejects_invalid_regex` — line 19
  - `function` `test_search_files_skips_binary_content` — line 25
  - `function` `test_search_files_keeps_sensitive_content_excluded` — line 31
- imports:
  - `living_assistant.tools.filesystem`
  - `living_assistant.workspace`

## `tests/test_group_health_daemon.py`

- language: `py`
- size: 1388 bytes
- hash: `bae4930a99b5`
- symbols:
  - `class` `Processes` — line 5
  - `method` `Processes.list` — line 6
  - `class` `Watches` — line 9
  - `method` `Watches.poll` — line 10
  - `method` `Watches.rebaseline` — line 11
  - `class` `Note` — line 14
  - `method` `Note.flush` — line 15
  - `method` `Note.send` — line 16
  - `method` `Note.is_quiet` — line 17
  - `class` `Groups` — line 20
  - `method` `Groups.__init__` — line 21
  - `method` `Groups.health_all` — line 22
  - `function` `test_daemon_emits_group_degraded_once_and_recovery_once` — line 26
- imports:
  - `living_assistant.daemon`
  - `living_assistant.memory`

## `tests/test_groups_parallel.py`

- language: `py`
- size: 3568 bytes
- hash: `b9b9305e2e62`
- symbols:
  - `class` `Projects` — line 8
  - `method` `Projects.__init__` — line 9
  - `method` `Projects.get` — line 11
  - `class` `Approval` — line 14
  - `method` `Approval.request` — line 15
  - `class` `Processes` — line 18
  - `method` `Processes.__init__` — line 19
  - `method` `Processes.start` — line 21
  - `method` `Processes.list` — line 28
  - `function` `test_group_dependency_plan_builds_topological_stages` — line 31
  - `function` `test_group_parallel_start_runs_independent_projects_concurrently` — line 40
  - `function` `test_group_dependency_failure_skips_downstream_projects` — line 50
  - `function` `test_group_dependency_cycle_is_rejected_by_plan` — line 60
  - `function` `test_group_health_tracks_expected_running_members` — line 68
- imports:
  - `__future__`
  - `living_assistant.groups`
  - `threading`
  - `time`

## `tests/test_hardware.py`

- language: `py`
- size: 336 bytes
- hash: `ce165ad15398`
- symbols:
  - `function` `hw` — line 5
  - `function` `test_profiles` — line 8
- imports:
  - `living_assistant.hardware`

## `tests/test_hierarchical_orchestration.py`

- language: `py`
- size: 6127 bytes
- hash: `40b267f6d396`
- symbols:
  - `class` `DummyModelManager` — line 6
  - `method` `DummyModelManager.__init__` — line 7
  - `method` `DummyModelManager.activate` — line 9
  - `method` `DummyModelManager.sleep` — line 10
  - `method` `DummyModelManager.lease` — line 11
  - `class` `DummyProvider` — line 15
  - `method` `DummyProvider.chat` — line 16
  - `function` `test_executive_routing` — line 44
  - `function` `test_development_supervisor_parallel` — line 52
  - `function` `test_aggregator_and_verifier` — line 64
  - `function` `test_aggregator_supports_legacy_model_manager_without_lease` — line 105
  - `function` `test_aggregator_invalid_json_falls_back_to_structured_specialist_synthesis` — line 129
- imports:
  - `living_assistant.models`
  - `living_assistant.supervisors.development`
  - `living_assistant.supervisors.executive`
  - `pytest`

## `tests/test_improvement_context.py`

- language: `py`
- size: 1545 bytes
- hash: `3dd1519336a2`
- symbols:
  - `function` `engine` — line 7
  - `function` `test_improvement_context_finds_imports_and_callers` — line 14
  - `function` `test_improvement_context_is_exposed_as_tool` — line 27
- imports:
  - `living_assistant.approval`
  - `living_assistant.improvements`
  - `living_assistant.tools.improvementtools`
  - `living_assistant.workspace`

## `tests/test_memory.py`

- language: `py`
- size: 1339 bytes
- hash: `9778a41a903d`
- symbols:
  - `function` `test_memory_search_rebuilds_fts_for_existing_database` — line 3

## `tests/test_memory_v02.py`

- language: `py`
- size: 575 bytes
- hash: `5bfc3d222712`
- symbols:
  - `function` `test_due_todo_and_events` — line 4
- imports:
  - `datetime`
  - `living_assistant.memory`

## `tests/test_mobile_bridge.py`

- language: `py`
- size: 6401 bytes
- hash: `139cdb20a879`
- symbols:
  - `class` `Registry` — line 8
  - `method` `Registry.__init__` — line 9
  - `method` `Registry.get` — line 14
  - `class` `Manager` — line 18
  - `method` `Manager.__init__` — line 19
  - `method` `Manager._dispatch` — line 24
  - `class` `Orch` — line 37
  - `method` `Orch.__init__` — line 38
  - `method` `Orch.run` — line 41
  - `function` `cfg` — line 46
  - `function` `message` — line 63
  - `function` `test_authorized_message_runs_orchestrator_and_redacts_reply` — line 75
  - `function` `test_unauthorized_and_bot_messages_never_run_or_reply` — line 91
  - `function` `test_empty_allowlist_fails_closed` — line 109
  - `function` `test_rate_limit_prevents_extra_model_calls` — line 119
  - `function` `test_disabled_bridge_does_not_touch_connector` — line 129
  - `function` `test_persisted_offset_is_used_after_restart` — line 136
  - `class` `Processes` — line 145
  - `method` `Processes.list` — line 146
  - `class` `Watches` — line 148
  - `method` `Watches.poll` — line 149
  - `method` `Watches.rebaseline` — line 150
  - `class` `Note` — line 152
  - `method` `Note.__init__` — line 153
  - `method` `Note.flush` — line 154
  - `method` `Note.send` — line 155
  - `method` `Note.is_quiet` — line 156
  - `class` `Bridge` — line 158
  - `method` `Bridge.__init__` — line 159
  - `method` `Bridge.poll_once` — line 160
  - `function` `test_daemon_polls_mobile_bridge_and_surfaces_error` — line 165
- imports:
  - `json`
  - `living_assistant.connectors.mobile_bridge`
  - `living_assistant.core.memory`
  - `living_assistant.system.daemon`

## `tests/test_onboarding.py`

- language: `py`
- size: 3037 bytes
- hash: `4b4fa64940f5`
- symbols:
  - `function` `seed_config` — line 10
  - `function` `test_onboarding_updates_workspace_model_voice_and_connector_without_secret` — line 17
  - `function` `test_onboarding_rejects_invalid_model_and_overbroad_connector_capability` — line 40
  - `function` `test_cli_exposes_onboard_command` — line 58
  - `function` `test_load_config_prefers_completed_user_config_when_no_explicit_path` — line 63
- imports:
  - `living_assistant.cli`
  - `living_assistant.connectors`
  - `living_assistant.system.onboarding`
  - `pathlib`
  - `typer.testing`
  - `yaml`

## `tests/test_orchestrator_limits.py`

- language: `py`
- size: 1980 bytes
- hash: `fdfdcd511422`
- symbols:
  - `class` `SequenceProvider` — line 7
  - `method` `SequenceProvider.__init__` — line 8
  - `method` `SequenceProvider.chat` — line 13
  - `class` `MM` — line 26
  - `method` `MM.__init__` — line 27
  - `method` `MM.lease` — line 28
  - `method` `MM.sleep` — line 29
  - `class` `Specialists` — line 32
  - `method` `Specialists.delegate` — line 33
  - `function` `noop` — line 36
  - `function` `test_configured_tool_step_limit_can_exceed_ten` — line 40
  - `function` `test_tool_step_limit_returns_explicit_user_message` — line 52
- imports:
  - `contextlib`
  - `living_assistant.orchestrator`
  - `living_assistant.tools.base`

## `tests/test_overlay.py`

- language: `py`
- size: 11503 bytes
- hash: `a6743639587d`
- symbols:
  - `class` `_FakeLabel` — line 10
  - `method` `_FakeLabel.__init__` — line 11
  - `method` `_FakeLabel.configure` — line 14
  - `function` `test_overlay_query_error_uses_customtkinter_text_color` — line 18
  - `function` `test_overlay_source_has_no_commented_out_import_stubs` — line 31
  - `function` `test_overlay_screen_analysis_route_uses_existing_desktop_controller` — line 40
  - `function` `test_overlay_screen_analysis_route_requires_auth` — line 63
  - `function` `test_overlay_registers_ctrl_space_global_hotkey_without_extra_dependency` — line 73
  - `function` `test_overlay_command_palette_reuses_existing_composer_and_centers_window` — line 99
  - `function` `test_overlay_ui10_has_scrollable_conversation_history_sidebar` — line 130
  - `function` `test_overlay_ui11_expand_collapse_uses_smooth_geometry_animation` — line 140
  - `function` `test_overlay_ui12_has_model_voice_and_focus_settings_controls` — line 150
  - `function` `test_overlay_ui12_runtime_settings_endpoints_reuse_existing_runtime` — line 162
  - `function` `test_overlay_ui13_has_drag_resize_grip_and_handlers` — line 204
  - `function` `test_overlay_ui13_resize_updates_persistent_expanded_geometry_with_bounds` — line 213
  - `function` `test_overlay_ui14_draws_pending_approval_badge_only_when_collapsed` — line 244
  - `function` `test_overlay_ui14_badge_count_is_bounded_and_redrawn` — line 275
  - `function` `test_overlay_ui14_polls_existing_authenticated_approvals_endpoint` — line 288
- imports:
  - `__future__`
  - `fastapi.testclient`
  - `living_assistant.overlay`
  - `types`

## `tests/test_packaged_config.py`

- language: `py`
- size: 1001 bytes
- hash: `69155c1dea10`
- symbols:
  - `function` `test_packaged_default_config_resource_exists` — line 6
  - `function` `test_installed_mode_uses_packaged_config_and_user_data` — line 12
  - `function` `test_assistant_config_env_override` — line 20
- imports:
  - `importlib`
  - `living_assistant.config`
  - `pathlib`

## `tests/test_peer_agents.py`

- language: `py`
- size: 5692 bytes
- hash: `8a6a6f07ae39`
- symbols:
  - `class` `FakeResponse` — line 11
  - `method` `FakeResponse.json` — line 13
  - `class` `FakeClient` — line 15
  - `method` `FakeClient.__init__` — line 16
  - `method` `FakeClient.post` — line 17
  - `function` `config` — line 21
  - `function` `test_discovered_peer_is_not_trusted_unless_allowlisted` — line 31
  - `function` `test_delegate_uses_only_trusted_peer_https_and_redacts_payload` — line 45
  - `function` `test_untrusted_peer_never_receives_token` — line 61
  - `function` `test_accept_delegation_requires_peer_token_and_is_tool_free` — line 72
  - `function` `test_peer_api_uses_separate_peer_auth` — line 82
  - `function` `test_runtime_registers_peer_tools_when_feature_disabled_by_default` — line 94
  - `function` `test_mdns_start_uses_zeroconf_browser_without_advertising_secret` — line 102
- imports:
  - `fastapi.testclient`
  - `httpx`
  - `living_assistant.system.peer_agents`
  - `os`
  - `sys`
  - `types`

## `tests/test_planning_runtime.py`

- language: `py`
- size: 2425 bytes
- hash: `6a46f37580e2`
- symbols:
  - `function` `test_planning_tools_form_a_working_dependency_dag` — line 7
  - `function` `test_planning_tools_expose_valid_ollama_function_schemas` — line 23
  - `function` `test_runtime_registers_planning_tools_and_exposes_shared_graph` — line 32
- imports:
  - `living_assistant.task_graph`
  - `living_assistant.tools.planning`
  - `pathlib`

## `tests/test_policy.py`

- language: `py`
- size: 1263 bytes
- hash: `b7a01557c197`
- symbols:
  - `function` `test_blocks_root_delete` — line 3
  - `function` `test_blocks_defender_disable` — line 6
  - `function` `test_sudo_needs_approval` — line 9
  - `function` `test_sql_read_only` — line 13
  - `function` `test_sql_comment_handling_cannot_hide_a_second_write_statement` — line 20
- imports:
  - `living_assistant.security_policy`

## `tests/test_project_process_env.py`

- language: `py`
- size: 724 bytes
- hash: `ccc89a94c415`
- symbols:
  - `function` `test_managed_process_receives_project_environment` — line 6
- imports:
  - `__future__`
  - `living_assistant.tools.shell`
  - `time`

## `tests/test_project_registry.py`

- language: `py`
- size: 1656 bytes
- hash: `a4819740fb8a`
- symbols:
  - `function` `test_v01_project_registry_migrates` — line 4
  - `function` `test_project_add_detects_start` — line 13
  - `function` `test_project_environment_is_stored_and_updateable` — line 22
  - `function` `test_project_environment_rejects_secret_like_values` — line 31
- imports:
  - `json`
  - `living_assistant.tools.projects`

## `tests/test_projects.py`

- language: `py`
- size: 280 bytes
- hash: `c6316074540d`
- symbols:
  - `function` `test_node_detect` — line 3
- imports:
  - `living_assistant.tools.projects`

## `tests/test_quiet_activity_suppression.py`

- language: `py`
- size: 1981 bytes
- hash: `4fca21d8995b`
- symbols:
  - `class` `Approval` — line 5
  - `method` `Approval.request` — line 6
  - `class` `Workspace` — line 10
  - `method` `Workspace.resolve` — line 11
  - `function` `test_browser_activity_is_blocked_before_network_or_playwright` — line 15
  - `function` `test_browser_status_and_cleanup_paths_are_not_trapped_by_quiet_mode` — line 30
  - `function` `test_desktop_sensitive_observation_is_blocked_before_capture_or_approval` — line 37
- imports:
  - `living_assistant.browser`
  - `living_assistant.desktop_intelligence`

## `tests/test_session_context_budget.py`

- language: `py`
- size: 1466 bytes
- hash: `5f1d143c53fb`
- symbols:
  - `class` `Provider` — line 7
  - `method` `Provider.chat` — line 8
  - `class` `MM` — line 11
  - `method` `MM.lease` — line 13
  - `method` `MM.sleep` — line 14
  - `class` `Specialists` — line 17
  - `method` `Specialists.delegate` — line 18
  - `function` `test_session_context_keeps_more_than_twelve_short_messages` — line 21
  - `function` `test_session_context_budget_prioritizes_newest_history` — line 32
- imports:
  - `contextlib`
  - `living_assistant.orchestrator`
  - `living_assistant.sessions`

## `tests/test_skills.py`

- language: `py`
- size: 1234 bytes
- hash: `c554f3cd7337`
- symbols:
  - `function` `test_skill_matching` — line 3
  - `function` `test_fresh_skill_registry_is_seeded_with_builtin_defaults` — line 10
  - `function` `test_existing_empty_skill_registry_is_respected` — line 19
  - `function` `test_default_skills_resource_is_packaged_source_data` — line 26
- imports:
  - `living_assistant.skills`

## `tests/test_ui01_react_vite_tailwind.py`

- language: `py`
- size: 1915 bytes
- hash: `5c925804021b`
- symbols:
  - `function` `test_ui01_has_react_vite_tailwind_project_structure` — line 10
  - `function` `test_ui01_react_app_has_multiple_pages_and_hash_navigation` — line 22
  - `function` `test_ui01_production_assets_are_local_only` — line 31
  - `function` `test_ui01_vendored_react_versions_match_declared_runtime` — line 40
- imports:
  - `__future__`
  - `json`
  - `pathlib`

## `tests/test_ui06_plotly.py`

- language: `py`
- size: 7172 bytes
- hash: `8ee179829e41`
- symbols:
  - `function` `test_ui06_uses_real_plotly_component_not_hand_drawn_svg_or_canvas` — line 18
  - `function` `test_ui06_plotly_version_is_exact_and_loader_is_same_origin_only` — line 31
  - `function` `test_ui06_dashboard_csp_is_local_only` — line 44
  - `function` `test_ui06_resource_samples_handle_cpu_ram_vram_and_partial_metrics` — line 58
  - `function` `test_ui06_chart_render_errors_are_contained` — line 107
  - `function` `test_ui06_chart_loader_and_vendor_build_are_packaged_source_assets` — line 116
  - `function` `test_ui06_vendor_build_copies_exact_pinned_plotly_and_license` — line 127
  - `function` `test_ui06_committed_plotly_runtime_is_verified` — line 154
  - `function` `test_ui06_packaged_dashboard_serves_plotly` — line 165
  - `function` `test_ui06_production_build_runs_vendor_and_css_before_vite` — line 175
- imports:
  - `__future__`
  - `base64`
  - `fastapi.testclient`
  - `hashlib`
  - `json`
  - `pathlib`
  - `shutil`
  - `subprocess`

## `tests/test_ui_chat_approvals.py`

- language: `py`
- size: 1997 bytes
- hash: `5f0a3c15eafe`
- symbols:
  - `function` `_app` — line 9
  - `function` `test_ui02_chat_renders_assistant_markdown_without_html_injection` — line 13
  - `function` `test_ui03_chat_uses_local_prism_syntax_highlighting` — line 21
  - `function` `test_ui04_chat_has_live_streaming_token_indicator` — line 32
  - `function` `test_ui05_approvals_use_non_blocking_toast_for_new_requests` — line 41
  - `function` `test_ui08_dashboard_uses_mobile_first_responsive_layout` — line 50
- imports:
  - `__future__`
  - `pathlib`

## `tests/test_v010_interaction.py`

- language: `py`
- size: 6456 bytes
- hash: `6937a12081de`
- symbols:
  - `class` `FakeProvider` — line 13
  - `method` `FakeProvider.__init__` — line 14
  - `method` `FakeProvider.chat_stream` — line 19
  - `method` `FakeProvider.unload` — line 24
  - `class` `NoPressure` — line 28
  - `method` `NoPressure.can_start_model` — line 29
  - `class` `DummySpecialists` — line 33
  - `method` `DummySpecialists.delegate` — line 34
  - `function` `_orchestrator` — line 38
  - `function` `test_event_bus_records_ordered_activity` — line 51
  - `function` `test_orchestrator_streams_tokens_and_final_without_bypassing_normal_context` — line 60
  - `function` `test_streaming_tool_call_runs_through_registered_tool_then_continues` — line 71
  - `function` `test_streaming_error_redacts_secret_like_values` — line 87
  - `function` `test_dashboard_is_bundled_and_no_longer_disabled_by_api_token` — line 99
  - `function` `test_chat_stream_api_emits_sse` — line 116
  - `function` `test_activity_endpoint_is_authenticated_like_other_local_data` — line 143
  - `function` `test_event_bus_persists_recent_activity_across_restart` — line 156
- imports:
  - `__future__`
  - `fastapi.testclient`
  - `living_assistant.event_bus`
  - `living_assistant.model_provider`
  - `living_assistant.orchestrator`
  - `living_assistant.tools.base`
  - `types`

## `tests/test_v011_voice_presence.py`

- language: `py`
- size: 9381 bytes
- hash: `41741a7def83`
- symbols:
  - `class` `AllowApproval` — line 12
  - `method` `AllowApproval.__init__` — line 13
  - `method` `AllowApproval.request` — line 14
  - `class` `DenyApproval` — line 19
  - `method` `DenyApproval.request` — line 20
  - `function` `cfg` — line 23
  - `class` `FakeStream` — line 51
  - `method` `FakeStream.__init__` — line 52
  - `method` `FakeStream.__enter__` — line 54
  - `method` `FakeStream.__exit__` — line 55
  - `method` `FakeStream.read` — line 56
  - `class` `FakeSD` — line 66
  - `method` `FakeSD.__init__` — line 67
  - `method` `FakeSD.RawInputStream` — line 68
  - `function` `test_hands_free_is_opt_in_and_lite_gated` — line 71
  - `function` `test_wake_word_detection_is_local_and_approval_gated` — line 78
  - `function` `test_wake_word_denial_never_opens_audio_device` — line 94
  - `function` `test_adaptive_vad_records_speech_then_stops_on_silence` — line 101
  - `function` `test_no_speech_does_not_write_audio` — line 114
  - `function` `test_barge_in_denial_falls_back_to_normal_tts` — line 123
  - `function` `test_status_does_not_import_heavy_voice_models` — line 139
  - `function` `test_wake_and_command_capture_keeps_single_stream_audio` — line 147
  - `function` `test_clean_command_text_only_strips_leading_wake_phrase` — line 166
  - `function` `test_wake_command_preapproval_replay_uses_identical_action_hash` — line 174
- imports:
  - `living_assistant.approval`
  - `living_assistant.voice`
  - `living_assistant.workspace`
  - `numpy`
  - `pathlib`
  - `sys`
  - `types`

## `tests/test_v012_connectors.py`

- language: `py`
- size: 9510 bytes
- hash: `bd933a8084b9`
- symbols:
  - `class` `Approval` — line 12
  - `method` `Approval.__init__` — line 13
  - `method` `Approval.request` — line 15
  - `function` `registry` — line 20
  - `function` `test_registry_rejects_secret_settings` — line 24
  - `function` `test_credentials_never_return_secret_values` — line 34
  - `function` `test_read_connector_wraps_external_data` — line 42
  - `function` `test_write_requires_approval_and_does_not_store_body` — line 56
  - `function` `test_approved_write_calls_provider` — line 68
  - `function` `test_capability_gate_blocks_unregistered_action` — line 81
  - `function` `test_google_oauth_url_uses_pkce_and_no_client_secret` — line 89
  - `function` `test_microsoft_device_begin_uses_official_endpoint` — line 99
  - `function` `test_github_device_begin_uses_device_endpoint` — line 112
  - `function` `test_obsidian_cannot_escape_vault` — line 122
  - `function` `test_disabled_connector_cannot_call` — line 133
  - `function` `test_connector_api_routes_use_same_manager` — line 139
  - `function` `test_connector_refreshes_oauth_token_well_before_expiry` — line 155
  - `function` `test_connector_keeps_token_outside_refresh_safety_window` — line 175
- imports:
  - `httpx`
  - `json`
  - `living_assistant.connector_credentials`
  - `living_assistant.connector_oauth`
  - `living_assistant.connectors`
  - `pathlib`
  - `pytest`

## `tests/test_v013_model_runtime.py`

- language: `py`
- size: 13200 bytes
- hash: `8a537a30d77d`
- symbols:
  - `function` `hw` — line 12
  - `function` `cfg` — line 21
  - `function` `test_4gb_gpu_stays_single_model` — line 43
  - `function` `test_16gb_gpu_enables_two_models` — line 50
  - `function` `test_24gb_gpu_enables_three_models` — line 57
  - `function` `test_apple_unified_memory_thresholds` — line 63
  - `function` `test_lite_profile_always_single_in_auto_mode` — line 68
  - `function` `test_explicit_single_overrides_high_end_hardware` — line 73
  - `class` `FakeResources` — line 80
  - `method` `FakeResources.can_admit_model` — line 85
  - `method` `FakeResources.can_start_model` — line 90
  - `method` `FakeResources.thermal_pressure` — line 93
  - `class` `FakeProvider` — line 97
  - `method` `FakeProvider.__init__` — line 98
  - `method` `FakeProvider.model_size_bytes` — line 103
  - `method` `FakeProvider.unload` — line 106
  - `method` `FakeProvider.preload` — line 109
  - `method` `FakeProvider.running_models` — line 113
  - `function` `policy` — line 117
  - `function` `test_single_mode_evicts_previous_model` — line 131
  - `function` `test_multi_mode_keeps_two_and_lru_evicts` — line 140
  - `function` `test_pressure_evicts_idle_model_even_before_count_limit` — line 151
  - `function` `test_preload_uses_long_resident_keep_alive` — line 160
  - `function` `test_distinct_models_can_hold_generation_leases_concurrently` — line 168
  - `function` `test_same_model_is_serialized_when_parallel_per_model_is_one` — line 192
  - `function` `test_status_can_sync_provider_running_models` — line 219
  - `function` `test_thermal_pressure_serializes_otherwise_parallel_models` — line 229
  - `function` `test_resource_thermal_guard_blocks_additional_residency` — line 257
  - `function` `test_model_runtime_api_status_and_controls` — line 268
  - `function` `test_combined_model_sizes_respect_total_vram_budget` — line 307
  - `function` `test_lower_priority_background_model_cannot_evict_foreground_model` — line 320
  - `function` `test_higher_priority_foreground_model_evicts_lower_priority_background_model` — line 337
  - `function` `test_can_start_model_rejects_known_model_that_would_force_cpu_fallback` — line 346
  - `function` `test_can_start_model_blocks_when_only_reserved_vram_remains` — line 358
- imports:
  - `__future__`
  - `dataclasses`
  - `living_assistant.hardware`
  - `living_assistant.model_provider`
  - `living_assistant.resource_manager`
  - `threading`
  - `time`
  - `types`

## `tests/test_v014_desktop_intelligence.py`

- language: `py`
- size: 3955 bytes
- hash: `b26cab3e473a`
- symbols:
  - `class` `Approval` — line 9
  - `method` `Approval.__init__` — line 10
  - `method` `Approval.request` — line 11
  - `class` `Workspace` — line 14
  - `method` `Workspace.__init__` — line 15
  - `method` `Workspace.resolve` — line 16
  - `class` `Provider` — line 21
  - `method` `Provider.chat` — line 23
  - `class` `Lease` — line 25
  - `method` `Lease.__enter__` — line 26
  - `method` `Lease.__exit__` — line 27
  - `class` `MM` — line 28
  - `method` `MM.lease` — line 29
  - `function` `controller` — line 32
  - `function` `test_status_is_non_invasive` — line 37
  - `function` `test_accessibility_requires_approval` — line 44
  - `function` `test_click_denied_before_pyautogui_import` — line 51
  - `function` `test_type_length_guard` — line 57
  - `function` `test_hotkey_empty_rejected` — line 64
  - `function` `test_vision_disabled_by_default` — line 69
  - `function` `test_remote_vision_blocked` — line 75
  - `function` `test_remote_vision_can_be_explicitly_allowed_but_still_needs_approval` — line 82
  - `function` `test_desktop_tools_expose_semantic_first_controls` — line 89
  - `function` `test_monitor_ids_are_validated_without_capture` — line 96
  - `function` `test_tool_order_documents_preference` — line 109
- imports:
  - `living_assistant.desktop_intelligence`
  - `living_assistant.tools.desktop`
  - `pathlib`
  - `pytest`
  - `types`

## `tests/test_v015_security_sensors.py`

- language: `py`
- size: 11720 bytes
- hash: `7f975f9010cd`
- symbols:
  - `class` `AllowApproval` — line 12
  - `method` `AllowApproval.request` — line 13
  - `class` `DenyApproval` — line 15
  - `method` `DenyApproval.request` — line 16
  - `class` `GuardianStub` — line 18
  - `method` `GuardianStub.__init__` — line 19
  - `method` `GuardianStub.record_finding` — line 20
  - `method` `GuardianStub.findings` — line 23
  - `function` `platform` — line 26
  - `function` `test_sysmon_dns_normalization` — line 33
  - `function` `test_windows_security_4688_normalization` — line 38
  - `function` `test_event_correlation_office_powershell_network` — line 43
  - `function` `test_auditd_parser_groups_records` — line 54
  - `function` `test_dns_algorithmic_heuristic` — line 60
  - `function` `test_ransomware_burst_detector` — line 66
  - `function` `test_tls_context_reads_only_configured_jsonl` — line 75
  - `function` `test_dns_context_accepts_local_collector` — line 82
  - `function` `test_yara_scan_requires_approval` — line 90
  - `function` `test_usb_baseline_new_device` — line 98
  - `function` `test_extension_permission_change` — line 106
  - `function` `test_backup_integrity_detects_removed_file` — line 116
  - `function` `test_binary_trust_detects_hash_change` — line 125
  - `function` `test_reputation_missing_key_does_not_upload` — line 134
  - `function` `test_reputation_records_high_confidence_malicious_hash` — line 141
  - `function` `test_automatic_isolation_disabled_by_default` — line 157
  - `function` `test_automatic_isolation_requires_independent_signals` — line 163
  - `function` `test_network_isolation_and_restore_are_reversible` — line 169
  - `function` `test_periodic_extension_permission_finding` — line 179
  - `function` `test_native_macos_helper_source_is_shipped` — line 190
  - `function` `test_security_sensor_api_status` — line 194
  - `function` `test_dashboard_surfaces_sensor_platform` — line 206
  - `function` `test_partial_network_isolation_keeps_restore_state` — line 221
  - `function` `test_security_tools_include_sensor_controls` — line 234
- imports:
  - `__future__`
  - `json`
  - `living_assistant.security_sensors`
  - `pathlib`
  - `pytest`

## `tests/test_v016_platform_hardening.py`

- language: `py`
- size: 9128 bytes
- hash: `b1907597abb2`
- symbols:
  - `function` `test_portable_link_prefers_symlink` — line 18
  - `function` `test_file_link_falls_back_to_hardlink` — line 27
  - `function` `test_windows_directory_uses_junction_fallback` — line 38
  - `function` `test_copy_fallback_is_never_implicit` — line 52
  - `function` `test_sleep_resume_monitor_detects_large_gap` — line 64
  - `function` `test_watch_rebaseline_suppresses_resume_churn` — line 74
  - `function` `test_workspace_listing_survives_broken_symlink` — line 86
  - `function` `test_link_probe_leaves_no_persistent_artifact` — line 100
  - `function` `test_platform_status_is_serializable` — line 108
  - `function` `test_service_installers_use_current_safe_patterns` — line 115
  - `function` `test_windows_bootstrap_does_not_require_activation_script` — line 125
  - `function` `test_windows_private_createjunction_argument_order` — line 132
  - `function` `test_api_exposes_platform_status` — line 144
  - `function` `test_api_health_reports_current_package_version` — line 158
  - `function` `test_daemon_resume_revalidates_ephemeral_state` — line 167
  - `function` `test_tree_walker_does_not_descend_link_like_directory` — line 202
  - `function` `test_integrity_snapshot_does_not_follow_directory_symlink` — line 215
- imports:
  - `__future__`
  - `living_assistant.platform_hardening`
  - `living_assistant.watchers`
  - `living_assistant.workspace`
  - `os`
  - `pathlib`
  - `platform`
  - `pytest`

## `tests/test_v0171_audit_fixes.py`

- language: `py`
- size: 5749 bytes
- hash: `9f670662987d`
- symbols:
  - `function` `_tools` — line 11
  - `class` `FakeBrowser` — line 15
  - `method` `FakeBrowser.__init__` — line 16
  - `method` `FakeBrowser.search_web` — line 20
  - `method` `FakeBrowser.search_images` — line 26
  - `function` `test_auto_search_does_not_require_serper_key` — line 33
  - `function` `test_browser_provider_supports_image_search_without_serper` — line 46
  - `function` `test_explicit_serper_provider_still_requires_key` — line 56
  - `function` `test_search_budget_blocks_runaway_calls` — line 65
  - `function` `test_strict_browser_route_guard_blocks_unlisted_public_hosts` — line 74
  - `function` `test_browser_session_limit_is_enforced_before_launch` — line 99
  - `function` `test_release_install_scripts_enforce_checksum_manifest` — line 110
  - `function` `test_generated_api_token_is_persistent_and_private` — line 118
- imports:
  - `__future__`
  - `living_assistant.approval`
  - `living_assistant.browser`
  - `living_assistant.tools.webtools`
  - `living_assistant.workspace`
  - `pathlib`

## `tests/test_v0172_security_regressions.py`

- language: `py`
- size: 11770 bytes
- hash: `0710e1b8c26a`
- symbols:
  - `function` `_handlers` — line 26
  - `function` `_git` — line 30
  - `function` `_manager` — line 36
  - `function` `test_git_rejects_parent_repository_outside_workspace` — line 40
  - `function` `test_git_sensitive_diff_requires_approval_and_redacts_provider_tokens` — line 54
  - `function` `test_api_auth_fails_closed_and_generated_token_works` — line 73
  - `function` `test_shell_timeout_kills_descendants` — line 90
  - `function` `test_self_improvement_refuses_sensitive_targets` — line 122
  - `function` `test_connector_settings_reject_secret_values_even_under_benign_keys` — line 130
  - `function` `test_device_oauth_does_not_return_raw_device_code` — line 136
  - `function` `test_desktop_window_titles_are_opt_in_and_approval_gated` — line 156
  - `function` `test_database_alias_policy_blocks_unknown_tables_and_redacts_columns` — line 169
  - `function` `test_redaction_catches_provider_tokens_without_secret_key_name` — line 190
  - `function` `test_browser_dns_pin_reuses_single_validated_resolution` — line 196
  - `function` `test_strict_browser_route_guard_does_not_reresolve_dns` — line 218
  - `function` `test_browser_fixed_public_dependency_rejects_private_dns` — line 247
- imports:
  - `__future__`
  - `fastapi.testclient`
  - `living_assistant.approval`
  - `living_assistant.connector_credentials`
  - `living_assistant.connectors`
  - `living_assistant.desktop_intelligence`
  - `living_assistant.improvements`
  - `living_assistant.security_utils`
  - `living_assistant.tools.database`
  - `living_assistant.tools.gittools`
  - `living_assistant.tools.shell`
  - `living_assistant.workspace`
  - `os`
  - `pathlib`
  - `psutil`
  - `pytest`
  - `sqlite3`
  - `subprocess`
  - `time`
  - `types`

## `tests/test_v0173_shell_output.py`

- language: `py`
- size: 1097 bytes
- hash: `e881afcc1b6d`
- symbols:
  - `function` `test_run_command_bounds_model_visible_output_without_buffering_capture` — line 6
- imports:
  - `living_assistant.approval`
  - `living_assistant.tools.shell`
  - `living_assistant.workspace`

## `tests/test_v0173_specialist_timeout.py`

- language: `py`
- size: 958 bytes
- hash: `f80145e26365`
- symbols:
  - `class` `SlowProvider` — line 6
  - `method` `SlowProvider.chat` — line 7
  - `class` `FakeManager` — line 12
  - `method` `FakeManager.__init__` — line 14
  - `method` `FakeManager.activate` — line 16
  - `function` `test_specialist_delegate_returns_on_timeout_instead_of_hanging` — line 20
- imports:
  - `living_assistant.agents`
  - `time`

## `tests/test_v0173_voice_tools.py`

- language: `py`
- size: 1132 bytes
- hash: `645869a7ca86`
- symbols:
  - `function` `test_one_shot_voice_tools_remain_available_when_voice_mode_disabled` — line 7
- imports:
  - `living_assistant.approval`
  - `living_assistant.tools.voicetools`
  - `living_assistant.voice`
  - `living_assistant.workspace`

## `tests/test_v017_release_packaging.py`

- language: `py`
- size: 6453 bytes
- hash: `fda93eb8bce5`
- symbols:
  - `function` `_fake_installed_version` — line 15
  - `function` `_minimal_wheel` — line 25
  - `function` `test_release_status_is_read_only` — line 33
  - `function` `test_data_schema_migration_is_idempotent` — line 41
  - `function` `test_backup_uses_sqlite_snapshot_and_excludes_browser_cache` — line 49
  - `function` `test_foreign_wheel_is_rejected` — line 67
  - `function` `test_checksum_mismatch_rejected_before_install` — line 74
  - `function` `test_rollback_swaps_stable_shim` — line 82
  - `function` `test_remove_active_version_is_refused` — line 96
  - `function` `test_uninstall_purge_requires_confirmation_before_removing_runtime` — line 102
  - `function` `test_release_scripts_use_versioned_runtime_shims` — line 110
  - `function` `test_api_health_reports_v017` — line 122
  - `function` `test_release_verify_checks_active_runtime` — line 130
- imports:
  - `__future__`
  - `hashlib`
  - `json`
  - `living_assistant.release_manager`
  - `os`
  - `pathlib`
  - `pytest`
  - `sqlite3`
  - `zipfile`

## `tests/test_v03_browser.py`

- language: `py`
- size: 300 bytes
- hash: `f522fc430054`
- symbols:
  - `function` `test_browser_url_policy` — line 4
- imports:
  - `living_assistant.browser`

## `tests/test_v03_desktop_approval.py`

- language: `py`
- size: 634 bytes
- hash: `279deccd4a01`
- symbols:
  - `function` `test_clipboard_read_noninteractive_queues_approval` — line 6
- imports:
  - `living_assistant.approval`
  - `living_assistant.tools.desktop`
  - `living_assistant.workspace`

## `tests/test_v03_filesystem_diff.py`

- language: `py`
- size: 901 bytes
- hash: `b76358c0aeab`
- symbols:
  - `function` `get_tool` — line 5
  - `function` `test_preview_write_diff` — line 9
  - `function` `test_write_returns_diff` — line 20
- imports:
  - `living_assistant.tools.filesystem`
  - `living_assistant.workspace`

## `tests/test_v03_groups.py`

- language: `py`
- size: 1455 bytes
- hash: `724a57526a9f`
- symbols:
  - `class` `Projects` — line 4
  - `method` `Projects.__init__` — line 5
  - `method` `Projects.get` — line 6
  - `class` `Processes` — line 13
  - `method` `Processes.list` — line 14
  - `method` `Processes.stop` — line 15
  - `function` `test_group_plan` — line 18
  - `function` `test_group_unknown_project` — line 28
- imports:
  - `living_assistant.approval`
  - `living_assistant.groups`

## `tests/test_v03_quarantine.py`

- language: `py`
- size: 762 bytes
- hash: `439ec1d6cacf`
- symbols:
  - `function` `test_risky_download_detection` — line 5
  - `function` `test_quarantine_register` — line 11
- imports:
  - `living_assistant.quarantine`
  - `pathlib`

## `tests/test_v04_approval_notify.py`

- language: `py`
- size: 529 bytes
- hash: `7fca6524d12e`
- symbols:
  - `class` `Notifier` — line 3
  - `method` `Notifier.__init__` — line 4
  - `method` `Notifier.send` — line 5
  - `function` `test_noninteractive_approval_notifies` — line 8
- imports:
  - `living_assistant.approval`

## `tests/test_v04_browser_scope.py`

- language: `py`
- size: 410 bytes
- hash: `f708185d7de7`
- symbols:
  - `function` `test_metadata_blocked_and_local_allowed` — line 4
  - `function` `test_session_name_sanitized` — line 10
- imports:
  - `living_assistant.browser`

## `tests/test_v04_improvements.py`

- language: `py`
- size: 2680 bytes
- hash: `275bfb2296b7`
- symbols:
  - `function` `build` — line 6
  - `function` `test_proposal_requires_approval_then_applies` — line 14
  - `function` `test_conflict_and_protected_core` — line 27
  - `function` `test_rollback_requires_approval_and_restores` — line 39
  - `function` `test_rollback_refuses_to_overwrite_post_apply_edit` — line 50
- imports:
  - `living_assistant.approval`
  - `living_assistant.improvements`
  - `living_assistant.workspace`

## `tests/test_v04_routines.py`

- language: `py`
- size: 1464 bytes
- hash: `31ac0e9c4a7c`
- symbols:
  - `class` `Memory` — line 3
  - `method` `Memory.__init__` — line 4
  - `method` `Memory.add_todo` — line 5
  - `class` `Notifier` — line 6
  - `method` `Notifier.__init__` — line 7
  - `method` `Notifier.send` — line 8
  - `function` `test_interval_routine_runs_once_inside_window` — line 11
  - `function` `test_event_routine_and_prompt_gate` — line 21
- imports:
  - `living_assistant.routines`

## `tests/test_v04_voice.py`

- language: `py`
- size: 650 bytes
- hash: `6aa9c1c492b3`
- symbols:
  - `class` `Approval` — line 4
  - `method` `Approval.request` — line 5
  - `function` `test_voice_profile_gate` — line 8
  - `function` `test_disabled_record_does_not_need_audio_dependencies` — line 15
- imports:
  - `living_assistant.voice`
  - `living_assistant.workspace`

## `tests/test_v05_briefing.py`

- language: `py`
- size: 3374 bytes
- hash: `1094529d51fc`
- symbols:
  - `class` `EmptyProjects` — line 7
  - `method` `EmptyProjects.list` — line 8
  - `class` `EmptyProcesses` — line 9
  - `method` `EmptyProcesses.list` — line 10
  - `class` `EmptyApprovals` — line 11
  - `method` `EmptyApprovals.list` — line 12
  - `class` `Note` — line 13
  - `method` `Note.__init__` — line 14
  - `method` `Note.send` — line 15
  - `function` `test_briefing_build_and_schedule_once` — line 18
  - `function` `test_briefing_build_uses_bounded_same_day_cache` — line 32
  - `function` `test_briefing_includes_bounded_security_and_experience_context` — line 53
- imports:
  - `datetime`
  - `living_assistant.briefing`
  - `living_assistant.calendar_store`
  - `living_assistant.memory`
  - `living_assistant.personal_state`

## `tests/test_v05_calendar.py`

- language: `py`
- size: 647 bytes
- hash: `01705b341fd0`
- symbols:
  - `function` `test_calendar_add_range_cancel_and_export` — line 4
- imports:
  - `living_assistant.calendar_store`

## `tests/test_v05_connectors.py`

- language: `py`
- size: 434 bytes
- hash: `daa2c696b606`
- symbols:
  - `function` `test_connector_registry_stores_metadata_not_secret` — line 4
- imports:
  - `living_assistant.connectors`

## `tests/test_v05_notifications.py`

- language: `py`
- size: 1696 bytes
- hash: `8949b0daaca8`
- symbols:
  - `function` `test_quiet_notifications_queue_and_flush` — line 4
  - `function` `test_windows_notification_uses_powershell_toast_backend` — line 16
- imports:
  - `living_assistant.notifications`

## `tests/test_v05_personal_state.py`

- language: `py`
- size: 674 bytes
- hash: `62594e052246`
- symbols:
  - `function` `test_quiet_hours_wrap_midnight` — line 5
  - `function` `test_focus_expires` — line 13
- imports:
  - `datetime`
  - `living_assistant.personal_state`

## `tests/test_v05_routine_clock.py`

- language: `py`
- size: 1250 bytes
- hash: `ef60d0a92641`
- symbols:
  - `class` `Memory` — line 4
  - `method` `Memory.__init__` — line 5
  - `method` `Memory.add_todo` — line 6
  - `class` `Notifier` — line 7
  - `method` `Notifier.__init__` — line 8
  - `method` `Notifier.send` — line 9
  - `function` `ts` — line 11
  - `function` `test_daily_clock_routine_once_per_day` — line 13
  - `function` `test_weekly_clock_routine_days` — line 21
- imports:
  - `datetime`
  - `living_assistant.routines`

## `tests/test_v05_sessions.py`

- language: `py`
- size: 3368 bytes
- hash: `93250651d644`
- symbols:
  - `function` `test_session_history_search_and_delete` — line 5
  - `function` `test_session_prune` — line 16
  - `function` `test_session_redacts_common_secrets` — line 31
  - `function` `test_session_search_rebuilds_fts_for_existing_database` — line 39
  - `function` `test_session_prune_does_not_delete_when_archive_write_fails` — line 66
- imports:
  - `datetime`
  - `living_assistant.sessions`

## `tests/test_v06_quarantine_provenance.py`

- language: `py`
- size: 1852 bytes
- hash: `735a8ca7101b`
- symbols:
  - `function` `test_quarantine_tracks_origin_hash_and_risk` — line 4
  - `function` `test_download_risk_reasons_explain_why` — line 18
  - `function` `test_quarantine_drops_signed_url_query` — line 23
  - `function` `test_quarantine_verify_detects_post_registration_tampering` — line 32
- imports:
  - `living_assistant.quarantine`

## `tests/test_v06_security_guardian.py`

- language: `py`
- size: 7215 bytes
- hash: `6da6bc5665a9`
- symbols:
  - `function` `guardian` — line 8
  - `function` `test_integrity_baseline_detects_change` — line 12
  - `function` `test_network_baseline_initializes_and_deduplicates_findings` — line 24
  - `function` `test_resolved_finding_reopens_as_new_signal` — line 44
  - `function` `test_process_inspection_current_process_is_bounded` — line 53
  - `function` `test_posture_evaluator_only_flags_explicit_disabled_states` — line 63
  - `function` `test_posture_evaluator_does_not_treat_unknown_tool_as_compromise` — line 76
  - `function` `test_process_scoring_flags_temp_listener` — line 83
  - `function` `test_process_scoring_flags_office_spawned_script_host` — line 90
  - `function` `test_security_persistence_redacts_secrets_before_storage` — line 99
  - `function` `test_missing_baseline_is_not_silently_trusted` — line 107
  - `function` `test_capturing_baseline_resolves_setup_finding` — line 115
  - `function` `test_integrity_baseline_does_not_hash_symlink_target` — line 124
  - `function` `test_security_guardian_core_is_self_improvement_protected` — line 142
- imports:
  - `living_assistant.security_guardian`
  - `os`
  - `pathlib`
  - `pytest`

## `tests/test_v07_evaluation.py`

- language: `py`
- size: 12634 bytes
- hash: `4ffb59439219`
- symbols:
  - `function` `build` — line 13
  - `function` `approve_and_retry` — line 31
  - `function` `git` — line 37
  - `function` `init_git` — line 43
  - `function` `test_suite_roundtrip` — line 49
  - `function` `test_copy_evaluation_passes_without_modifying_source` — line 58
  - `function` `test_failed_candidate_is_not_promotable` — line 70
  - `function` `test_benchmark_comparison_enforces_budgets` — line 82
  - `function` `test_unsafe_evaluation_command_rejected_before_approval` — line 91
  - `function` `test_measure_command_is_time_bounded` — line 101
  - `function` `test_git_evaluation_and_promotion_are_separate_approved_steps` — line 107
  - `function` `test_git_promotion_refuses_stale_head` — line 128
  - `function` `test_git_evaluation_refuses_dirty_source` — line 141
  - `function` `test_protected_core_can_be_measured_but_not_auto_promoted` — line 153
  - `function` `test_git_promotion_can_be_reverted_without_history_rewrite` — line 170
  - `function` `test_promotion_refuses_branch_tip_tampering` — line 185
  - `function` `test_profile_adaptive_benchmark_defaults` — line 200
  - `function` `test_evaluation_does_not_execute_shell_chaining` — line 213
- imports:
  - `__future__`
  - `living_assistant.approval`
  - `living_assistant.evaluation`
  - `living_assistant.improvements`
  - `living_assistant.workspace`
  - `pathlib`
  - `pytest`
  - `subprocess`

## `tests/test_v08_hardened_canary.py`

- language: `py`
- size: 10474 bytes
- hash: `a5cefb864ddc`
- symbols:
  - `function` `approve_and_retry` — line 13
  - `function` `base_stack` — line 19
  - `function` `git` — line 37
  - `function` `test_sandbox_argv_drops_privilege_and_binds_localhost` — line 43
  - `function` `test_container_suite_roundtrip_and_mocked_evaluation` — line 58
  - `function` `test_canary_comparison_enforces_health_and_budgets` — line 79
  - `function` `test_promotion_requires_exact_passing_canary_when_suite_demands_it` — line 88
  - `function` `test_canary_run_records_paired_measurement_without_promoting` — line 107
  - `function` `test_lite_profile_rejects_container_by_default` — line 128
  - `function` `test_real_host_canary_excludes_startup_failures_from_health_window` — line 136
  - `function` `test_evaluation_subprocess_redacts_common_secret_environment` — line 146
  - `function` `test_host_canary_timeout_terminates_descendant_processes` — line 155
- imports:
  - `__future__`
  - `living_assistant.approval`
  - `living_assistant.canary`
  - `living_assistant.evaluation`
  - `living_assistant.improvements`
  - `living_assistant.sandbox`
  - `living_assistant.workspace`
  - `pathlib`
  - `subprocess`

## `tests/test_v092_security_hardening.py`

- language: `py`
- size: 9128 bytes
- hash: `37d5e96883cc`
- symbols:
  - `function` `_tools` — line 22
  - `function` `test_shell_read_exemption_cannot_be_chained` — line 26
  - `function` `test_sql_read_only_rejects_multi_statement_and_side_effects` — line 34
  - `function` `test_sqlite_query_tool_enforces_read_only` — line 44
  - `function` `test_database_errors_redact_dsn_password` — line 59
  - `function` `test_sensitive_file_read_needs_one_time_approval_and_search_skips_content` — line 71
  - `function` `test_sensitive_preview_does_not_expose_old_secret_before_approval` — line 89
  - `function` `test_one_time_approval_is_atomic_under_concurrency` — line 99
  - `function` `test_thread_local_sqlite_store_survives_concurrent_writes` — line 110
  - `function` `test_remote_ollama_is_opt_in_and_insecure_remote_is_separate_opt_in` — line 122
  - `function` `test_redactor_covers_database_uri_bearer_and_private_key` — line 132
  - `function` `test_private_network_scope_and_metadata_are_not_public` — line 138
  - `function` `test_project_health_url_must_be_loopback` — line 144
  - `function` `test_macos_notification_text_is_not_interpolated_into_applescript` — line 153
  - `function` `test_repeated_recovery_context_excludes_raw_tool_output` — line 171
  - `function` `test_local_api_rejects_bad_host_and_cross_origin` — line 187
- imports:
  - `__future__`
  - `concurrent.futures`
  - `living_assistant.approval`
  - `living_assistant.browser`
  - `living_assistant.experience`
  - `living_assistant.memory`
  - `living_assistant.model_provider`
  - `living_assistant.notifications`
  - `living_assistant.security_policy`
  - `living_assistant.security_utils`
  - `living_assistant.tools.database`
  - `living_assistant.tools.filesystem`
  - `living_assistant.tools.projects`
  - `living_assistant.workspace`
  - `pathlib`
  - `pytest`
  - `sqlite3`

## `tests/test_v09_experience.py`

- language: `py`
- size: 10176 bytes
- hash: `c2a855d839e9`
- symbols:
  - `function` `engine` — line 6
  - `function` `recovery_trace` — line 18
  - `function` `test_automatic_recovery_is_candidate_first_then_promotes_after_repeat` — line 25
  - `function` `test_verified_postmortem_is_immediately_retrievable` — line 37
  - `function` `test_user_confirmation_makes_lesson_high_confidence` — line 47
  - `function` `test_negative_verification_reduces_confidence_and_can_demote` — line 57
  - `function` `test_stale_unconfirmed_lesson_decays_but_confirmed_lesson_has_longer_memory` — line 67
  - `function` `test_conflicting_procedures_are_marked_and_context_warns` — line 78
  - `function` `test_superseded_lesson_is_not_retrieved` — line 88
  - `function` `test_episode_and_lesson_storage_redacts_secrets` — line 97
  - `function` `test_episode_maintenance_prunes_old_traces_not_lessons` — line 109
  - `function` `test_search_is_project_and_query_sensitive` — line 120
  - `function` `test_stats_distinguish_trusted_lessons_from_episodes` — line 128
  - `function` `test_failure_patterns_cluster_repeated_recent_errors` — line 136
  - `function` `test_maintenance_demotes_and_expires_stale_lessons` — line 146
  - `function` `test_maintenance_demotes_active_lesson_before_expiry` — line 168
  - `function` `test_daemon_runs_experience_confidence_maintenance` — line 183
- imports:
  - `__future__`
  - `datetime`
  - `living_assistant.experience`

## `tests/test_v09_orchestrator_learning.py`

- language: `py`
- size: 2192 bytes
- hash: `40839a26b15c`
- symbols:
  - `class` `FakeProvider` — line 6
  - `method` `FakeProvider.__init__` — line 7
  - `method` `FakeProvider.chat` — line 9
  - `class` `FakeMM` — line 18
  - `method` `FakeMM.__init__` — line 19
  - `method` `FakeMM.activate` — line 20
  - `method` `FakeMM.sleep` — line 21
  - `class` `DummySpecialists` — line 23
  - `method` `DummySpecialists.delegate` — line 24
  - `function` `test_orchestrator_auto_learns_repeated_recovery_and_retrieves_it` — line 27
- imports:
  - `__future__`
  - `living_assistant.experience`
  - `living_assistant.orchestrator`
  - `living_assistant.tools.base`

## `tests/test_watchers.py`

- language: `py`
- size: 1142 bytes
- hash: `d87ef57ef20f`
- symbols:
  - `function` `test_watcher_detects_change` — line 4
  - `function` `test_watcher_batches_large_change_bursts` — line 16
- imports:
  - `living_assistant.watchers`
  - `os`
  - `time`

## `tests/test_webtools_image_download.py`

- language: `py`
- size: 3273 bytes
- hash: `111edf431d85`
- symbols:
  - `class` `_Response` — line 10
  - `method` `_Response.__init__` — line 15
  - `method` `_Response.raise_for_status` — line 19
  - `method` `_Response.iter_bytes` — line 22
  - `method` `_Response.close` — line 25
  - `class` `_Client` — line 29
  - `method` `_Client.__init__` — line 32
  - `method` `_Client.__enter__` — line 35
  - `method` `_Client.__exit__` — line 38
  - `method` `_Client.build_request` — line 41
  - `method` `_Client.send` — line 44
  - `function` `_tools` — line 48
  - `function` `test_download_image_infers_extension` — line 59
  - `function` `test_download_image_rejects_non_image_response` — line 67
  - `function` `test_download_image_rejects_mismatched_extension` — line 74
  - `function` `test_download_image_quarantines_svg` — line 81
  - `function` `test_generic_download_url_remains_available` — line 88
- imports:
  - `__future__`
  - `living_assistant.tools.webtools`
  - `living_assistant.workspace`
  - `pathlib`

## `tests/test_webui.py`

- language: `py`
- size: 2508 bytes
- hash: `7ab309af5de7`
- symbols:
  - `function` `_dashboard_source` — line 9
  - `function` `_app_source` — line 17
  - `function` `test_dashboard_webui_has_safe_markdown_and_prism_pipeline` — line 25
  - `function` `test_dashboard_webui_surfaces_request_errors_to_the_user` — line 36
  - `function` `test_dashboard_route_serves_hardened_local_ui` — line 43
  - `function` `test_webui_is_declared_as_package_data` — line 72
- imports:
  - `__future__`
  - `fastapi.testclient`
  - `importlib`
  - `pathlib`

## `tests/test_windows_eventlog_daemon_wiring.py`

- language: `py`
- size: 2813 bytes
- hash: `4bd63b7eb0bf`
- symbols:
  - `class` `Guardian` — line 7
  - `method` `Guardian.__init__` — line 8
  - `method` `Guardian.record_finding` — line 9
  - `method` `Guardian.findings` — line 12
  - `class` `Processes` — line 15
  - `method` `Processes.list` — line 16
  - `class` `Watches` — line 19
  - `method` `Watches.poll` — line 20
  - `method` `Watches.rebaseline` — line 21
  - `class` `Note` — line 24
  - `method` `Note.flush` — line 25
  - `method` `Note.send` — line 26
  - `method` `Note.is_quiet` — line 27
  - `function` `_windows_events` — line 30
  - `function` `test_periodic_scan_uses_windows_eventlog_collector` — line 38
  - `function` `test_daemon_invokes_security_sensor_periodic_scan` — line 48
- imports:
  - `living_assistant.daemon`
  - `living_assistant.memory`
  - `living_assistant.security_sensors`

## `tests/test_workspace.py`

- language: `py`
- size: 435 bytes
- hash: `1b8bc9cd5c0d`
- symbols:
  - `function` `test_workspace_rejects_escape` — line 5
  - `function` `test_workspace_write` — line 10
- imports:
  - `living_assistant.workspace`
  - `pathlib`
  - `pytest`

