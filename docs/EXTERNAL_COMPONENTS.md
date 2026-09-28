# External Components

This document tracks external components vendored into our main repository.

## agency-agents
* Upstream: https://github.com/msitarzewski/agency-agents.git
* Integrated commit: 053ddbbf392a1688fc7043d81529f47ef2cf86c8
* License: MIT
* Local path: external-components/agency-agents

## agentmemory
* Upstream: https://github.com/rohitg00/agentmemory.git
* Integrated commit: e04ba88819c365c9acf9d6661ea802143e728bd6
* License: MIT
* Local path: external-components/agentmemory

## Anthropic-Cybersecurity-Skills
* Upstream: https://github.com/mukul975/Anthropic-Cybersecurity-Skills.git
* Integrated commit: 54a798831d2266a3ca61ce68a7acb80b81160d57
* License: Unknown
* Location: container volume `living-assistant-cybersecurity-skills` only (not vendored in this repo).
  Its malware-analysis write-ups and YARA rules trip Windows Defender heuristics when stored on the host,
  so the assistant reads them through network-less, read-only containers. Populate it with the
  `security_skills_sync` tool (requires approval and Docker Desktop).

## awesome-ai-agent-tools
* Upstream: https://github.com/michielhdoteth/awesome-ai-agent-tools.git
* Integrated commit: 579a0a96dab86857da7daa483aa0281d7dde8a17
* License: CC0-1.0
* Local path: external-components/awesome-ai-agent-tools

## awesome-harness-engineering
* Upstream: https://github.com/harness-engineer/awesome-harness-engineering.git
* Integrated commit: 0b14b85ab0fe286ee19dbe3ad36d7ce5b3fc5c55
* License: Unknown
* Local path: external-components/awesome-harness-engineering

## browser-use
* Upstream: https://github.com/browser-use/browser-use.git
* Integrated commit: d8110c5ff87ccba887aaa726cdb780f2f84bef8d
* License: MIT
* Local path: external-components/browser-use

## codebase-memory-mcp
* Upstream: https://github.com/DeusData/codebase-memory-mcp.git
* Integrated commit: e783f73d752f83b689451e3a7e48061cda1202f7
* License: MIT
* Local path: external-components/codebase-memory-mcp

## diagram-design
* Upstream: https://github.com/cathrynlavery/diagram-design.git
* Integrated commit: dc1ace47b99a419e42d01a03cb6ace5346efa8ae
* License: MIT
* Local path: external-components/diagram-design

## Edge0
* Upstream: https://github.com/Edge0-AI/Edge0.git
* Integrated commit: fb4cd2c49ebe22bb230e1451ecb8fb4957ca62e6
* License: MIT
* Local path: external-components/Edge0

## Graft
* Upstream: https://github.com/AEndrix03/Graft.git
* Integrated commit: 85f1f36e6cac63630b988f63d153b16f881a11e9
* License: Apache-2.0
* Local path: external-components/Graft

## openmontage
* Upstream: https://github.com/MrArtt/openmontage.git
* Integrated commit: 1188e1bee9bfd97258e5014abf0b866a6691cc9b
* License: Apache-2.0
* Local path: external-components/openmontage

## OpenViking
* Upstream: https://github.com/volcengine/OpenViking.git
* Integrated commit: de1c5c49541f8910877db31f1a4ceb617e8e9855
* License: Apache-2.0
* Local path: external-components/OpenViking

## scientific-agent-skills
* Upstream: https://github.com/K-Dense-AI/scientific-agent-skills.git
* Integrated commit: 49c6e97775eaa18ba791bebe23162a70ae601c18
* License: MIT
* Local path: external-components/scientific-agent-skills
