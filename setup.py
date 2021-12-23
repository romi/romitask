from setuptools import setup, Extension, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

s = setup(
    name="romitask",
    version="0.0.1",
    packages=find_packages(),
    scripts=[
        'bin/romi_run_task',
        'bin/print_task_info',
        'bin/romi_run_task_rest_api'
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
        'luigi',
        'toml',
        'watchdog',
        'flask',
        'flask-cors',
        'flask-restful'
    ],
    include_package_data=True
)
