from pydantic import BaseModel, Field
from typing import List, Optional

class ExecutivePlan(BaseModel):
    objective: str = Field(description="The high-level objective to achieve based on the user request.")
    teams: List[str] = Field(description="List of team supervisors required to fulfill this objective (e.g., 'development', 'operations', 'security', 'knowledge', 'personal', 'upgrade').")
    parallel: bool = Field(description="Whether the selected teams can operate concurrently.")
    risk: str = Field(description="The assessed risk level of the request (e.g., 'low', 'medium', 'high', 'critical').")
    reason: str = Field(description="Brief reasoning for why these teams and risk level were chosen.")
    requires_planning: bool = Field(description="True if a Mission Planner should be invoked for complex multistep missions.")

class ProposedMutation(BaseModel):
    action: str = Field(description="The specific action to take (e.g., 'restart_service', 'modify_file').")
    target: str = Field(description="The target of the action (e.g., file path, service name).")
    payload: Optional[str] = Field(None, description="The content or arguments for the action.")
    justification: str = Field(description="Why this mutation is necessary.")

class SpecialistResponse(BaseModel):
    specialist: str = Field(description="The logical name of the specialist role (e.g., 'database', 'network').")
    summary: str = Field(description="A concise summary of the investigation or action.")
    findings: List[str] = Field(default_factory=list, description="Specific factual findings discovered by the specialist.")
    evidence: List[str] = Field(default_factory=list, description="Concrete evidence supporting the findings (e.g., log snippets, metrics, file contents).")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0.")
    uncertainties: List[str] = Field(default_factory=list, description="List of unknowns, missing data, or areas requiring further investigation.")
    recommended_actions: List[str] = Field(default_factory=list, description="High-level recommended next steps.")
    proposed_mutations: List[ProposedMutation] = Field(default_factory=list, description="Explicit system mutations that require approval and execution.")
