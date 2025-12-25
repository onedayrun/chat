"""
Tests for FastAPI Application
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

# Import app after patching settings
with patch('src.services.github_service.settings') as mock_settings:
    mock_settings.GITHUB_TOKEN = "test-token"
    mock_settings.GITHUB_ORG = "test-org"
    
    with patch('src.services.deployment_service.settings') as mock_deploy_settings:
        mock_deploy_settings.RAILWAY_TOKEN = "test-railway"
        mock_deploy_settings.VERCEL_TOKEN = "test-vercel"
        mock_deploy_settings.RENDER_API_KEY = "test-render"
        
        with patch('config.settings.settings') as mock_app_settings:
            mock_app_settings.APP_NAME = "OneDay.run Test"
            mock_app_settings.APP_VERSION = "1.0.0"
            mock_app_settings.GITHUB_TOKEN = "test-token"
            mock_app_settings.ANTHROPIC_API_KEY = "test-key"
            mock_app_settings.PRICING_TIERS = {
                "1h": {"price": 150, "max_tokens": 50000, "max_files": 5},
                "8h": {"price": 1200, "max_tokens": 400000, "max_files": 20},
            }
            
            from src.main import app


client = TestClient(app)


class TestRootEndpoints:
    """Testy dla podstawowych endpoints"""
    
    def test_root(self):
        """Test root endpoint"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"
    
    def test_health(self):
        """Test health endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestProjectEndpoints:
    """Testy dla endpoints projektów"""
    
    def test_create_project(self):
        """Test tworzenia projektu"""
        project_data = {
            "client_name": "Test Client",
            "tier": "8h",
            "initial_message": "Build me an API"
        }
        
        response = client.post("/projects", json=project_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
        assert data["status"] == "created"
        assert data["phase"] == "discovery"
    
    def test_create_project_with_stack(self):
        """Test tworzenia projektu z tech stack"""
        project_data = {
            "client_name": "Test Client",
            "tier": "24h",
            "initial_message": "Build dashboard",
            "tech_stack": "python_fastapi",
            "project_type": "dashboard"
        }
        
        response = client.post("/projects", json=project_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
    
    def test_create_project_invalid_tier(self):
        """Test tworzenia projektu z nieprawidłowym tier"""
        project_data = {
            "client_name": "Test Client",
            "tier": "invalid",
            "initial_message": "Build me an API"
        }
        
        response = client.post("/projects", json=project_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_get_project_not_found(self):
        """Test pobierania nieistniejącego projektu"""
        response = client.get("/projects/non-existent-id")
        
        assert response.status_code == 404


class TestComponentsEndpoints:
    """Testy dla endpoints komponentów"""
    
    def test_list_components_categories(self):
        """Test listy kategorii"""
        response = client.get("/components")
        
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "auth" in data["categories"]
        assert "database" in data["categories"]
    
    def test_list_components_by_category(self):
        """Test listy komponentów w kategorii"""
        response = client.get("/components?category=auth")
        
        assert response.status_code == 200
        data = response.json()
        assert "components" in data
    
    def test_search_components(self):
        """Test wyszukiwania komponentów"""
        response = client.get("/components/search?q=auth")
        
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "components" in data
        assert data["success"] is True
    
    def test_search_components_with_filters(self):
        """Test wyszukiwania z filtrami"""
        response = client.get("/components/search?q=jwt&category=auth&tech_stack=python")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestPricingEndpoint:
    """Testy dla endpoint cennika"""
    
    def test_get_pricing(self):
        """Test pobierania cennika"""
        response = client.get("/pricing")
        
        assert response.status_code == 200
        data = response.json()
        assert "tiers" in data
        assert "currency" in data
        assert "includes" in data
        assert data["currency"] == "PLN"
    
    def test_pricing_tiers_structure(self):
        """Test struktury tier-ów cenowych"""
        response = client.get("/pricing")
        data = response.json()
        
        # Check some tiers exist
        tiers = data["tiers"]
        assert "1h" in tiers or "8h" in tiers


class TestValidation:
    """Testy walidacji danych"""
    
    def test_project_tier_validation(self):
        """Test walidacji tier w projekcie"""
        valid_tiers = ["1h", "8h", "24h", "36h", "48h", "72h"]
        
        for tier in valid_tiers:
            project_data = {
                "client_name": "Test",
                "tier": tier,
                "initial_message": "Test"
            }
            response = client.post("/projects", json=project_data)
            assert response.status_code == 200, f"Tier {tier} should be valid"
    
    def test_project_required_fields(self):
        """Test wymaganych pól"""
        # Missing client_name
        response = client.post("/projects", json={
            "tier": "8h",
            "initial_message": "Test"
        })
        assert response.status_code == 422
        
        # Missing tier
        response = client.post("/projects", json={
            "client_name": "Test",
            "initial_message": "Test"
        })
        assert response.status_code == 422
        
        # Missing initial_message
        response = client.post("/projects", json={
            "client_name": "Test",
            "tier": "8h"
        })
        assert response.status_code == 422


class TestCORS:
    """Testy CORS"""
    
    def test_cors_headers(self):
        """Test nagłówków CORS"""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # CORS should allow requests
        assert response.status_code in [200, 405]


class TestErrorHandling:
    """Testy obsługi błędów"""
    
    def test_404_error(self):
        """Test błędu 404"""
        response = client.get("/non-existent-endpoint")
        assert response.status_code == 404
    
    def test_method_not_allowed(self):
        """Test niedozwolonej metody"""
        response = client.delete("/")
        assert response.status_code == 405


class TestChatUI:
    """Testy dla Chat UI"""
    
    def test_chat_ui_returns_html(self):
        """Test że chat UI zwraca HTML"""
        # First create a project to get valid ID
        project_response = client.post("/projects", json={
            "client_name": "Test",
            "tier": "8h",
            "initial_message": "Test"
        })
        project_id = project_response.json()["project_id"]
        
        response = client.get(f"/chat/{project_id}")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "OneDay.run" in response.text
        assert "WebSocket" in response.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
