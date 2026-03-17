"""Setup script for mini-opencode package.

This file provides backward compatibility for tools that require setup.py.
The project primarily uses pyproject.toml for configuration.
"""

from setuptools import setup, find_packages

setup(
    name='mini-opencode',
    version='0.1.0',
    description='mini-OpenCode is a lightweight experimental Coding Agent inspired by Deer-Code and OpenCode.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    author='',
    author_email='',
    url='https://github.com/sure520/mini-opencode',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires='>=3.12',
    install_requires=[
        'dotenv>=0.9.9',
        'firecrawl>=4.13.0',
        'jinja2>=3.1.6',
        'langchain>=1.2.4',
        'langchain-deepseek>=1.0.1',
        'langchain-mcp-adapters>=0.2.1',
        'langchain-tavily>=0.2.16',
        'langgraph>=1.0.6',
        'pexpect>=4.9.0',
        'PyYAML>=6.0.1',
        'structlog>=25.5.0',
        'textual>=7.3.0',
    ],
    extras_require={
        'dev': [
            'mypy>=1.19.1',
            'pytest>=9.0.2',
            'pytest-asyncio>=1.3.0',
            'pytest-cov>=7.0.0',
            'ruff>=0.15.5',
            'types-pexpect>=4.9.0.20260127',
            'types-pyyaml>=6.0.12.20250915',
        ],
    },
    entry_points={
        'console_scripts': [
            'mini-opencode=mini_opencode.main:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    license='MIT',
)
