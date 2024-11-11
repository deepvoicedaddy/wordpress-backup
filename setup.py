from setuptools import setup, find_packages

setup(
    name="wordpressdotcom-backup",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "python-frontmatter>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "wp-backup=wp_backup:main",
        ],
    },
    author="Deep Voice Daddy",
    author_email="thedeepvoicedaddy@proton.me",
    description="A tool to backup WordPress.com blog posts",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/deepvoicedaddy/wordpressdotcom-backup",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
