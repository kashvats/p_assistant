import importlib


def test_domain_packages_own_representative_implementations_and_legacy_aliases_match():
    pairs = {
        'runtime': 'core.runtime',
        'orchestrator': 'agents.orchestrator',
        'security_sensors': 'security.security_sensors',
        'evaluation': 'learning.evaluation',
        'connector_oauth': 'connectors.connector_oauth',
        'browser': 'desktop.browser',
        'daemon': 'system.daemon',
    }
    for legacy, canonical in pairs.items():
        old = importlib.import_module(f'living_assistant.{legacy}')
        new = importlib.import_module(f'living_assistant.{canonical}')
        assert old is new


def test_agents_and_connectors_packages_preserve_legacy_public_symbols():
    from living_assistant.agents import SpecialistRouter
    from living_assistant.connectors import ConnectorManager, ConnectorRegistry
    assert SpecialistRouter is not None
    assert ConnectorManager is not None and ConnectorRegistry is not None
