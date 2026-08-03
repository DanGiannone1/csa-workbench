"""Shared, dependency-light application rules for CSA Workbench."""

from .brief import compute_brief
from .engagements import EngagementService, Outcome
from .engagement_results import engagement_detail_text, engagement_product_result
from .personal_workspace import PersonalNotFound, PersonalWorkspaceError, PersonalWorkspaceService
from .tool_protocol import DESTINATION_IDS, ProductToolResult, validate_destination

__all__ = ["DESTINATION_IDS", "EngagementService", "Outcome", "PersonalNotFound", "PersonalWorkspaceError", "PersonalWorkspaceService", "ProductToolResult", "compute_brief", "engagement_detail_text", "engagement_product_result", "validate_destination"]
