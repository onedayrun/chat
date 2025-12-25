"""
OneDay.run Platform - GitHub Service
Zarządza repozytoriami i plikami na GitHub
"""
import asyncio
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime
from github import Github, GithubException
from github.Repository import Repository
from github.ContentFile import ContentFile
import aiohttp

from config.settings import settings


class GitHubService:
    """
    Serwis do zarządzania repozytoriami GitHub
    Obsługuje:
    - Tworzenie repozytoriów
    - Zarządzanie plikami (CRUD)
    - Commity i branche
    - Webhooks
    """
    
    def __init__(self, token: str = None):
        self.token = token or settings.GITHUB_TOKEN
        self.github = Github(self.token)
        self._user = None
        self.org = settings.GITHUB_ORG

    def _get_user(self):
        if self._user is None:
            self._user = self.github.get_user()
        return self._user

    @property
    def user(self):
        return self._get_user()

    @user.setter
    def user(self, value):
        self._user = value
        
    async def create_repository(
        self,
        name: str,
        description: str = "",
        private: bool = True,
        auto_init: bool = True,
        template: str = None
    ) -> Dict[str, Any]:
        """
        Tworzy nowe repozytorium
        
        Args:
            name: Nazwa repozytorium
            description: Opis
            private: Czy prywatne
            auto_init: Czy inicjalizować z README
            template: Nazwa template repo do użycia
            
        Returns:
            Dict z informacjami o repo
        """
        try:
            # Check if using organization
            if self.org:
                try:
                    org = self.github.get_organization(self.org)
                    if template:
                        # Create from template
                        template_repo = self.github.get_repo(template)
                        repo = org.create_repo_from_template(
                            name=name,
                            repo=template_repo,
                            description=description,
                            private=private
                        )
                    else:
                        repo = org.create_repo(
                            name=name,
                            description=description,
                            private=private,
                            auto_init=auto_init
                        )
                except GithubException:
                    # Fallback to user repo
                    repo = self._get_user().create_repo(
                        name=name,
                        description=description,
                        private=private,
                        auto_init=auto_init
                    )
            else:
                repo = self._get_user().create_repo(
                    name=name,
                    description=description,
                    private=private,
                    auto_init=auto_init
                )
            
            return {
                "success": True,
                "repo_name": repo.full_name,
                "url": repo.html_url,
                "clone_url": repo.clone_url,
                "ssh_url": repo.ssh_url,
                "default_branch": repo.default_branch
            }
            
        except GithubException as e:
            return {
                "success": False,
                "error": str(e),
                "status": e.status
            }

    async def create_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str = None,
        branch: str = None
    ) -> Dict[str, Any]:
        """
        Tworzy nowy plik w repozytorium
        
        Args:
            repo: Nazwa repozytorium (owner/repo)
            path: Ścieżka do pliku
            content: Zawartość pliku
            message: Commit message
            branch: Branch (domyślnie main)
        """
        try:
            repository = self.github.get_repo(repo)
            branch = branch or repository.default_branch
            message = message or f"Add {path}"
            
            result = repository.create_file(
                path=path,
                message=message,
                content=content,
                branch=branch
            )
            
            return {
                "success": True,
                "path": path,
                "sha": result["commit"].sha,
                "url": result["content"].html_url
            }
            
        except GithubException as e:
            return {
                "success": False,
                "error": str(e),
                "path": path
            }

    async def update_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str = None,
        branch: str = None
    ) -> Dict[str, Any]:
        """Aktualizuje istniejący plik"""
        try:
            repository = self.github.get_repo(repo)
            branch = branch or repository.default_branch
            
            # Get current file to get SHA
            file_content = repository.get_contents(path, ref=branch)
            
            result = repository.update_file(
                path=path,
                message=message or f"Update {path}",
                content=content,
                sha=file_content.sha,
                branch=branch
            )
            
            return {
                "success": True,
                "path": path,
                "sha": result["commit"].sha,
                "url": result["content"].html_url
            }
            
        except GithubException as e:
            return {
                "success": False,
                "error": str(e),
                "path": path
            }

    async def create_or_update_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str = None,
        branch: str = None
    ) -> Dict[str, Any]:
        """Tworzy lub aktualizuje plik (upsert)"""
        try:
            repository = self.github.get_repo(repo)
            branch = branch or repository.default_branch
            
            try:
                # Try to get existing file
                file_content = repository.get_contents(path, ref=branch)
                # File exists - update
                return await self.update_file(repo, path, content, message, branch)
            except GithubException:
                # File doesn't exist - create
                return await self.create_file(repo, path, content, message, branch)
                
        except GithubException as e:
            return {
                "success": False,
                "error": str(e),
                "path": path
            }

    async def create_multiple_files(
        self,
        repo: str,
        files: List[Dict[str, str]],
        message: str = "Add multiple files",
        branch: str = None
    ) -> Dict[str, Any]:
        """
        Tworzy wiele plików w jednym lub kilku commitach
        
        Args:
            repo: Nazwa repozytorium
            files: Lista dict z 'path' i 'content'
            message: Commit message
            branch: Branch
        """
        results = []
        errors = []
        
        for file_data in files:
            result = await self.create_or_update_file(
                repo=repo,
                path=file_data["path"],
                content=file_data["content"],
                message=f"{message}: {file_data['path']}",
                branch=branch
            )
            
            if result["success"]:
                results.append(result)
            else:
                errors.append(result)
        
        return {
            "success": len(errors) == 0,
            "created": len(results),
            "errors": len(errors),
            "results": results,
            "error_details": errors
        }

    async def get_file(
        self,
        repo: str,
        path: str,
        branch: str = None
    ) -> Dict[str, Any]:
        """Pobiera zawartość pliku"""
        try:
            repository = self.github.get_repo(repo)
            branch = branch or repository.default_branch
            
            file_content = repository.get_contents(path, ref=branch)
            
            if isinstance(file_content, list):
                # It's a directory
                return {
                    "success": True,
                    "type": "directory",
                    "contents": [{"path": f.path, "type": f.type} for f in file_content]
                }
            
            content = base64.b64decode(file_content.content).decode('utf-8')
            
            return {
                "success": True,
                "type": "file",
                "path": path,
                "content": content,
                "sha": file_content.sha,
                "size": file_content.size,
                "url": file_content.html_url
            }
            
        except GithubException as e:
            return {
                "success": False,
                "error": str(e),
                "path": path
            }

    async def delete_file(
        self,
        repo: str,
        path: str,
        message: str = None,
        branch: str = None
    ) -> Dict[str, Any]:
        """Usuwa plik"""
        try:
            repository = self.github.get_repo(repo)
            branch = branch or repository.default_branch
            
            file_content = repository.get_contents(path, ref=branch)
            
            repository.delete_file(
                path=path,
                message=message or f"Delete {path}",
                sha=file_content.sha,
                branch=branch
            )
            
            return {"success": True, "path": path}
            
        except GithubException as e:
            return {
                "success": False,
                "error": str(e),
                "path": path
            }

    async def create_branch(
        self,
        repo: str,
        branch_name: str,
        from_branch: str = None
    ) -> Dict[str, Any]:
        """Tworzy nowy branch"""
        try:
            repository = self.github.get_repo(repo)
            source_branch = from_branch or repository.default_branch
            
            # Get SHA of source branch
            source = repository.get_branch(source_branch)
            
            # Create new branch
            repository.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=source.commit.sha
            )
            
            return {
                "success": True,
                "branch": branch_name,
                "from": source_branch
            }
            
        except GithubException as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def list_repos(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Lista repozytoriów"""
        repos = []
        
        if self.org:
            try:
                org = self.github.get_organization(self.org)
                for repo in org.get_repos()[:limit]:
                    repos.append({
                        "name": repo.full_name,
                        "url": repo.html_url,
                        "private": repo.private,
                        "updated_at": repo.updated_at.isoformat()
                    })
            except GithubException:
                pass
        
        # Also include user repos
        for repo in self._get_user().get_repos()[:limit]:
            repos.append({
                "name": repo.full_name,
                "url": repo.html_url,
                "private": repo.private,
                "updated_at": repo.updated_at.isoformat()
            })
        
        return repos

    async def get_repo_structure(
        self,
        repo: str,
        path: str = "",
        branch: str = None
    ) -> Dict[str, Any]:
        """Pobiera strukturę katalogów repozytorium"""
        try:
            repository = self.github.get_repo(repo)
            branch = branch or repository.default_branch
            
            contents = repository.get_contents(path, ref=branch)
            
            if not isinstance(contents, list):
                contents = [contents]
            
            structure = []
            for item in contents:
                entry = {
                    "name": item.name,
                    "path": item.path,
                    "type": item.type,
                    "size": item.size if item.type == "file" else None
                }
                
                if item.type == "dir":
                    # Recursively get subdirectory contents
                    subdir = await self.get_repo_structure(repo, item.path, branch)
                    entry["children"] = subdir.get("contents", [])
                
                structure.append(entry)
            
            return {
                "success": True,
                "repo": repo,
                "branch": branch,
                "path": path,
                "contents": structure
            }
            
        except GithubException as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def setup_project_from_template(
        self,
        project_name: str,
        tech_stack: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Tworzy nowy projekt z odpowiedniego template'u
        """
        # Map tech stack to template
        templates = {
            "python_fastapi": f"{self.org}/template-fastapi" if self.org else None,
            "python_django": f"{self.org}/template-django" if self.org else None,
            "node_express": f"{self.org}/template-express" if self.org else None,
            "react_next": f"{self.org}/template-nextjs" if self.org else None,
            "vue_nuxt": f"{self.org}/template-nuxt" if self.org else None,
        }
        
        template = templates.get(tech_stack)
        
        # Create repo
        result = await self.create_repository(
            name=project_name,
            description=description,
            private=True,
            template=template
        )
        
        if result["success"]:
            # Add standard files if no template
            if not template:
                await self._setup_basic_structure(result["repo_name"], tech_stack)
        
        return result

    async def _setup_basic_structure(self, repo: str, tech_stack: str):
        """Tworzy podstawową strukturę projektu"""
        
        basic_files = {
            "python_fastapi": [
                {"path": "src/__init__.py", "content": ""},
                {"path": "src/main.py", "content": self._get_fastapi_main()},
                {"path": "requirements.txt", "content": self._get_requirements("fastapi")},
                {"path": "Dockerfile", "content": self._get_dockerfile("python")},
                {"path": ".gitignore", "content": self._get_gitignore("python")},
            ],
            "python_django": [
                {"path": ".gitignore", "content": self._get_gitignore("python")},
                {"path": "requirements.txt", "content": self._get_requirements("django")},
            ],
            "node_express": [
                {"path": "src/index.js", "content": self._get_express_main()},
                {"path": "package.json", "content": self._get_package_json("express")},
                {"path": ".gitignore", "content": self._get_gitignore("node")},
            ],
        }
        
        files = basic_files.get(tech_stack, [])
        if files:
            await self.create_multiple_files(repo, files, "Initial project structure")

    def _get_fastapi_main(self) -> str:
        return '''"""FastAPI Application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="OneDay Project",
    description="Generated by OneDay.run Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to OneDay Project", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
'''

    def _get_requirements(self, framework: str) -> str:
        reqs = {
            "fastapi": "fastapi>=0.100.0\nuvicorn[standard]>=0.23.0\npydantic>=2.0.0\npython-dotenv>=1.0.0",
            "django": "django>=4.2\ngunicorn>=21.0\npsycopg2-binary>=2.9\npython-dotenv>=1.0.0",
        }
        return reqs.get(framework, "")

    def _get_dockerfile(self, runtime: str) -> str:
        if runtime == "python":
            return '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
'''
        return ""

    def _get_gitignore(self, runtime: str) -> str:
        ignores = {
            "python": "__pycache__/\n*.py[cod]\n*$py.class\n.env\n.venv/\nvenv/\n*.egg-info/\ndist/\nbuild/\n.pytest_cache/\n.mypy_cache/",
            "node": "node_modules/\n.env\ndist/\nbuild/\n*.log\n.DS_Store",
        }
        return ignores.get(runtime, "")

    def _get_express_main(self) -> str:
        return '''const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

app.get('/', (req, res) => {
  res.json({ message: 'Welcome to OneDay Project', status: 'running' });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
'''

    def _get_package_json(self, framework: str) -> str:
        return '''{
  "name": "oneday-project",
  "version": "1.0.0",
  "description": "Generated by OneDay.run Platform",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js",
    "dev": "nodemon src/index.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "dotenv": "^16.3.1"
  },
  "devDependencies": {
    "nodemon": "^3.0.1"
  }
}
'''
