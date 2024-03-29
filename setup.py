from setuptools import setup, find_packages

setup(
    name="gptextual",
    version="0.0.9",
    packages=find_packages(exclude=["tests"]),
    package_data={"": ["*.tcss"]},
    include_package_data=True,
    description="A configurable, terminal based Chat client for LLMs built with Textual",
    author="Stefan Kirchfeld",
    author_email="stefan.kirchfeld@gmail.com",
    url="https://github.com/stefankirchfeld/gptextual",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    entry_points={
        "console_scripts": [
            "gptx = gptextual.textual_ui.app:run",
        ],
        "gptextual_function": [
            "google_web_search = gptextual.runtime.function_calling.functions:google_web_search"
        ],
    },
    keywords="gpt,chat,llm,chatgpt,langchain,openai,sap,textual,terminal",
    install_requires=[
        "httpx~=0.26.0",
        "humanize~=4.9.0",
        "langchain~=0.1.10",
        "langchain-core~=0.1.28",
        "polars~=0.20.7",
        "pydantic~=2.6.1",
        "pyperclip~=1.8.2",
        "rich~=13.7.0",
        "shortuuid~=1.0.11",
        "textual==0.50.1",
        "tiktoken~=0.5.2",
        "toolong==1.2.0",
        "pyyaml~=6.0.1",
        "setuptools~=69.1.0",
    ],
    extras_require={
        "openai": ["langchain-openai~=0.0.8"],
        "google": ["langchain-google-genai~=0.0.9"],
        "sap": ["generative-ai-hub-sdk~=1.2.2"],
        "anthropic": ["langchain-anthropic~=0.1.1"],
        "all": [
            "langchain-openai~=0.0.8",
            "langchain-google-genai~=0.0.9",
            "generative-ai-hub-sdk~=1.2.2",
            "langchain-anthropic~=0.1.1",
        ],
    },
)
