"""
Tests for Orchestrator Agent
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.agents.orchestrator import (
    OrchestratorAgent,
    ProjectContext,
    ProjectPhase,
    MessageRole
)


class TestProjectContext:
    """Testy dla ProjectContext"""
    
    def test_create_context(self):
        """Test tworzenia kontekstu projektu"""
        context = ProjectContext(
            project_id="test-123",
            client_name="Test Client",
            tier="8h"
        )
        
        assert context.project_id == "test-123"
        assert context.client_name == "Test Client"
        assert context.tier == "8h"
        assert context.current_phase == ProjectPhase.DISCOVERY
        assert context.tokens_used == 0
        assert context.generated_files == []
    
    def test_context_to_dict(self):
        """Test konwersji kontekstu do słownika"""
        context = ProjectContext(
            project_id="test-123",
            client_name="Test Client",
            tier="24h"
        )
        context.tech_stack = "python_fastapi"
        context.github_repo = "org/test-repo"
        
        data = context.to_dict()
        
        assert data["project_id"] == "test-123"
        assert data["tech_stack"] == "python_fastapi"
        assert data["github_repo"] == "org/test-repo"
        assert data["current_phase"] == "discovery"


class TestOrchestratorAgent:
    """Testy dla OrchestratorAgent"""
    
    @pytest.fixture
    def agent(self):
        """Tworzy instancję agenta do testów"""
        return OrchestratorAgent()
    
    @pytest.fixture
    def agent_with_services(self):
        """Tworzy agenta z mock services"""
        mock_github = Mock()
        mock_components = Mock()
        mock_deployers = {"railway": Mock(), "vercel": Mock()}
        
        services = {
            "github": mock_github,
            "components": mock_components,
            "deployers": mock_deployers
        }
        
        return OrchestratorAgent(services=services)
    
    @pytest.mark.asyncio
    async def test_start_project(self, agent):
        """Test rozpoczęcia projektu"""
        context = await agent.start_project(
            project_id="proj-001",
            client_name="Test Client",
            tier="8h",
            initial_message="Build me an API"
        )
        
        assert context.project_id == "proj-001"
        assert context.client_name == "Test Client"
        assert context.tier == "8h"
        assert agent.context is not None
    
    def test_build_system_prompt(self, agent):
        """Test budowania system prompt"""
        agent.context = ProjectContext(
            project_id="test",
            client_name="Client",
            tier="24h"
        )
        
        prompt = agent._build_system_prompt()
        
        assert "discovery" in prompt.lower()
        assert "test" in prompt
    
    def test_advance_phase(self, agent):
        """Test przechodzenia między fazami"""
        agent.context = ProjectContext(
            project_id="test",
            client_name="Client",
            tier="24h"
        )
        
        assert agent.context.current_phase == ProjectPhase.DISCOVERY
        
        result = agent.advance_phase(ProjectPhase.PLANNING)
        
        assert result is True
        assert agent.context.current_phase == ProjectPhase.PLANNING
    
    def test_advance_phase_no_context(self, agent):
        """Test advance_phase bez kontekstu"""
        result = agent.advance_phase(ProjectPhase.PLANNING)
        assert result is False
    
    def test_get_progress(self, agent):
        """Test pobierania postępu"""
        agent.context = ProjectContext(
            project_id="test-123",
            client_name="Client",
            tier="48h"
        )
        agent.context.generated_files = [{"path": "main.py"}]
        agent.context.components_used = ["auth-jwt"]
        agent.context.tokens_used = 5000
        
        progress = agent.get_progress()
        
        assert progress["project_id"] == "test-123"
        assert progress["files_generated"] == 1
        assert progress["components_used"] == 1
        assert progress["tokens_used"] == 5000
        assert "progress_percent" in progress
    
    def test_get_progress_no_context(self, agent):
        """Test get_progress bez kontekstu"""
        progress = agent.get_progress()
        assert "error" in progress
    
    @pytest.mark.asyncio
    async def test_tool_search_components(self, agent_with_services):
        """Test narzędzia search_components"""
        agent_with_services.services["components"].search = AsyncMock(
            return_value={"success": True, "components": []}
        )
        
        result = await agent_with_services._tool_search_components({
            "query": "auth",
            "category": "auth"
        })
        
        assert result["success"] is True
        agent_with_services.services["components"].search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_tool_create_file_no_repo(self, agent_with_services):
        """Test create_file bez skonfigurowanego repo"""
        agent_with_services.context = ProjectContext(
            project_id="test",
            client_name="Client",
            tier="8h"
        )
        # github_repo is None
        
        result = await agent_with_services._tool_create_file({
            "path": "main.py",
            "content": "print('hello')"
        })
        
        assert result["success"] is False
        assert "not configured" in result["error"].lower() or "no repo" in result["error"].lower()


class TestProjectPhases:
    """Testy dla faz projektu"""
    
    def test_all_phases_defined(self):
        """Test czy wszystkie fazy są zdefiniowane"""
        phases = list(ProjectPhase)
        
        assert ProjectPhase.DISCOVERY in phases
        assert ProjectPhase.PLANNING in phases
        assert ProjectPhase.GENERATION in phases
        assert ProjectPhase.DEPLOYMENT in phases
        assert ProjectPhase.HANDOVER in phases
    
    def test_phase_order(self):
        """Test kolejności faz"""
        phases = list(ProjectPhase)
        phase_names = [p.value for p in phases]
        
        assert phase_names.index("discovery") < phase_names.index("planning")
        assert phase_names.index("planning") < phase_names.index("generation")
        assert phase_names.index("generation") < phase_names.index("deployment")


class TestIntegration:
    """Testy integracyjne (wymagają mock LLM)"""
    
    @pytest.mark.asyncio
    @patch('src.agents.orchestrator.acompletion')
    async def test_chat_flow(self, mock_completion):
        """Test pełnego flow chatu"""
        # Mock streaming response
        async def mock_stream():
            class MockChunk:
                def __init__(self, content):
                    self.choices = [Mock(delta=Mock(content=content, tool_calls=None))]
            
            for word in ["Hello", " ", "world", "!"]:
                yield MockChunk(word)
        
        mock_completion.return_value = mock_stream()
        
        agent = OrchestratorAgent()
        await agent.start_project("test", "Client", "8h", "Hello")
        
        response_parts = []
        async for chunk in agent.chat("Build an API", stream=True):
            response_parts.append(chunk)
        
        full_response = "".join(response_parts)
        assert len(full_response) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
