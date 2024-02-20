from setuptools import setup, find_packages

setup(
    name="gptextual",  # This is the name of your PyPI-package.
    version="0.0.1",  # Update the version number for new releases
    packages=find_packages(
        exclude=["tests"]
    ),  # This will include all sub-packages in the package directory
    package_data={"": ["*.tcss"]},
    include_package_data=True,
    description="A configurable, terminal based Chat client for LLMs built with Textual",
    author="Stefan Kirchfeld",
    author_email="stefan.kirchfeld@gmail.com",
    url="https://github.com/yourusername/your-package-name",  # The URL to the github repo
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
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
        "httpx",
        "humanize",
        "langchain",
        "langchain-core",
        "polars",
        "pydantic",
        "pyperclip",
        "rich",
        "shortuuid",
        "textual==0.50.1",
        "tiktoken",
        "toolong==1.2.0",
        "pyyaml",
    ],
    extras_require={
        "openai": ["langchain-openai"],
        "google": ["langchain-google-genai"],
        "sap": ["generative-ai-hub-sdk"],
        "all": ["langchain-openai", "langchain-google-genai", "generative-ai-hub-sdk"],
    },
)
