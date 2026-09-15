import json
import re
import tomllib

from pathlib import PurePosixPath


LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".html": "HTML",
    ".css": "CSS",
}


FRAMEWORK_KEYWORDS = {
    "FastAPI": [
        "from fastapi",
        "import fastapi",
        "fastapi==",
    ],
    "Flask": [
        "from flask",
        "import flask",
        "flask==",
    ],
    "Django": [
        "from django",
        "import django",
        "django==",
    ],
    "React": [
        "from 'react'",
        'from "react"',
        '"react":',
    ],
    "Express": [
        "require('express')",
        'require("express")',
        '"express":',
    ],
    "Spring Boot": [
        "spring-boot",
        "@springbootapplication",
    ],
}


COMMAND_PREFIXES = (
    "pip install",
    "python -m pip install",
    "python ",
    "python3 ",
    "uvicorn ",
    "pytest",
    "npm install",
    "npm run",
    "yarn ",
    "pnpm ",
    "docker build",
    "docker run",
    "docker compose",
    "mvn ",
    "./mvnw ",
    "gradle ",
    "./gradlew ",
    "go run",
    "go test",
    "cargo ",
    "dotnet ",
)


def add_source(
    source_map: dict,
    fact_name: str,
    source_file: str,
):
    if fact_name not in source_map:
        source_map[fact_name] = set()

    source_map[fact_name].add(source_file)


def format_source_map(
    source_map: dict,
) -> list[dict]:
    formatted_facts = []

    for fact_name in sorted(source_map):
        formatted_facts.append({
            "name": fact_name,
            "source_files": sorted(
                source_map[fact_name]
            ),
        })

    return formatted_facts


def detect_languages(
    selected_files: list[dict],
) -> list[dict]:
    detected_languages = {}

    for selected_file in selected_files:
        source_file = selected_file["path"]
        file_path = PurePosixPath(source_file)

        extension = file_path.suffix.lower()

        language = LANGUAGE_EXTENSIONS.get(
            extension
        )

        if language:
            add_source(
                detected_languages,
                language,
                source_file,
            )

    return format_source_map(
        detected_languages
    )


def detect_frameworks(
    selected_files: list[dict],
) -> list[dict]:
    detected_frameworks = {}

    for selected_file in selected_files:
        source_file = selected_file["path"]
        content = selected_file["content"].lower()

        for framework, keywords in (
            FRAMEWORK_KEYWORDS.items()
        ):
            if any(
                keyword in content
                for keyword in keywords
            ):
                add_source(
                    detected_frameworks,
                    framework,
                    source_file,
                )

    return format_source_map(
        detected_frameworks
    )


def clean_python_dependency(
    dependency: str,
) -> str:
    dependency = dependency.strip()
    dependency = dependency.split(";")[0]

    package_name = re.split(
        r"[<>=!~\[\s]",
        dependency,
        maxsplit=1,
    )[0]

    return package_name.strip()


def extract_dependencies(
    selected_files: list[dict],
) -> list[dict]:
    detected_dependencies = {}

    for selected_file in selected_files:
        source_file = selected_file["path"]
        file_path = PurePosixPath(source_file)
        file_name = file_path.name.lower()
        content = selected_file["content"]

        if (
            file_name.startswith("requirements")
            and file_path.suffix.lower() == ".txt"
        ):
            for line in content.splitlines():
                line = line.strip()

                if (
                    not line
                    or line.startswith("#")
                    or line.startswith("-")
                ):
                    continue

                dependency = clean_python_dependency(
                    line
                )

                if dependency:
                    add_source(
                        detected_dependencies,
                        dependency,
                        source_file,
                    )

        elif file_name == "package.json":
            try:
                package_data = json.loads(content)
            except json.JSONDecodeError:
                continue

            for section in [
                "dependencies",
                "devDependencies",
            ]:
                packages = package_data.get(
                    section,
                    {},
                )

                for dependency in packages:
                    add_source(
                        detected_dependencies,
                        dependency,
                        source_file,
                    )

        elif file_name == "pyproject.toml":
            try:
                project_data = tomllib.loads(
                    content
                )
            except tomllib.TOMLDecodeError:
                continue

            project_dependencies = (
                project_data
                .get("project", {})
                .get("dependencies", [])
            )

            for dependency_line in project_dependencies:
                dependency = clean_python_dependency(
                    dependency_line
                )

                if dependency:
                    add_source(
                        detected_dependencies,
                        dependency,
                        source_file,
                    )

            poetry_dependencies = (
                project_data
                .get("tool", {})
                .get("poetry", {})
                .get("dependencies", {})
            )

            for dependency in poetry_dependencies:
                if dependency.lower() == "python":
                    continue

                add_source(
                    detected_dependencies,
                    dependency,
                    source_file,
                )

    return format_source_map(
        detected_dependencies
    )


def extract_commands(
    selected_files: list[dict],
) -> list[dict]:
    detected_commands = []
    seen_commands = set()

    for selected_file in selected_files:
        source_file = selected_file["path"]
        file_path = PurePosixPath(source_file)
        file_name = file_path.name.lower()

        is_documentation = (
            file_name.startswith("readme")
            or file_path.suffix.lower()
            in {".md", ".rst", ".sh"}
        )

        if not is_documentation:
            continue

        for line in selected_file[
            "content"
        ].splitlines():
            command = line.strip()
            command = command.strip("`")

            if command.startswith("$ "):
                command = command[2:]

            if command.startswith("> "):
                command = command[2:]

            if command.lower().startswith(
                COMMAND_PREFIXES
            ):
                command_key = (
                    command.lower(),
                    source_file,
                )

                if command_key in seen_commands:
                    continue

                seen_commands.add(command_key)

                detected_commands.append({
                    "command": command,
                    "source_file": source_file,
                })

    return detected_commands


def extract_api_endpoints(
    selected_files: list[dict],
) -> list[dict]:
    detected_endpoints = []
    seen_endpoints = set()

    fastapi_pattern = re.compile(
        r"@(?:app|router)\."
        r"(get|post|put|patch|delete)"
        r"\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )

    express_pattern = re.compile(
        r"\b(?:app|router)\."
        r"(get|post|put|patch|delete)"
        r"\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )

    spring_pattern = re.compile(
        r"@(Get|Post|Put|Patch|Delete)"
        r"Mapping\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )

    for selected_file in selected_files:
        source_file = selected_file["path"]
        content = selected_file["content"]

        for pattern in [
            fastapi_pattern,
            express_pattern,
            spring_pattern,
        ]:
            for method, route in pattern.findall(
                content
            ):
                endpoint_key = (
                    method.upper(),
                    route,
                    source_file,
                )

                if endpoint_key in seen_endpoints:
                    continue

                seen_endpoints.add(endpoint_key)

                detected_endpoints.append({
                    "method": method.upper(),
                    "path": route,
                    "source_file": source_file,
                })

    return detected_endpoints


def extract_environment_variables(
    selected_files: list[dict],
) -> list[dict]:
    environment_variables = {}

    patterns = [
        re.compile(
            r"os\.getenv\(\s*['\"]"
            r"([A-Z][A-Z0-9_]*)['\"]"
        ),
        re.compile(
            r"os\.environ(?:\.get)?"
            r"\(\s*['\"]"
            r"([A-Z][A-Z0-9_]*)['\"]"
        ),
        re.compile(
            r"os\.environ\[\s*['\"]"
            r"([A-Z][A-Z0-9_]*)['\"]"
        ),
        re.compile(
            r"process\.env\."
            r"([A-Z][A-Z0-9_]*)"
        ),
        re.compile(
            r"\$\{([A-Z][A-Z0-9_]*)\}"
        ),
    ]

    for selected_file in selected_files:
        source_file = selected_file["path"]
        content = selected_file["content"]

        for pattern in patterns:
            for variable_name in pattern.findall(
                content
            ):
                add_source(
                    environment_variables,
                    variable_name,
                    source_file,
                )

        file_name = PurePosixPath(
            source_file
        ).name.lower()

        if file_name in {
            ".env.example",
            ".env.sample",
            ".env.template",
        }:
            for line in content.splitlines():
                match = re.match(
                    r"^([A-Z][A-Z0-9_]*)\s*=",
                    line.strip(),
                )

                if match:
                    add_source(
                        environment_variables,
                        match.group(1),
                        source_file,
                    )

    return format_source_map(
        environment_variables
    )


def detect_docker_files(
    selected_files: list[dict],
) -> list[str]:
    docker_files = []

    for selected_file in selected_files:
        source_file = selected_file["path"]

        file_name = PurePosixPath(
            source_file
        ).name.lower()

        if (
            file_name.startswith("dockerfile")
            or file_name.startswith(
                "docker-compose"
            )
            or file_name == "compose.yaml"
            or file_name == "compose.yml"
        ):
            docker_files.append(source_file)

    return sorted(docker_files)


def detect_important_folders(
    selected_files: list[dict],
) -> list[str]:
    important_folders = set()

    for selected_file in selected_files:
        file_path = PurePosixPath(
            selected_file["path"]
        )

        if len(file_path.parts) > 1:
            top_folder = file_path.parts[0]

            if not top_folder.startswith("."):
                important_folders.add(
                    top_folder
                )

    return sorted(important_folders)


def analyze_repository(
    repository_info: dict,
    selected_files: list[dict],
) -> dict:
    return {
        "repository_name": repository_info[
            "repository"
        ],
        "description": repository_info.get(
            "description"
        ),
        "languages": detect_languages(
            selected_files
        ),
        "frameworks": detect_frameworks(
            selected_files
        ),
        "dependencies": extract_dependencies(
            selected_files
        ),
        "commands": extract_commands(
            selected_files
        ),
        "api_endpoints": extract_api_endpoints(
            selected_files
        ),
        "environment_variables": (
            extract_environment_variables(
                selected_files
            )
        ),
        "docker_files": detect_docker_files(
            selected_files
        ),
        "important_folders": (
            detect_important_folders(
                selected_files
            )
        ),
    }