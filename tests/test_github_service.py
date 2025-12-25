"""
Tests for GitHub Service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from github import GithubException

from src.services.github_service import GitHubService


class TestGitHubService:
    """Testy dla GitHubService"""
    
    @pytest.fixture
    def mock_github(self):
        """Mock dla PyGithub"""
        with patch('src.services.github_service.Github') as mock:
            mock_user = Mock()
            mock_user.login = "test-user"
            mock_instance = mock.return_value
            mock_instance.get_user.return_value = mock_user
            yield mock_instance
    
    @pytest.fixture
    def service(self, mock_github):
        """Tworzy serwis z mockowanym GitHub"""
        with patch('src.services.github_service.settings') as mock_settings:
            mock_settings.GITHUB_TOKEN = "test-token"
            mock_settings.GITHUB_ORG = "test-org"
            return GitHubService(token="test-token")
    
    @pytest.mark.asyncio
    async def test_create_repository_success(self, service, mock_github):
        """Test tworzenia repozytorium"""
        mock_repo = Mock()
        mock_repo.full_name = "test-org/test-repo"
        mock_repo.html_url = "https://github.com/test-org/test-repo"
        mock_repo.clone_url = "https://github.com/test-org/test-repo.git"
        mock_repo.ssh_url = "git@github.com:test-org/test-repo.git"
        mock_repo.default_branch = "main"
        
        mock_org = Mock()
        mock_org.create_repo.return_value = mock_repo
        mock_github.get_organization.return_value = mock_org
        
        result = await service.create_repository(
            name="test-repo",
            description="Test repository",
            private=True
        )
        
        assert result["success"] is True
        assert result["repo_name"] == "test-org/test-repo"
        assert "url" in result
    
    @pytest.mark.asyncio
    async def test_create_repository_failure(self, service, mock_github):
        """Test błędu przy tworzeniu repozytorium"""
        mock_github.get_organization.side_effect = GithubException(
            status=404,
            data={"message": "Not Found"}
        )
        service.user.create_repo.side_effect = GithubException(
            status=422,
            data={"message": "Repository already exists"}
        )
        
        result = await service.create_repository(
            name="existing-repo",
            description="Test"
        )
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_create_file(self, service, mock_github):
        """Test tworzenia pliku"""
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_commit = Mock()
        mock_commit.sha = "abc123"
        mock_content = Mock()
        mock_content.html_url = "https://github.com/org/repo/blob/main/test.py"
        
        mock_repo.create_file.return_value = {
            "commit": mock_commit,
            "content": mock_content
        }
        mock_github.get_repo.return_value = mock_repo
        
        result = await service.create_file(
            repo="test-org/test-repo",
            path="src/main.py",
            content="print('hello')",
            message="Add main.py"
        )
        
        assert result["success"] is True
        assert result["path"] == "src/main.py"
        assert "sha" in result
    
    @pytest.mark.asyncio
    async def test_get_file(self, service, mock_github):
        """Test pobierania pliku"""
        import base64
        
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        
        content = "print('hello world')"
        mock_file = Mock()
        mock_file.content = base64.b64encode(content.encode()).decode()
        mock_file.sha = "def456"
        mock_file.size = len(content)
        mock_file.html_url = "https://github.com/org/repo/blob/main/main.py"
        mock_file.type = "file"
        
        mock_repo.get_contents.return_value = mock_file
        mock_github.get_repo.return_value = mock_repo
        
        result = await service.get_file(
            repo="test-org/test-repo",
            path="main.py"
        )
        
        assert result["success"] is True
        assert result["type"] == "file"
        assert result["content"] == content
    
    @pytest.mark.asyncio
    async def test_create_multiple_files(self, service, mock_github):
        """Test tworzenia wielu plików"""
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_commit = Mock()
        mock_commit.sha = "abc123"
        mock_content = Mock()
        mock_content.html_url = "https://github.com/org/repo/blob/main/test.py"
        
        mock_repo.create_file.return_value = {
            "commit": mock_commit,
            "content": mock_content
        }
        mock_repo.get_contents.side_effect = GithubException(
            status=404, data={"message": "Not Found"}
        )
        mock_github.get_repo.return_value = mock_repo
        
        files = [
            {"path": "src/__init__.py", "content": ""},
            {"path": "src/main.py", "content": "print('hello')"},
            {"path": "requirements.txt", "content": "fastapi>=0.100.0"}
        ]
        
        result = await service.create_multiple_files(
            repo="test-org/test-repo",
            files=files,
            message="Initial commit"
        )
        
        assert result["created"] == 3
        assert result["errors"] == 0
    
    @pytest.mark.asyncio
    async def test_create_branch(self, service, mock_github):
        """Test tworzenia brancha"""
        mock_repo = Mock()
        mock_branch = Mock()
        mock_branch.commit.sha = "abc123"
        mock_repo.get_branch.return_value = mock_branch
        mock_repo.create_git_ref.return_value = Mock()
        mock_github.get_repo.return_value = mock_repo
        
        result = await service.create_branch(
            repo="test-org/test-repo",
            branch_name="feature/new-feature",
            from_branch="main"
        )
        
        assert result["success"] is True
        assert result["branch"] == "feature/new-feature"
    
    def test_get_fastapi_main(self, service):
        """Test generowania main.py dla FastAPI"""
        content = service._get_fastapi_main()
        
        assert "FastAPI" in content
        assert "app = FastAPI" in content
        assert "@app.get" in content
        assert "/health" in content
    
    def test_get_requirements(self, service):
        """Test generowania requirements.txt"""
        fastapi_reqs = service._get_requirements("fastapi")
        django_reqs = service._get_requirements("django")
        
        assert "fastapi" in fastapi_reqs
        assert "uvicorn" in fastapi_reqs
        assert "django" in django_reqs
    
    def test_get_dockerfile(self, service):
        """Test generowania Dockerfile"""
        dockerfile = service._get_dockerfile("python")
        
        assert "FROM python" in dockerfile
        assert "WORKDIR" in dockerfile
        assert "pip install" in dockerfile
        assert "uvicorn" in dockerfile
    
    def test_get_gitignore(self, service):
        """Test generowania .gitignore"""
        python_ignore = service._get_gitignore("python")
        node_ignore = service._get_gitignore("node")
        
        assert "__pycache__" in python_ignore
        assert ".env" in python_ignore
        assert "node_modules" in node_ignore


class TestGitHubServiceTemplates:
    """Testy dla template'ów projektów"""
    
    @pytest.fixture
    def service(self):
        with patch('src.services.github_service.Github'):
            with patch('src.services.github_service.settings') as mock_settings:
                mock_settings.GITHUB_TOKEN = "test-token"
                mock_settings.GITHUB_ORG = "test-org"
                return GitHubService(token="test-token")
    
    @pytest.mark.asyncio
    async def test_setup_project_from_template(self, service):
        """Test tworzenia projektu z template'u"""
        with patch.object(service, 'create_repository') as mock_create:
            with patch.object(service, '_setup_basic_structure') as mock_setup:
                mock_create.return_value = {
                    "success": True,
                    "repo_name": "test-org/new-project"
                }
                
                result = await service.setup_project_from_template(
                    project_name="new-project",
                    tech_stack="python_fastapi",
                    description="New FastAPI project"
                )
                
                assert result["success"] is True
                mock_create.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
