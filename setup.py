"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

from setuptools import setup, find_packages

with open("docs/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="maj-document-recognition",
    version="1.0.0",
    author="MAJ",
    author_email="m.a.j.puzik@example.com",
    description="Kompletní OCR systém pro klasifikaci dokumentů s AI a Thunderbird/Paperless-NGX integrací",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/majpuzik/maj-document-recognition",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "flask>=2.3.0",
        "flask-cors>=4.0.0",
        "requests>=2.31.0",
        "pyyaml>=6.0",
        "pillow>=10.0.0",
        "pytesseract>=0.3.10",
        "pdf2image>=1.16.3",
        "python-docx>=0.8.11",
        "numpy>=1.24.0",
        "scikit-learn>=1.3.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "aiohttp>=3.8.0",
        "python-magic>=0.4.27",
        "opencv-python>=4.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "flake8>=6.1.0",
            "mypy>=1.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "maj-docrecog=src.main:main",
            "maj-docrecog-web=src.web.app:main",
        ],
    },
)
