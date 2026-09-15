import json

from app.repo_analyzer import analyze_repository


def get_fact_names(facts: list[dict]) -> list[str]:
    return [
        fact["name"]
        for fact in facts
    ]


def test_python_fastapi_repository_analysis():
    repository_info = {
        "repository": "example-api",
        "description": "Example FastAPI project",
    }

    selected_files = [
        {
            "path": "app/main.py",
            "content": (
                "from fastapi import FastAPI\n"
                "import os\n"
                'AWS_REGION = os.getenv("AWS_REGION")\n'
                '@app.get("/health")\n'
                "def health(): pass\n"
            ),
            "size": 150,
        },
        {
            "path": "requirements.txt",
            "content": (
                "fastapi==0.115.0\n"
                "uvicorn>=0.30.0\n"
                "pytest\n"
            ),
            "size": 50,
        },
        {
            "path": "README.md",
            "content": (
                "pip install -r requirements.txt\n"
                "uvicorn app.main:app --reload\n"
            ),
            "size": 70,
        },
        {
            "path": "Dockerfile",
            "content": "FROM python:3.12",
            "size": 20,
        },
    ]

    facts = analyze_repository(
        repository_info,
        selected_files,
    )

    assert "Python" in get_fact_names(
        facts["languages"]
    )

    assert "FastAPI" in get_fact_names(
        facts["frameworks"]
    )

    assert "fastapi" in get_fact_names(
        facts["dependencies"]
    )

    assert "uvicorn" in get_fact_names(
        facts["dependencies"]
    )

    assert {
        "method": "GET",
        "path": "/health",
        "source_file": "app/main.py",
    } in facts["api_endpoints"]

    assert "AWS_REGION" in get_fact_names(
        facts["environment_variables"]
    )

    assert facts["docker_files"] == [
        "Dockerfile"
    ]

    assert "app" in facts["important_folders"]


def test_javascript_express_repository_analysis():
    repository_info = {
        "repository": "example-node-api",
        "description": "Example Express project",
    }

    package_content = json.dumps({
        "dependencies": {
            "express": "^5.0.0",
        },
        "devDependencies": {
            "jest": "^30.0.0",
        },
    })

    selected_files = [
        {
            "path": "package.json",
            "content": package_content,
            "size": len(package_content),
        },
        {
            "path": "src/index.js",
            "content": (
                'const express = require("express");\n'
                "const port = process.env.PORT;\n"
                'app.post("/users", handler);\n'
            ),
            "size": 100,
        },
    ]

    facts = analyze_repository(
        repository_info,
        selected_files,
    )

    assert "JavaScript" in get_fact_names(
        facts["languages"]
    )

    assert "Express" in get_fact_names(
        facts["frameworks"]
    )

    assert "express" in get_fact_names(
        facts["dependencies"]
    )

    assert "jest" in get_fact_names(
        facts["dependencies"]
    )

    assert {
        "method": "POST",
        "path": "/users",
        "source_file": "src/index.js",
    } in facts["api_endpoints"]

    assert "PORT" in get_fact_names(
        facts["environment_variables"]
    )


def test_java_spring_repository_analysis():
    repository_info = {
        "repository": "example-java-api",
        "description": "Example Spring project",
    }

    selected_files = [
        {
            "path": "src/Application.java",
            "content": (
                "@SpringBootApplication\n"
                '@GetMapping("/hello")\n'
                "public String hello() {"
                ' return "Hello"; }\n'
            ),
            "size": 100,
        }
    ]

    facts = analyze_repository(
        repository_info,
        selected_files,
    )

    assert "Java" in get_fact_names(
        facts["languages"]
    )

    assert "Spring Boot" in get_fact_names(
        facts["frameworks"]
    )

    assert {
        "method": "GET",
        "path": "/hello",
        "source_file": "src/Application.java",
    } in facts["api_endpoints"]