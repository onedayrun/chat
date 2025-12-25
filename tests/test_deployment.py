"""
Tests for Deployment Service
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.services.deployment_service import (
    DeploymentManager,
    DeploymentResult,
    DeploymentStatus,
    RailwayDeployer,
    VercelDeployer,
    RenderDeployer,
    BaseDeployer
)


class TestDeploymentResult:
    """Testy dla DeploymentResult"""
    
    def test_create_success_result(self):
        """Test tworzenia sukcesu"""
        result = DeploymentResult(
            success=True,
            status=DeploymentStatus.SUCCESS,
            url="https://app.railway.app",
            deployment_id="dep-123"
        )
        
        assert result.success is True
        assert result.status == DeploymentStatus.SUCCESS
        assert result.url == "https://app.railway.app"
        assert result.error is None
    
    def test_create_failure_result(self):
        """Test tworzenia błędu"""
        result = DeploymentResult(
            success=False,
            status=DeploymentStatus.FAILED,
            error="Build failed"
        )
        
        assert result.success is False
        assert result.status == DeploymentStatus.FAILED
        assert result.error == "Build failed"
        assert result.url is None
    
    def test_to_dict(self):
        """Test konwersji do słownika"""
        result = DeploymentResult(
            success=True,
            status=DeploymentStatus.BUILDING,
            deployment_id="dep-456",
            logs="Building..."
        )
        
        data = result.to_dict()
        
        assert data["success"] is True
        assert data["status"] == "building"
        assert data["deployment_id"] == "dep-456"


class TestDeploymentStatus:
    """Testy dla statusów deployment"""
    
    def test_all_statuses_defined(self):
        """Test czy wszystkie statusy są zdefiniowane"""
        statuses = list(DeploymentStatus)
        
        assert DeploymentStatus.PENDING in statuses
        assert DeploymentStatus.BUILDING in statuses
        assert DeploymentStatus.DEPLOYING in statuses
        assert DeploymentStatus.SUCCESS in statuses
        assert DeploymentStatus.FAILED in statuses


class TestRailwayDeployer:
    """Testy dla Railway deployer"""
    
    @pytest.fixture
    def deployer(self):
        with patch('src.services.deployment_service.settings') as mock_settings:
            mock_settings.RAILWAY_TOKEN = "test-token"
            return RailwayDeployer(token="test-token")
    
    @pytest.mark.asyncio
    async def test_deploy(self, deployer):
        """Test deployment na Railway"""
        result = await deployer.deploy(
            repo="test-org/test-app",
            branch="main"
        )
        
        assert result.success is True
        assert result.status == DeploymentStatus.BUILDING
        assert "railway" in result.deployment_id
    
    @pytest.mark.asyncio
    async def test_get_status(self, deployer):
        """Test statusu deployment"""
        result = await deployer.get_status("railway-test-org-test-app")
        
        assert result.success is True
        assert result.deployment_id == "railway-test-org-test-app"
    
    @pytest.mark.asyncio
    async def test_get_logs(self, deployer):
        """Test pobierania logów"""
        logs = await deployer.get_logs("railway-test")
        
        assert isinstance(logs, str)
        assert "railway-test" in logs


class TestVercelDeployer:
    """Testy dla Vercel deployer"""
    
    @pytest.fixture
    def deployer(self):
        with patch('src.services.deployment_service.settings') as mock_settings:
            mock_settings.VERCEL_TOKEN = "test-token"
            return VercelDeployer(token="test-token")
    
    @pytest.mark.asyncio
    async def test_deploy(self, deployer):
        """Test deployment na Vercel"""
        result = await deployer.deploy(
            repo="test-org/test-app",
            branch="main",
            config={"framework": "nextjs"}
        )
        
        assert result.success is True
        assert "vercel" in result.deployment_id
        assert ".vercel.app" in result.url


class TestRenderDeployer:
    """Testy dla Render deployer"""
    
    @pytest.fixture
    def deployer(self):
        with patch('src.services.deployment_service.settings') as mock_settings:
            mock_settings.RENDER_API_KEY = "test-key"
            return RenderDeployer(api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_deploy(self, deployer):
        """Test deployment na Render"""
        result = await deployer.deploy(
            repo="test-org/test-app",
            branch="main"
        )
        
        assert result.success is True
        assert "render" in result.deployment_id
        assert ".onrender.com" in result.url


class TestDeploymentManager:
    """Testy dla DeploymentManager"""
    
    @pytest.fixture
    def manager_all_platforms(self):
        """Manager ze wszystkimi platformami"""
        with patch('src.services.deployment_service.settings') as mock_settings:
            mock_settings.RAILWAY_TOKEN = "railway-token"
            mock_settings.VERCEL_TOKEN = "vercel-token"
            mock_settings.RENDER_API_KEY = "render-key"
            return DeploymentManager()
    
    @pytest.fixture
    def manager_railway_only(self):
        """Manager tylko z Railway"""
        with patch('src.services.deployment_service.settings') as mock_settings:
            mock_settings.RAILWAY_TOKEN = "railway-token"
            mock_settings.VERCEL_TOKEN = None
            mock_settings.RENDER_API_KEY = None
            return DeploymentManager()
    
    def test_get_available_platforms_all(self, manager_all_platforms):
        """Test dostępnych platform - wszystkie"""
        platforms = manager_all_platforms.get_available_platforms()
        
        assert "railway" in platforms
        assert "vercel" in platforms
        assert "render" in platforms
    
    def test_get_available_platforms_partial(self, manager_railway_only):
        """Test dostępnych platform - częściowe"""
        platforms = manager_railway_only.get_available_platforms()
        
        assert "railway" in platforms
        assert "vercel" not in platforms
        assert "render" not in platforms
    
    @pytest.mark.asyncio
    async def test_deploy_success(self, manager_all_platforms):
        """Test deployment przez manager"""
        result = await manager_all_platforms.deploy(
            platform="railway",
            repo="org/app",
            branch="main"
        )
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_deploy_unavailable_platform(self, manager_railway_only):
        """Test deployment na niedostępnej platformie"""
        result = await manager_railway_only.deploy(
            platform="vercel",
            repo="org/app"
        )
        
        assert result.success is False
        assert "not available" in result.error.lower()
    
    def test_recommend_platform_frontend(self, manager_all_platforms):
        """Test rekomendacji dla frontend"""
        platform = manager_all_platforms.recommend_platform(
            tech_stack="react_next",
            project_type="web_app"
        )
        
        assert platform == "vercel"
    
    def test_recommend_platform_backend(self, manager_all_platforms):
        """Test rekomendacji dla backend"""
        platform = manager_all_platforms.recommend_platform(
            tech_stack="python_fastapi",
            project_type="api"
        )
        
        assert platform == "railway"
    
    def test_recommend_platform_fallback(self, manager_railway_only):
        """Test fallback rekomendacji"""
        platform = manager_railway_only.recommend_platform(
            tech_stack="react_next",  # Normalnie Vercel, ale niedostępny
            project_type="web_app"
        )
        
        # Should fallback to first available
        assert platform == "railway"


class TestBaseDeployer:
    """Testy dla abstrakcyjnej klasy BaseDeployer"""
    
    def test_cannot_instantiate(self):
        """Test że nie można utworzyć instancji BaseDeployer"""
        with pytest.raises(TypeError):
            BaseDeployer()
    
    def test_subclass_must_implement_methods(self):
        """Test że subklasa musi implementować metody"""
        class IncompleteDeployer(BaseDeployer):
            pass
        
        with pytest.raises(TypeError):
            IncompleteDeployer()


class TestDeploymentIntegration:
    """Testy integracyjne deployment"""
    
    @pytest.mark.asyncio
    async def test_full_deployment_flow(self):
        """Test pełnego flow deployment"""
        with patch('src.services.deployment_service.settings') as mock_settings:
            mock_settings.RAILWAY_TOKEN = "test-token"
            mock_settings.VERCEL_TOKEN = None
            mock_settings.RENDER_API_KEY = None
            
            manager = DeploymentManager()
            
            # Check available platforms
            platforms = manager.get_available_platforms()
            assert len(platforms) > 0
            
            # Get recommendation
            platform = manager.recommend_platform("python_fastapi", "api")
            assert platform in platforms
            
            # Deploy
            result = await manager.deploy(
                platform=platform,
                repo="test/app",
                config={"env": {"DEBUG": "false"}}
            )
            
            assert result.success is True
            assert result.url is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
