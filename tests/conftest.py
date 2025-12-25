"""
Pytest Configuration and Fixtures
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
import sys
import types
import inspect
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


try:
    import github  # type: ignore
except ModuleNotFoundError:
    github = types.ModuleType("github")

    class GithubException(Exception):
        def __init__(self, status=None, data=None):
            message = None
            if isinstance(data, dict):
                message = data.get("message")
            super().__init__(message or "GithubException")
            self.status = status
            self.data = data

    class Github:
        def __init__(self, token=None):
            self.token = token

        def get_user(self):
            user = Mock()
            user.login = "stub-user"
            return user

        def get_organization(self, org):
            raise GithubException(status=404, data={"message": "Not Found"})

        def get_repo(self, repo):
            return Mock()

    github.Github = Github
    github.GithubException = GithubException

    repo_mod = types.ModuleType("github.Repository")

    class Repository:  # noqa: B903
        pass

    repo_mod.Repository = Repository

    content_mod = types.ModuleType("github.ContentFile")

    class ContentFile:  # noqa: B903
        pass

    content_mod.ContentFile = ContentFile

    sys.modules["github"] = github
    sys.modules["github.Repository"] = repo_mod
    sys.modules["github.ContentFile"] = content_mod


try:
    import litellm  # type: ignore
except ModuleNotFoundError:
    litellm = types.ModuleType("litellm")

    async def acompletion(*args, **kwargs):
        raise RuntimeError("litellm is not installed")

    litellm.acompletion = acompletion
    litellm.api_key = None
    litellm.api_base = None
    sys.modules["litellm"] = litellm


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for tests"""
    with patch('config.settings.settings') as mock:
        mock.APP_NAME = "OneDay.run Test"
        mock.APP_VERSION = "1.0.0-test"
        mock.DEBUG = True
        mock.SECRET_KEY = "test-secret"
        mock.ANTHROPIC_API_KEY = "test-anthropic-key"
        mock.GITHUB_TOKEN = "test-github-token"
        mock.GITHUB_ORG = "test-org"
        mock.RAILWAY_TOKEN = "test-railway"
        mock.VERCEL_TOKEN = "test-vercel"
        mock.RENDER_API_KEY = "test-render"
        mock.DATABASE_URL = "sqlite:///./test.db"
        mock.DEFAULT_MODEL = "anthropic/claude-opus-4-5-20251101"
        mock.MAX_TOKENS = 4096
        mock.TEMPERATURE = 0.7
        mock.PRICING_TIERS = {
            "1h": {"price": 150, "max_tokens": 50000},
            "8h": {"price": 1200, "max_tokens": 400000},
        }
        yield mock


@pytest.fixture
def mock_github():
    """Mock GitHub client"""
    with patch('src.services.github_service.Github') as mock:
        mock_user = Mock()
        mock_user.login = "test-user"
        mock_instance = mock.return_value
        mock_instance.get_user.return_value = mock_user
        yield mock_instance


@pytest.fixture
def mock_litellm():
    """Mock LiteLLM for LLM calls"""
    with patch('litellm.acompletion') as mock:
        async def mock_completion(*args, **kwargs):
            class MockChoice:
                def __init__(self):
                    self.message = Mock(content="Mock response", tool_calls=None)
                    self.delta = Mock(content="Mock ", tool_calls=None)
            
            class MockResponse:
                def __init__(self):
                    self.choices = [MockChoice()]
            
            if kwargs.get('stream'):
                async def stream_gen():
                    for word in ["Mock", " ", "response"]:
                        choice = MockChoice()
                        choice.delta.content = word
                        yield Mock(choices=[choice])
                return stream_gen()
            return MockResponse()
        
        mock.side_effect = mock_completion
        yield mock


@pytest.fixture
def sample_project_data():
    """Sample project data for tests"""
    return {
        "project_id": "test-001",
        "client_name": "Test Client",
        "tier": "8h",
        "initial_message": "Build me a REST API for task management",
        "tech_stack": "python_fastapi",
        "project_type": "api"
    }


@pytest.fixture
def sample_component():
    """Sample component for tests"""
    from src.components.library import Component, ComponentCategory
    
    return Component(
        id="test-component",
        name="Test Component",
        description="A test component for unit tests",
        category=ComponentCategory.UTILS,
        tech_stack=["python"],
        files=[
            {"path": "test.py", "content": "# Test file\nprint('hello')"}
        ],
        dependencies=["pytest"],
        tags=["test", "sample"]
    )


@pytest.fixture
def sample_files():
    """Sample files for GitHub tests"""
    return [
        {"path": "src/__init__.py", "content": ""},
        {"path": "src/main.py", "content": "from fastapi import FastAPI\napp = FastAPI()"},
        {"path": "requirements.txt", "content": "fastapi>=0.100.0\nuvicorn>=0.23.0"},
        {"path": "README.md", "content": "# Test Project\n\nGenerated by OneDay.run"},
    ]


# Markers for slow/integration tests
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")


def pytest_pyfunc_call(pyfuncitem):
    try:
        import pytest_asyncio  # type: ignore

        if hasattr(pytest_asyncio, "fixture"):
            return None
    except ModuleNotFoundError:
        pass

    testfunction = pyfuncitem.obj
    if not inspect.iscoroutinefunction(testfunction):
        return None

    loop = pyfuncitem.funcargs.get("event_loop")
    if loop is None:
        loop = asyncio.new_event_loop()
        close_loop = True
    else:
        close_loop = False

    old_loop = None
    try:
        try:
            old_loop = asyncio.get_event_loop()
        except RuntimeError:
            old_loop = None

        asyncio.set_event_loop(loop)
        kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
        loop.run_until_complete(testfunction(**kwargs))
        return True
    finally:
        asyncio.set_event_loop(old_loop)
        if close_loop:
            loop.close()
