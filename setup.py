from setuptools import setup, Extension, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

s = setup(
    name="romitask",
    version="0.10.99",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    scripts=[
        'bin/romi_run_task',
        'bin/print_task_info'
    ],
    author="Nabil Ait Taleb",
    author_email="mohamednabil.aittaleb@sony.com",
    description="A romi task runner",
    long_description=long_description,
    long_description_content_type="text/markdown",
    zip_safe=False,
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    install_requires=[
        'luigi==3.0.3',
        'tqdm',
        'toml',
        'watchdog',
        'colorlog'
    ],
    include_package_data=True
)