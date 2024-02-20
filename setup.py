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
        "Development Status :: 3 - Alpha",
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
        "httpx~=0.26.0",
        "humanize~=4.9.0",
        "langchain~=0.1.5",
        "langchain-core~=0.1.19",
        "polars~=0.20.7",
        "pydantic~=2.6.1",
        "pyperclip~=1.8.2",
        "rich~=13.7.0",
        "shortuuid~=1.0.11",
        "textual==0.50.1",
        "tiktoken~=0.5.2",
        "toolong==1.2.0",
        "pyyaml~=6.0.1",
    ],
    extras_require={
        "openai": ["langchain-openai~=0.0.5"],
        "google": ["langchain-google-genai~=0.0.9"],
        "sap": ["generative-ai-hub-sdk~=1.2.2"],
        "all": [
            "langchain-openai~=0.0.5",
            "langchain-google-genai~=0.0.9",
            "generative-ai-hub-sdk~=1.2.2",
        ],
    },
)
