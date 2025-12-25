"""
Tests for Component Library
"""
import pytest
from src.components.library import (
    ComponentLibrary,
    Component,
    ComponentCategory,
    component_library
)


class TestComponent:
    """Testy dla klasy Component"""
    
    def test_create_component(self):
        """Test tworzenia komponentu"""
        comp = Component(
            id="test-component",
            name="Test Component",
            description="A test component",
            category=ComponentCategory.UTILS,
            tech_stack=["python"],
            files=[{"path": "test.py", "content": "# test"}],
            dependencies=["pytest"],
            tags=["test", "utility"]
        )
        
        assert comp.id == "test-component"
        assert comp.name == "Test Component"
        assert comp.category == ComponentCategory.UTILS
        assert len(comp.files) == 1
        assert comp.version == "1.0.0"
    
    def test_component_to_dict(self):
        """Test konwersji komponentu do słownika"""
        comp = Component(
            id="auth-basic",
            name="Basic Auth",
            description="Simple authentication",
            category=ComponentCategory.AUTH,
            tech_stack=["python", "fastapi"],
            files=[],
            dependencies=["passlib"]
        )
        
        data = comp.to_dict()
        
        assert data["id"] == "auth-basic"
        assert data["category"] == "auth"
        assert "python" in data["tech_stack"]
        assert isinstance(data["dependencies"], list)


class TestComponentCategory:
    """Testy dla kategorii komponentów"""
    
    def test_all_categories_exist(self):
        """Test czy wszystkie kategorie są zdefiniowane"""
        categories = list(ComponentCategory)
        
        assert ComponentCategory.AUTH in categories
        assert ComponentCategory.DATABASE in categories
        assert ComponentCategory.API in categories
        assert ComponentCategory.UI in categories
        assert ComponentCategory.INTEGRATION in categories
        assert ComponentCategory.UTILS in categories
    
    def test_category_values(self):
        """Test wartości kategorii"""
        assert ComponentCategory.AUTH.value == "auth"
        assert ComponentCategory.DATABASE.value == "database"
        assert ComponentCategory.API.value == "api"


class TestComponentLibrary:
    """Testy dla ComponentLibrary"""
    
    @pytest.fixture
    def library(self):
        """Tworzy nową bibliotekę do testów"""
        return ComponentLibrary()
    
    def test_default_components_loaded(self, library):
        """Test czy domyślne komponenty są załadowane"""
        assert len(library.components) > 0
        
        # Check specific components exist
        assert "auth-fastapi-jwt" in library.components
        assert "db-sqlalchemy-base" in library.components
        assert "api-crud-base" in library.components
    
    def test_add_component(self, library):
        """Test dodawania komponentu"""
        initial_count = len(library.components)
        
        new_comp = Component(
            id="custom-component",
            name="Custom Component",
            description="A custom component",
            category=ComponentCategory.UTILS,
            tech_stack=["python"],
            files=[],
            dependencies=[]
        )
        
        result = library.add_component(new_comp)
        
        assert result is True
        assert len(library.components) == initial_count + 1
        assert "custom-component" in library.components
    
    def test_get_component(self, library):
        """Test pobierania komponentu"""
        comp = library.get_component("auth-fastapi-jwt")
        
        assert comp is not None
        assert comp.id == "auth-fastapi-jwt"
        assert comp.category == ComponentCategory.AUTH
    
    def test_get_component_not_found(self, library):
        """Test pobierania nieistniejącego komponentu"""
        comp = library.get_component("non-existent")
        assert comp is None
    
    def test_get_component_files(self, library):
        """Test pobierania plików komponentu"""
        files = library.get_component_files("auth-fastapi-jwt")
        
        assert len(files) > 0
        assert any("router.py" in f["path"] for f in files)
        assert any("security.py" in f["path"] for f in files)
    
    def test_get_component_files_not_found(self, library):
        """Test pobierania plików nieistniejącego komponentu"""
        files = library.get_component_files("non-existent")
        assert files == []
    
    def test_list_categories(self, library):
        """Test listy kategorii"""
        categories = library.list_categories()
        
        assert "auth" in categories
        assert "database" in categories
        assert "api" in categories
        assert len(categories) == len(ComponentCategory)
    
    def test_list_by_category(self, library):
        """Test listy komponentów w kategorii"""
        auth_components = library.list_by_category("auth")
        
        assert len(auth_components) > 0
        assert all(c["category"] == "auth" for c in auth_components)
    
    @pytest.mark.asyncio
    async def test_search_by_query(self, library):
        """Test wyszukiwania po zapytaniu"""
        result = await library.search(query="auth")
        
        assert result["success"] is True
        assert result["count"] > 0
        assert any("auth" in c["name"].lower() or "auth" in c["description"].lower() 
                   for c in result["components"])
    
    @pytest.mark.asyncio
    async def test_search_by_category(self, library):
        """Test wyszukiwania po kategorii"""
        result = await library.search(query="", category="database")
        
        assert result["success"] is True
        assert all(c["category"] == "database" for c in result["components"])
    
    @pytest.mark.asyncio
    async def test_search_by_tech_stack(self, library):
        """Test wyszukiwania po stack technologicznym"""
        result = await library.search(query="", tech_stack="python")
        
        assert result["success"] is True
        # All results should include python in tech_stack
        for comp in result["components"]:
            assert "python" in comp["tech_stack"]
    
    @pytest.mark.asyncio
    async def test_search_combined_filters(self, library):
        """Test wyszukiwania z kombinacją filtrów"""
        result = await library.search(
            query="jwt",
            category="auth",
            tech_stack="fastapi"
        )
        
        assert result["success"] is True
        # Results should match all criteria
        for comp in result["components"]:
            assert comp["category"] == "auth"
            assert "fastapi" in comp["tech_stack"]
    
    @pytest.mark.asyncio
    async def test_search_no_results(self, library):
        """Test wyszukiwania bez wyników"""
        result = await library.search(query="xyznonexistent123")
        
        assert result["success"] is True
        assert result["count"] == 0
        assert result["components"] == []
    
    @pytest.mark.asyncio
    async def test_search_limit(self, library):
        """Test limitu wyników"""
        result = await library.search(query="", limit=2)
        
        assert len(result["components"]) <= 2


class TestGlobalComponentLibrary:
    """Testy dla globalnej instancji biblioteki"""
    
    def test_global_instance_exists(self):
        """Test czy globalna instancja istnieje"""
        assert component_library is not None
        assert isinstance(component_library, ComponentLibrary)
    
    def test_global_instance_has_components(self):
        """Test czy globalna instancja ma załadowane komponenty"""
        assert len(component_library.components) > 0


class TestComponentContent:
    """Testy zawartości komponentów"""
    
    @pytest.fixture
    def library(self):
        return ComponentLibrary()
    
    def test_auth_jwt_has_required_files(self, library):
        """Test czy auth-jwt ma wymagane pliki"""
        files = library.get_component_files("auth-fastapi-jwt")
        paths = [f["path"] for f in files]
        
        assert any("config.py" in p for p in paths)
        assert any("models.py" in p for p in paths)
        assert any("security.py" in p for p in paths)
        assert any("router.py" in p for p in paths)
    
    def test_auth_jwt_security_content(self, library):
        """Test zawartości security.py"""
        files = library.get_component_files("auth-fastapi-jwt")
        security_file = next((f for f in files if "security.py" in f["path"]), None)
        
        assert security_file is not None
        content = security_file["content"]
        
        assert "verify_password" in content
        assert "get_password_hash" in content
        assert "create_access_token" in content
        assert "jwt" in content.lower()
    
    def test_db_sqlalchemy_has_required_files(self, library):
        """Test czy db-sqlalchemy ma wymagane pliki"""
        files = library.get_component_files("db-sqlalchemy-base")
        paths = [f["path"] for f in files]
        
        assert any("base.py" in p for p in paths)
    
    def test_crud_base_content(self, library):
        """Test zawartości CRUD base"""
        files = library.get_component_files("api-crud-base")
        base_file = next((f for f in files if "base.py" in f["path"]), None)
        
        assert base_file is not None
        content = base_file["content"]
        
        assert "CRUDBase" in content
        assert "async def get" in content
        assert "async def create" in content
        assert "async def update" in content
        assert "async def delete" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
