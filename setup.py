import setuptools

with open("README.rst", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="notesdir",
    version="0.0.4",
    author="Jacob Williams",
    author_email="jacobaw@gmail.com",
    description="Helpers for managing notes as a directory full of files.",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/brokensandals/notesdir",
    packages=setuptools.find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'notesdir = notesdir.cli:main'
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'beautifulsoup4>=4.9.1',
        'lxml',
        'Mako>=1.1.3',
        'pypdf4',
        'pyyaml>=5.3.1',
        'shortuuid',
        'terminaltables',
    ],
    python_requires='>=3.7',
)
