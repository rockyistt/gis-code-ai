"""
GIS Code AI 安装配置
"""
from setuptools import setup, find_packages
from pathlib import Path

# 读取 README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# 读取依赖
requirements = (this_directory / "requirements.txt").read_text(encoding='utf-8').splitlines()

setup(
    name="gis-code-ai",
    version="0.1.0",
    author="GIS Code AI Team",
    author_email="",
    description="AI自动化在GIS测试方面的应用",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rockyistt/gis-code-ai",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: GIS",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "gis-code-ai=src.main:main",
        ],
    },
)
