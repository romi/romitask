from setuptools import find_packages
from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

s = setup(
    name="romitask",
    version="0.10.99",  # overriden by `use_scm_version=True`
    packages=find_packages('src'),
    package_dir={'': 'src'},
    scripts=[
        'bin/romi_run_task',
        'bin/print_task_info'
    ],
    author="Nabil Ait Taleb",
    author_email="mohamednabil.aittaleb@sony.com",
    description="The ROMI task runner, a luigi based task pipeline.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    zip_safe=False,
    python_requires='>=3.7',
    # use_scm_version=True,
    # setup_requires=['setuptools_scm'],
    install_requires=[],
    include_package_data=True
)