from setuptools import setup, find_packages

setup(
    name="CommandRunner",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    license='MIT',
    description='A Django app to run commands on front-end.',
    url='https://github.com/ARezaK/command-runner',
    install_requires=[
        "Django>=2.0",  # Ensure you list all necessary dependencies
    ],
    author='ARezaK',
    author_email='sometimestheworldrunsslow@github.com',
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
    ],
)
