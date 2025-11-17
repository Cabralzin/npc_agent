from setuptools import setup, find_packages

setup(
    name="npc_agent",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'langchain>=0.1.0',
        'langchain-openai>=0.0.1',
        'langgraph>=0.1.0',
        'pydantic>=2.0.0',
        'streamlit>=1.32.0',
        'python-dotenv>=1.0.1'
    ],
    python_requires='>=3.8',
)
