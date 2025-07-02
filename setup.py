from setuptools import setup, find_packages
import os

# 读取 README.md 文件内容
long_description = ""
if os.path.exists('README.md'):
    with open('README.md', 'r', encoding='utf-8') as f:
        long_description = f.read()

setup(
    name='nga-cli',
    version='0.0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'rich',
        'inquirer',
        'click',
        'PySocks',
        'certifi',
        'httpx[socks]',
        'prompt-toolkit',
    ],
    entry_points={
        'console_scripts': [
            'nga = nga_cli.cli:main_cli',
        ],
    },
    description='一个用于在命令行中浏览 NGA 论坛的工具。',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/gyokusei/nga-cli',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Terminals",
        "Topic :: Utilities",
    ],
    python_requires='>=3.8',
)
